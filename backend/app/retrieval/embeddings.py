"""Small synchronous client for Ollama's local embedding endpoint."""

from __future__ import annotations

import json
import math
import socket
from collections.abc import Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

REQUEST_BATCH_SIZE = 32


class EmbeddingError(RuntimeError):
    """A stable provider error with a message suitable for Persian UI display."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class OllamaEmbedder:
    """Create text vectors through an Ollama server on the local network."""

    def __init__(
        self, base_url: str, model: str, timeout_seconds: float = 30.0
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def embed(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed texts in bounded requests and validate the returned vectors."""
        vectors: list[list[float]] = []
        dimension: int | None = None
        for start in range(0, len(texts), REQUEST_BATCH_SIZE):
            batch = texts[start : start + REQUEST_BATCH_SIZE]
            batch_vectors = self._embed_batch(batch)
            for vector in batch_vectors:
                if dimension is None:
                    dimension = len(vector)
                elif len(vector) != dimension:
                    raise EmbeddingError(
                        "embedding_dimension_mismatch",
                        "ابعاد بردارهای دریافتی یکسان نیست. مدل را بررسی کنید.",
                    )
            vectors.extend(batch_vectors)
        return vectors

    def _embed_batch(self, texts: Sequence[str]) -> list[list[float]]:
        request_body = json.dumps(
            {"model": self.model, "input": list(texts)}, ensure_ascii=False
        ).encode("utf-8")
        request = Request(
            f"{self.base_url}/api/embed",
            data=request_body,
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urlopen(request, timeout=self.timeout_seconds) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except HTTPError as error:
            if error.code == 404:
                raise EmbeddingError(
                    "embedding_model_missing",
                    f"مدل {self.model} در Ollama پیدا نشد. مدل را نصب کنید و دوباره تلاش کنید.",
                ) from None
            raise EmbeddingError(
                "embedding_provider_error",
                "Ollama نتوانست بردارهای متنی را بسازد. وضعیت سرویس و مدل را بررسی کنید.",
            ) from None
        except (URLError, TimeoutError, socket.timeout, OSError):
            raise EmbeddingError(
                "embedding_unavailable",
                "سرویس Ollama در دسترس نیست. وضعیت Ollama را بررسی و دوباره تلاش کنید.",
            ) from None
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise EmbeddingError(
                "embedding_invalid_response",
                "پاسخ Ollama برای بردارسازی معتبر نیست. سرویس را بررسی کنید.",
            ) from None

        if not isinstance(payload, dict):
            raise _invalid_response()
        raw_vectors = payload.get("embeddings")
        if not isinstance(raw_vectors, list):
            raise _invalid_response()
        if len(raw_vectors) != len(texts):
            raise EmbeddingError(
                "embedding_count_mismatch",
                "تعداد بردارهای Ollama با تعداد متن‌ها برابر نیست. دوباره تلاش کنید.",
            )

        vectors: list[list[float]] = []
        dimension: int | None = None
        for raw_vector in raw_vectors:
            if not isinstance(raw_vector, list) or not raw_vector:
                raise _invalid_vector()
            if any(
                isinstance(value, bool) or not isinstance(value, (int, float))
                for value in raw_vector
            ):
                raise _invalid_vector()
            vector = [float(value) for value in raw_vector]
            if any(not math.isfinite(value) for value in vector):
                raise _invalid_vector()
            if dimension is None:
                dimension = len(vector)
            elif len(vector) != dimension:
                raise EmbeddingError(
                    "embedding_dimension_mismatch",
                    "ابعاد بردارهای دریافتی یکسان نیست. مدل را بررسی کنید.",
                )
            vectors.append(vector)
        return vectors


def _invalid_response() -> EmbeddingError:
    return EmbeddingError(
        "embedding_invalid_response",
        "پاسخ Ollama برای بردارسازی معتبر نیست. سرویس را بررسی کنید.",
    )


def _invalid_vector() -> EmbeddingError:
    return EmbeddingError(
        "embedding_invalid_vector",
        "یکی از بردارهای دریافتی معتبر نیست. مدل Ollama را بررسی کنید.",
    )
