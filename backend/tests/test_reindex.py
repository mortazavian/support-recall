from __future__ import annotations

import hashlib
import json
import sqlite3
from pathlib import Path

import pytest

from app.retrieval.embeddings import EmbeddingError
from app.retrieval.index import RetrievalError, VectorIndex
from app.storage import initialize_storage


class DeterministicEmbedder:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail

    def embed(self, texts: list[str]) -> list[list[float]]:
        if self.fail:
            raise EmbeddingError("embedding_unavailable", "provider unavailable")
        vectors = []
        for text in texts:
            vector = [0.0] * 64
            for word in text.lower().split():
                bucket = int.from_bytes(hashlib.sha256(word.encode()).digest()[:2]) % 64
                vector[bucket] += 1.0
            vectors.append(vector)
        return vectors


def _database(tmp_path: Path, sources: list[tuple[str, str]]) -> tuple[Path, Path]:
    database_path = tmp_path / "supportrecall.sqlite3"
    uploads_dir = tmp_path / "uploads"
    uploads_dir.mkdir()
    initialize_storage(database_path)
    with sqlite3.connect(database_path) as connection:
        for source_id, status in sources:
            connection.execute(
                "INSERT INTO sources (id, original_filename, stored_name, format, content_hash, "
                "status, record_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    source_id,
                    f"{source_id}.json",
                    f"{source_id}.json",
                    "json",
                    f"hash-{source_id}",
                    status,
                    1,
                    "now",
                    "now",
                ),
            )
            connection.execute(
                "INSERT INTO support_records (id, source_id, position, conversation_id, "
                "messages_json) VALUES (?, ?, ?, ?, ?)",
                (
                    f"{source_id}:1",
                    source_id,
                    1,
                    f"conversation-{source_id}",
                    json.dumps(
                        [
                            {"role": "customer", "content": f"Question for {source_id}"},
                            {"role": "support", "content": f"Answer for {source_id}"},
                        ]
                    ),
                ),
            )
            (uploads_dir / f"{source_id}.json").write_text("original upload", encoding="utf-8")
    return database_path, uploads_dir


def _index(tmp_path: Path, embedder: DeterministicEmbedder | None = None) -> VectorIndex:
    return VectorIndex(tmp_path / "vectors", "current-model", embedder or DeterministicEmbedder())


def test_reindex_without_confirmation_preserves_current_vectors(tmp_path) -> None:
    database_path, _ = _database(tmp_path, [("ready-1", "ready")])
    index = _index(tmp_path)
    index.index_source(database_path, "ready-1")
    before = index.collection.get(include=[])["ids"]

    with pytest.raises(RetrievalError) as error:
        index.rebuild(database_path, confirmed=False)

    assert error.value.code == "reindex_confirmation_required"
    assert index.collection.get(include=[])["ids"] == before


def test_confirmed_reindex_rebuilds_all_ready_sources(tmp_path) -> None:
    database_path, _ = _database(
        tmp_path,
        [("ready-1", "ready"), ("ready-2", "ready"), ("failed-1", "failed")],
    )
    old_index = VectorIndex(tmp_path / "vectors", "old-model", DeterministicEmbedder())
    old_index.index_source(database_path, "ready-1")
    index = _index(tmp_path)

    chunk_count = index.rebuild(database_path, confirmed=True)
    stored = index.collection.get(include=["metadatas"])

    assert chunk_count == 2
    assert set(stored["ids"]) == {"ready-1:1:1", "ready-2:1:1"}
    assert {metadata["source_id"] for metadata in stored["metadatas"]} == {
        "ready-1",
        "ready-2",
    }
    assert index.collection.metadata["embedding_model"] == "current-model"


def test_failed_reindex_keeps_sqlite_records_and_original_uploads(tmp_path) -> None:
    database_path, uploads_dir = _database(tmp_path, [("ready-1", "ready")])
    upload_path = uploads_dir / "ready-1.json"
    index = _index(tmp_path, DeterministicEmbedder(fail=True))

    with pytest.raises(EmbeddingError):
        index.rebuild(database_path, confirmed=True)

    with sqlite3.connect(database_path) as connection:
        source_count = connection.execute("SELECT COUNT(*) FROM sources").fetchone()[0]
        record_count = connection.execute("SELECT COUNT(*) FROM support_records").fetchone()[0]
    assert source_count == 1
    assert record_count == 1
    assert upload_path.read_text(encoding="utf-8") == "original upload"
