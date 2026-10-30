"""Central configuration for local backend paths."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True, slots=True)
class Settings:
    """Backend settings resolved from the process environment."""

    data_dir: Path
    uploads_path: Path | None = None
    ollama_base_url: str = "http://localhost:11434"
    embedding_model: str = "embeddinggemma:latest"
    vector_path: Path | None = None

    @classmethod
    def from_environment(cls) -> Settings:
        """Read the data directory, defaulting to ``<project-root>/data``."""
        configured_dir = os.environ.get("SUPPORTRECALL_DATA_DIR")
        if configured_dir:
            data_dir = Path(configured_dir).expanduser()
            if not data_dir.is_absolute():
                data_dir = PROJECT_ROOT / data_dir
        else:
            data_dir = PROJECT_ROOT / "data"

        configured_uploads_dir = os.environ.get("SUPPORTRECALL_UPLOADS_DIR")
        uploads_path = Path(configured_uploads_dir).expanduser() if configured_uploads_dir else None
        if uploads_path is not None and not uploads_path.is_absolute():
            uploads_path = PROJECT_ROOT / uploads_path

        configured_vector_dir = os.environ.get("SUPPORTRECALL_VECTOR_DIR")
        vector_path = Path(configured_vector_dir).expanduser() if configured_vector_dir else None
        if vector_path is not None and not vector_path.is_absolute():
            vector_path = PROJECT_ROOT / vector_path

        return cls(
            data_dir=data_dir.resolve(),
            uploads_path=uploads_path.resolve() if uploads_path is not None else None,
            ollama_base_url=os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434").rstrip("/"),
            embedding_model=os.environ.get(
                "SUPPORTRECALL_EMBEDDING_MODEL", "embeddinggemma:latest"
            ),
            vector_path=vector_path.resolve() if vector_path is not None else None,
        )

    @property
    def database_path(self) -> Path:
        """Return the persistent SQLite file path."""
        return self.data_dir / "supportrecall.sqlite3"

    @property
    def uploads_dir(self) -> Path:
        """Return the configured upload directory or the data-local default."""
        return self.uploads_path or self.data_dir / "uploads"

    @property
    def vector_dir(self) -> Path:
        """Return the configured vector directory or its data-local default."""
        return self.vector_path or self.data_dir / "vectors"
