"""SQLite initialization and readiness checks."""

from __future__ import annotations

import sqlite3
from pathlib import Path

SCHEMA_VERSION = "1"


def initialize_storage(database_path: Path) -> None:
    """Create the application database and its initial schema marker."""
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            "CREATE TABLE IF NOT EXISTS app_meta ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        connection.execute(
            "INSERT OR IGNORE INTO app_meta (key, value) VALUES (?, ?)",
            ("schema_version", SCHEMA_VERSION),
        )


def check_storage(database_path: Path) -> None:
    """Raise if the initialized database is missing or cannot be queried."""
    with sqlite3.connect(database_path, timeout=1) as connection:
        schema_version = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()

    if schema_version != (SCHEMA_VERSION,):
        raise RuntimeError("SupportRecall database schema is not initialized")
