"""Explicit command for rebuilding the persistent vector index."""

from __future__ import annotations

import argparse
import sys

from app.retrieval.embeddings import EmbeddingError, OllamaEmbedder
from app.retrieval.index import RetrievalError, VectorIndex
from app.settings import Settings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Rebuild SupportRecall's local vector index.")
    parser.add_argument("--confirm", action="store_true")
    arguments = parser.parse_args(argv)
    if not arguments.confirm:
        parser.error("برای بازسازی نمایه، گزینه --confirm را وارد کنید.")

    settings = Settings.from_environment()
    if not settings.database_path.is_file():
        print("پایگاه داده SupportRecall پیدا نشد.", file=sys.stderr)
        return 1

    index = VectorIndex(
        settings.vector_dir,
        settings.embedding_model,
        OllamaEmbedder(settings.ollama_base_url, settings.embedding_model),
    )
    try:
        chunk_count = index.rebuild(settings.database_path, confirmed=True)
    except (EmbeddingError, RetrievalError) as error:
        print(error.message, file=sys.stderr)
        return 1

    print(f"تعداد بخش‌های نمایه‌شده: {chunk_count}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
