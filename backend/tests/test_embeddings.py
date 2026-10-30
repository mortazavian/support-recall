from __future__ import annotations

import json
import socket
import time
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import Iterator

import pytest

from app.retrieval.embeddings import EmbeddingError, OllamaEmbedder
from app.settings import Settings


@contextmanager
def _ollama_server(
    response: dict | bytes,
    *,
    status: int = 200,
    delay_seconds: float = 0,
) -> Iterator[tuple[str, list[tuple[str, dict]]]]:
    requests: list[tuple[str, dict]] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            requests.append((self.path, payload))
            if delay_seconds:
                time.sleep(delay_seconds)
            body = response(payload) if callable(response) else response
            if isinstance(body, dict):
                body = json.dumps(body).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            try:
                self.wfile.write(body)
            except BrokenPipeError:
                pass

        def log_message(self, format: str, *args: object) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}", requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def test_sends_ollama_embed_request_and_returns_vectors() -> None:
    with _ollama_server({"embeddings": [[0.1, 0.2], [0.3, 0.4]]}) as (url, requests):
        vectors = OllamaEmbedder(url, "embeddinggemma:latest").embed(["فارسی", "English"])

    assert vectors == [[0.1, 0.2], [0.3, 0.4]]
    assert requests == [
        (
            "/api/embed",
            {"model": "embeddinggemma:latest", "input": ["فارسی", "English"]},
        )
    ]


def test_splits_large_embedding_requests_into_batches_of_32() -> None:
    def respond(payload: dict) -> dict:
        return {"embeddings": [[float(index), 1.0] for index, _ in enumerate(payload["input"])]}

    with _ollama_server(respond) as (url, requests):
        vectors = OllamaEmbedder(url, "local-model").embed([f"item {i}" for i in range(33)])

    assert len(vectors) == 33
    assert [len(request[1]["input"]) for request in requests] == [32, 1]


@pytest.mark.parametrize(
    ("response", "code"),
    [
        ({"embeddings": []}, "embedding_count_mismatch"),
        (b"{not json", "embedding_invalid_response"),
        ({"embeddings": [[0.1], [0.1, 0.2]]}, "embedding_dimension_mismatch"),
        (b'{"embeddings":[[NaN],[0.1]]}', "embedding_invalid_vector"),
        ({"unexpected": []}, "embedding_invalid_response"),
    ],
)
def test_embed_rejects_invalid_vector_responses(response: dict | bytes, code: str) -> None:
    with _ollama_server(response) as (url, _):
        with pytest.raises(EmbeddingError) as error:
            OllamaEmbedder(url, "local-model").embed(["one", "two"])

    assert error.value.code == code
    assert any(ord(character) > 127 for character in error.value.message)


def test_embed_maps_missing_model_to_actionable_error() -> None:
    with _ollama_server(b'{"error":"model not found"}', status=404) as (url, _):
        with pytest.raises(EmbeddingError) as error:
            OllamaEmbedder(url, "missing-model").embed(["one"])

    assert error.value.code == "embedding_model_missing"


def test_embed_reports_timeout() -> None:
    with _ollama_server(
        {"embeddings": [[0.1]]}, delay_seconds=0.15
    ) as (url, _):
        with pytest.raises(EmbeddingError) as error:
            OllamaEmbedder(url, "local-model", timeout_seconds=0.01).embed(["one"])

    assert error.value.code == "embedding_unavailable"


def test_embed_reports_connection_failure() -> None:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    with pytest.raises(EmbeddingError) as error:
        OllamaEmbedder(f"http://127.0.0.1:{port}", "local-model").embed(["one"])

    assert error.value.code == "embedding_unavailable"


def test_empty_embedding_input_does_not_call_provider() -> None:
    assert OllamaEmbedder("http://127.0.0.1:1", "local-model").embed([]) == []


def test_settings_default_to_local_ollama_and_data_local_vectors(tmp_path) -> None:
    settings = Settings(data_dir=tmp_path)

    assert settings.ollama_base_url == "http://localhost:11434"
    assert settings.embedding_model == "embeddinggemma:latest"
    assert settings.vector_dir == tmp_path / "vectors"


def test_settings_read_provider_and_vector_overrides(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("SUPPORTRECALL_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("SUPPORTRECALL_VECTOR_DIR", str(tmp_path / "vectors"))
    monkeypatch.setenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434/")
    monkeypatch.setenv("SUPPORTRECALL_EMBEDDING_MODEL", "embeddinggemma:test")

    settings = Settings.from_environment()

    assert settings.vector_dir == tmp_path / "vectors"
    assert settings.ollama_base_url == "http://127.0.0.1:11434"
    assert settings.embedding_model == "embeddinggemma:test"
