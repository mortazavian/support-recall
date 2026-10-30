"""SQLite initialization and readiness checks."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

SCHEMA_VERSION = "2"


def initialize_storage(database_path: Path) -> None:
    """Create the application database and its initial schema marker."""
    database_path.parent.mkdir(parents=True, exist_ok=True)

    with closing(sqlite3.connect(database_path)) as connection, connection:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.execute(
            "CREATE TABLE IF NOT EXISTS app_meta ("
            "key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        version_row = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()
        version = version_row[0] if version_row else "1"
        connection.execute(
            "INSERT OR IGNORE INTO app_meta (key, value) VALUES (?, ?)",
            ("schema_version", version),
        )
        if version not in {"1", SCHEMA_VERSION}:
            raise RuntimeError(f"Unsupported SupportRecall database schema version: {version}")

        connection.execute(
            "CREATE TABLE IF NOT EXISTS sources ("
            "id TEXT PRIMARY KEY, original_filename TEXT NOT NULL, stored_name TEXT NOT NULL, "
            "format TEXT NOT NULL CHECK (format IN ('csv', 'json', 'text')), "
            "content_hash TEXT NOT NULL UNIQUE, mapping_json TEXT, "
            "status TEXT NOT NULL CHECK (status IN ('pending', 'processing', 'ready', 'failed')), "
            "record_count INTEGER NOT NULL DEFAULT 0, error_code TEXT, error_message TEXT, "
            "created_at TEXT NOT NULL, updated_at TEXT NOT NULL)"
        )
        connection.execute(
            "CREATE TABLE IF NOT EXISTS support_records ("
            "id TEXT PRIMARY KEY, source_id TEXT NOT NULL "
            "REFERENCES sources(id) ON DELETE CASCADE, "
            "position INTEGER NOT NULL, conversation_id TEXT, date TEXT, "
            "product TEXT, category TEXT, "
            "messages_json TEXT NOT NULL, UNIQUE(source_id, position))"
        )
        connection.execute(
            "CREATE INDEX IF NOT EXISTS support_records_source_position "
            "ON support_records(source_id, position)"
        )
        connection.execute(
            "UPDATE app_meta SET value = ? WHERE key = ?", (SCHEMA_VERSION, "schema_version")
        )


def check_storage(database_path: Path) -> None:
    """Raise if the initialized database is missing or cannot be queried."""
    with closing(sqlite3.connect(database_path, timeout=1)) as connection:
        schema_version = connection.execute(
            "SELECT value FROM app_meta WHERE key = ?", ("schema_version",)
        ).fetchone()

    if schema_version != (SCHEMA_VERSION,):
        raise RuntimeError("SupportRecall database schema is not initialized")
