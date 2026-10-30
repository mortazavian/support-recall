from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.retrieval.embeddings import EmbeddingError
from app.retrieval.index import VectorIndex
from app.storage import initialize_storage


class DeterministicEmbedder:
    def __init__(self, fail_on_call: int | None = None) -> None:
        self.fail_on_call = fail_on_call
        self.calls = 0

    def embed(self, texts: list[str]) -> list[list[float]]:
        self.calls += 1
        if self.calls == self.fail_on_call:
            raise EmbeddingError("embedding_unavailable", "provider unavailable")
        return [_vector_for(text) for text in texts]


def _vector_for(text: str) -> list[float]:
    vector = [0.0] * 64
    for word in text.lower().split():
        bucket = int.from_bytes(hashlib.sha256(word.encode("utf-8")).digest()[:2]) % len(vector)
        vector[bucket] += 1.0
    return vector


def _database(tmp_path: Path, *, text: str = "Refund arrived yesterday.") -> Path:
    database_path = tmp_path / "supportrecall.sqlite3"
    initialize_storage(database_path)
    messages = [
        {"role": "customer", "content": f"When will the refund arrive? {text}"},
        {"role": "support", "content": "The refund was processed yesterday."},
    ]
    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "INSERT INTO sources (id, original_filename, stored_name, format, content_hash, "
            "status, record_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            ("source-1", "support.json", "stored.json", "json", "hash-1", "ready", 1, "now", "now"),
        )
        connection.execute(
            "INSERT INTO support_records (id, source_id, position, conversation_id, date, "
            "product, category, messages_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (
                "source-1:1",
                "source-1",
                1,
                "conversation-1",
                None,
                None,
                None,
                json.dumps(messages, ensure_ascii=False),
            ),
        )
    return database_path


def _index(tmp_path: Path, embedder: DeterministicEmbedder | None = None) -> VectorIndex:
    return VectorIndex(
        vector_dir=tmp_path / "vectors",
        embedding_model="test-embedding-model",
        embedder=embedder or DeterministicEmbedder(),
    )


def test_index_uses_deterministic_ids_source_metadata_and_profile(tmp_path) -> None:
    database_path = _database(tmp_path)
    index = _index(tmp_path)

    count = index.index_source(database_path, "source-1")
    stored = index.collection.get(include=["metadatas", "documents"])

    assert count == 1
    assert stored["ids"] == ["source-1:1:1"]
    metadata = stored["metadatas"][0]
    assert metadata["source_id"] == "source-1"
    assert metadata["record_id"] == "source-1:1"
    assert metadata["conversation_id"] == "conversation-1"
    assert metadata["position"] == 1
    assert "date" not in metadata
    assert "product" not in metadata
    assert "category" not in metadata
    assert index.collection.metadata["embedding_model"] == "test-embedding-model"
    assert index.collection.metadata["embedding_dimension"] == 64


def test_search_returns_nearest_chunk_with_cosine_distance(tmp_path) -> None:
    database_path = _database(tmp_path)
    index = _index(tmp_path)
    index.index_source(database_path, "source-1")

    results = index.search("refund processed", limit=1)

    assert len(results) == 1
    assert results[0]["metadata"]["conversation_id"] == "conversation-1"
    assert "refund" in results[0]["text"].lower()
    assert 0 <= results[0]["distance"] <= 2


def test_vectors_persist_after_reopening_the_index(tmp_path) -> None:
    database_path = _database(tmp_path)
    index = _index(tmp_path)
    index.index_source(database_path, "source-1")
    del index

    reopened = _index(tmp_path)

    assert reopened.search("refund", limit=1)[0]["metadata"]["source_id"] == "source-1"


def test_indexing_again_replaces_source_chunks_without_duplicate_ids(tmp_path) -> None:
    database_path = _database(tmp_path)
    index = _index(tmp_path)

    index.index_source(database_path, "source-1")
    index.index_source(database_path, "source-1")

    stored = index.collection.get(include=[])
    assert index.collection.count() == 1
    assert stored["ids"] == ["source-1:1:1"]


def test_delete_source_removes_all_its_vectors(tmp_path) -> None:
    database_path = _database(tmp_path)
    index = _index(tmp_path)
    index.index_source(database_path, "source-1")

    index.delete_source("source-1")

    assert index.collection.count() == 0
    assert index.search("refund") == []


def test_failed_index_can_be_retried_without_duplicate_vectors(tmp_path) -> None:
    long_text = " ".join(f"message{index}" for index in range(10_000))
    database_path = _database(tmp_path, text=long_text)
    embedder = DeterministicEmbedder(fail_on_call=2)
    index = _index(tmp_path, embedder)

    with pytest.raises(EmbeddingError):
        index.index_source(database_path, "source-1")
    assert index.collection.count() == 0

    embedder.fail_on_call = None
    chunk_count = index.index_source(database_path, "source-1")

    assert chunk_count > 32
    assert index.collection.count() == chunk_count
    assert len(index.collection.get(include=[])["ids"]) == chunk_count
