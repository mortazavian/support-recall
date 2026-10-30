"""Persistent Chroma index for normalized support conversations."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import chromadb

from app.imports.parsers import Message
from app.retrieval.chunking import chunk_conversation
from app.retrieval.embeddings import REQUEST_BATCH_SIZE, EmbeddingError, OllamaEmbedder

COLLECTION_NAME = "support_recall"


class RetrievalError(RuntimeError):
    """A stable retrieval error with a Persian message for the API boundary."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class VectorIndex:
    """Persist source-linked chunks and search them with cosine distance."""

    def __init__(self, vector_dir: Path, embedding_model: str, embedder: OllamaEmbedder) -> None:
        vector_dir.mkdir(parents=True, exist_ok=True)
        self.embedding_model = embedding_model
        self.embedder = embedder
        self.client = chromadb.PersistentClient(path=str(vector_dir))
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "embedding_model": embedding_model},
        )

    def index_source(self, database_path: Path, source_id: str) -> int:
        """Replace one source's chunks from its ordered SQLite records."""
        records = self._source_records(database_path, source_id)
        self._check_model_profile()
        self.delete_source(source_id)

        chunks: list[tuple[str, dict[str, Any], str]] = []
        for record in records:
            messages = [Message(**message) for message in json.loads(record["messages_json"])]
            for chunk_number, text in enumerate(chunk_conversation(messages), start=1):
                metadata: dict[str, Any] = {
                    "source_id": source_id,
                    "record_id": record["id"],
                    "position": record["position"],
                }
                for field in ("conversation_id", "date", "product", "category"):
                    value = record[field]
                    if value is not None:
                        metadata[field] = value
                chunk_id = f"{source_id}:{record['position']}:{chunk_number}"
                chunks.append((chunk_id, metadata, text))

        try:
            for start in range(0, len(chunks), REQUEST_BATCH_SIZE):
                batch = chunks[start : start + REQUEST_BATCH_SIZE]
                texts = [chunk[2] for chunk in batch]
                vectors = self.embedder.embed(texts)
                if len(vectors) != len(texts):
                    raise EmbeddingError(
                        "embedding_count_mismatch",
                        "تعداد بردارهای Ollama با تعداد متن‌ها برابر نیست. دوباره تلاش کنید.",
                    )
                self._check_dimension(len(vectors[0]))
                self.collection.upsert(
                    ids=[chunk[0] for chunk in batch],
                    embeddings=vectors,
                    metadatas=[chunk[1] for chunk in batch],
                    documents=texts,
                )
        except Exception:
            try:
                self.delete_source(source_id)
            except RetrievalError:
                pass
            raise

        return len(chunks)

    def delete_source(self, source_id: str) -> None:
        """Remove every stored chunk belonging to a source."""
        try:
            self.collection.delete(where={"source_id": source_id})
        except Exception:
            raise RetrievalError(
                "vector_delete_failed",
                "حذف بردارهای منبع انجام نشد. فضای ذخیره‌سازی را بررسی و دوباره تلاش کنید.",
            ) from None

    def search(self, query: str, limit: int = 5) -> list[dict[str, object]]:
        """Return the nearest text chunks and their source metadata."""
        if limit < 1:
            raise ValueError("limit must be positive")
        if self.collection.count() == 0:
            return []
        self._check_model_profile()
        vectors = self.embedder.embed([query])
        if len(vectors) != 1:
            raise EmbeddingError(
                "embedding_count_mismatch",
                "تعداد بردارهای Ollama با تعداد متن‌ها برابر نیست. دوباره تلاش کنید.",
            )
        self._check_dimension(len(vectors[0]))
        response = self.collection.query(
            query_embeddings=vectors,
            n_results=min(limit, self.collection.count()),
            include=["documents", "metadatas", "distances"],
        )
        documents = response["documents"][0]
        metadatas = response["metadatas"][0]
        distances = response["distances"][0]
        return [
            {"text": text, "metadata": metadata, "distance": distance}
            for text, metadata, distance in zip(documents, metadatas, distances, strict=True)
        ]

    def rebuild(self, database_path: Path, *, confirmed: bool) -> int:
        """Replace the full vector collection from every ready SQLite source."""
        if not confirmed:
            raise RetrievalError(
                "reindex_confirmation_required",
                "برای بازسازی نمایه، دستور را با گزینه --confirm اجرا کنید.",
            )

        with sqlite3.connect(database_path) as connection:
            source_ids = [
                row[0]
                for row in connection.execute(
                    "SELECT id FROM sources WHERE status = 'ready' ORDER BY created_at, id"
                ).fetchall()
            ]

        self._reset_collection()
        try:
            chunk_count = 0
            for source_id in source_ids:
                chunk_count += self.index_source(database_path, source_id)
        except Exception:
            self._reset_collection()
            raise
        return chunk_count

    def _reset_collection(self) -> None:
        self.client.delete_collection(COLLECTION_NAME)
        self.collection = self.client.get_or_create_collection(
            name=COLLECTION_NAME,
            metadata={"hnsw:space": "cosine", "embedding_model": self.embedding_model},
        )

    def _source_records(self, database_path: Path, source_id: str) -> list[sqlite3.Row]:
        with sqlite3.connect(database_path) as connection:
            connection.row_factory = sqlite3.Row
            source = connection.execute(
                "SELECT id FROM sources WHERE id = ?", (source_id,)
            ).fetchone()
            if source is None:
                raise RetrievalError("source_not_found", "منبع موردنظر پیدا نشد.")
            return connection.execute(
                "SELECT id, position, conversation_id, date, product, category, messages_json "
                "FROM support_records WHERE source_id = ? ORDER BY position",
                (source_id,),
            ).fetchall()

    def _check_model_profile(self) -> None:
        metadata = dict(self.collection.metadata or {})
        stored_model = metadata.get("embedding_model")
        if stored_model != self.embedding_model and self.collection.count() > 0:
            raise self._reindex_required()
        if stored_model != self.embedding_model:
            metadata["embedding_model"] = self.embedding_model
            metadata.pop("embedding_dimension", None)
            self._save_profile(metadata)

    def _check_dimension(self, dimension: int) -> None:
        metadata = dict(self.collection.metadata or {})
        stored_dimension = metadata.get("embedding_dimension")
        if stored_dimension is not None and int(stored_dimension) != dimension:
            if self.collection.count() > 0:
                raise self._reindex_required()
        if stored_dimension is None or int(stored_dimension) != dimension:
            metadata["embedding_dimension"] = dimension
            metadata["embedding_model"] = self.embedding_model
            self._save_profile(metadata)

    def _save_profile(self, metadata: dict[str, Any]) -> None:
        metadata.pop("hnsw:space", None)
        self.collection.modify(metadata=metadata)

    @staticmethod
    def _reindex_required() -> RetrievalError:
        message = (
            "مدل بردارسازی تغییر کرده است. برای ساخت دوباره نمایه، "
            "دستور بازنمایه‌سازی را اجرا کنید."
        )
        return RetrievalError(
            "reindex_required",
            message,
        )
