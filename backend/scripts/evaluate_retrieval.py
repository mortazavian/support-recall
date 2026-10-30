"""Evaluate bilingual retrieval against the configured local Ollama model."""

from __future__ import annotations

import json
import sqlite3
import sys
from contextlib import closing
from datetime import UTC, datetime
from pathlib import Path
from tempfile import TemporaryDirectory

FIXTURE_PATH = Path(__file__).parents[1] / "tests" / "fixtures" / "retrieval_evaluation.json"
SOURCE_ID = "retrieval-evaluation"


def main() -> int:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.retrieval.embeddings import EmbeddingError, OllamaEmbedder
    from app.retrieval.index import RetrievalError, VectorIndex
    from app.settings import Settings
    from app.storage import initialize_storage

    fixture = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    settings = Settings.from_environment()
    now = datetime.now(UTC).isoformat(timespec="seconds")

    with TemporaryDirectory(prefix="supportrecall-evaluation-") as temporary_dir:
        root = Path(temporary_dir)
        database_path = root / "evaluation.sqlite3"
        initialize_storage(database_path)
        _save_conversations(database_path, fixture["conversations"], now)
        index = VectorIndex(
            root / "vectors",
            settings.embedding_model,
            OllamaEmbedder(settings.ollama_base_url, settings.embedding_model),
        )

        try:
            index.index_source(database_path, SOURCE_ID)
            hits = 0
            top_k = fixture["top_k"]
            for query in fixture["queries"]:
                results = index.search(query["text"], limit=top_k)
                ranked = [
                    f"{item['metadata']['conversation_id']} ({item['distance']:.3f})"
                    for item in results
                ]
                found = any(
                    item["metadata"]["conversation_id"] == query["expected_conversation_id"]
                    for item in results
                )
                hits += int(found)
                print(
                    f"{query['query_id']}: expected={query['expected_conversation_id']} "
                    f"top{top_k}={', '.join(ranked)} hit={found}"
                )
        except (EmbeddingError, RetrievalError) as error:
            print(error.message, file=sys.stderr)
            return 1
        finally:
            index.client.close()

        recall = hits / len(fixture["queries"])
        print(f"recall@{top_k}: {hits}/{len(fixture['queries'])} = {recall:.3f}")
        return 0 if hits == len(fixture["queries"]) else 1


def _save_conversations(database_path: Path, conversations: list[dict], now: str) -> None:
    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute(
            "INSERT INTO sources (id, original_filename, stored_name, format, content_hash, "
            "status, record_count, created_at, updated_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                SOURCE_ID,
                "synthetic-retrieval-evaluation.json",
                "synthetic-retrieval-evaluation.json",
                "json",
                "synthetic-retrieval-evaluation",
                "ready",
                len(conversations),
                now,
                now,
            ),
        )
        connection.executemany(
            "INSERT INTO support_records (id, source_id, position, conversation_id, "
            "messages_json) VALUES (?, ?, ?, ?, ?)",
            [
                (
                    f"{SOURCE_ID}:{position}",
                    SOURCE_ID,
                    position,
                    conversation["conversation_id"],
                    json.dumps(conversation["messages"], ensure_ascii=False),
                )
                for position, conversation in enumerate(conversations, start=1)
            ],
        )


if __name__ == "__main__":
    sys.exit(main())
