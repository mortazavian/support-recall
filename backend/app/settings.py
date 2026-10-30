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

        return cls(data_dir=data_dir.resolve())

    @property
    def database_path(self) -> Path:
        """Return the persistent SQLite file path."""
        return self.data_dir / "supportrecall.sqlite3"
