from __future__ import annotations

import hashlib
import json
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.index import VectorIndex
from app.settings import Settings


class DeterministicEmbedder:
    def __init__(self, dimension: int = 256) -> None:
        self.dimension = dimension

    def embed(self, texts: list[str]) -> list[list[float]]:
        return [_vector_for(text, self.dimension) for text in texts]


class FailingEmbedder:
    def embed(self, texts: list[str]) -> list[list[float]]:
        raise EmbeddingError("embedding_unavailable", "سرویس Ollama در دسترس نیست.")


def _vector_for(text: str, dimension: int) -> list[float]:
    vector = [0.0] * dimension
    for word in re.findall(r"\w+", text.casefold()):
        bucket = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:2]) % dimension
        vector[bucket] += 1.0
    return vector


def _app(tmp_path, *, model: str = "test-model", embedder=None):
    settings = Settings(data_dir=tmp_path / "data", embedding_model=model)
    index = VectorIndex(settings.vector_dir, model, embedder or DeterministicEmbedder())
    return settings, index, create_app(settings, vector_index=index)


def _import_record(client: TestClient, record: dict[str, str], filename: str) -> dict:
    content = json.dumps([record], ensure_ascii=False).encode("utf-8")
    response = client.post(
        "/api/sources/import",
        files={"file": (filename, content, "application/json")},
    )
    assert response.status_code == 200, response.text
    return response.json()["source"]


def _persian_record() -> dict[str, str]:
    return {
        "conversation_id": "persian-reset",
        "product": "حساب کاربری",
        "category": "ورود",
        "question": "چطور رمز عبور را بازیابی کنم؟",
        "answer": "از صفحه ورود گزینه فراموشی رمز را انتخاب کنید.",
    }


def _english_record() -> dict[str, str]:
    return {
        "conversation_id": "english-reset",
        "product": "account",
        "category": "login",
        "question": "How do I reset my password?",
        "answer": "Select forgot password on the sign in page.",
    }


def test_inspect_returns_source_linked_persian_and_english_excerpts(tmp_path) -> None:
    settings, index, app = _app(tmp_path)
    with TestClient(app) as client:
        persian_source = _import_record(client, _persian_record(), "persian.json")
        english_source = _import_record(client, _english_record(), "english.json")
        persian = client.post(
            "/api/retrieval/inspect", json={"query": "بازیابی رمز عبور"}
        )
        english = client.post(
            "/api/retrieval/inspect", json={"query": "reset password"}
        )

    assert persian.status_code == 200
    assert english.status_code == 200
    persian_result = persian.json()["results"][0]
    english_result = english.json()["results"][0]
    assert persian_result["source_id"] == persian_source["id"]
    assert persian_result["filename"] == "persian.json"
    assert persian_result["conversation_id"] == "persian-reset"
    assert persian_result["position"] == 1
    assert persian_result["product"] == "حساب کاربری"
    assert persian_result["category"] == "ورود"
    assert "رمز عبور" in persian_result["excerpt"]
    assert english_result["source_id"] == english_source["id"]
    assert english_result["filename"] == "english.json"
    assert english_result["conversation_id"] == "english-reset"
    assert "password" in english_result["excerpt"].lower()
    assert isinstance(persian_result["distance"], float)
    assert index.collection.count() == 2
    assert settings.database_path.is_file()


@pytest.mark.parametrize(
    "payload",
    [
        {"query": "   "},
        {"query": "password", "limit": 0},
        {"query": "password", "limit": 11},
    ],
)
def test_inspect_rejects_blank_query_and_out_of_range_limit(tmp_path, payload) -> None:
    _, _, app = _app(tmp_path)

    with TestClient(app) as client:
        response = client.post("/api/retrieval/inspect", json=payload)

    assert response.status_code == 422


def test_inspect_returns_provider_error_without_generating_an_answer(tmp_path) -> None:
    settings, index, app = _app(tmp_path)
    with TestClient(app) as client:
        _import_record(client, _english_record(), "english.json")
        index.embedder = FailingEmbedder()
        response = client.post(
            "/api/retrieval/inspect", json={"query": "reset password"}
        )

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "embedding_unavailable"
    assert any(ord(character) > 127 for character in response.json()["detail"]["message"])
    assert settings.database_path.is_file()


@pytest.mark.parametrize("profile_change", ["model", "dimension"])
def test_inspect_requires_reindex_after_embedding_profile_changes(
    tmp_path, profile_change: str
) -> None:
    original_settings, original_index, original_app = _app(tmp_path)
    with TestClient(original_app) as client:
        _import_record(client, _english_record(), "english.json")

    if profile_change == "model":
        model = "changed-model"
        embedder = DeterministicEmbedder()
    else:
        model = "test-model"
        embedder = DeterministicEmbedder(dimension=128)
    changed_settings = Settings(
        data_dir=original_settings.data_dir,
        embedding_model=model,
    )
    changed_index = VectorIndex(changed_settings.vector_dir, model, embedder)

    with TestClient(create_app(changed_settings, vector_index=changed_index)) as client:
        response = client.post("/api/retrieval/inspect", json={"query": "password reset"})

    assert original_index.collection.count() == 1
    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "reindex_required"
    assert any(ord(character) > 127 for character in response.json()["detail"]["message"])
