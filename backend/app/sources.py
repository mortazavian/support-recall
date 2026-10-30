"""Persistent source import and lifecycle operations."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import sqlite3
import uuid
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Iterator

from app.imports.parsers import (
    Conversation,
    CsvColumnMapping,
    ImportParseError,
    ParsedImport,
    inspect_csv_columns,
    parse_import,
)
from app.retrieval.embeddings import EmbeddingError
from app.retrieval.index import RetrievalError, VectorIndex

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
MAX_RECORDS = 2_000
PREVIEW_LIMIT = 20
_logger = logging.getLogger(__name__)


class SourceError(ValueError):
    """An actionable source lifecycle error intended for the API boundary."""

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


@contextmanager
def _database(database_path: Path) -> Iterator[sqlite3.Connection]:
    connection = sqlite3.connect(database_path, timeout=10)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def preview_upload(
    filename: str,
    content: bytes,
    mapping: CsvColumnMapping | None = None,
) -> dict[str, object]:
    """Validate an upload and return a bounded preview without persistence."""
    safe_filename = _safe_filename(filename)
    _check_upload_size(content)
    if Path(safe_filename).suffix.lower() == ".csv" and mapping is None:
        columns = inspect_csv_columns(content)
        return {
            "format": "csv",
            "columns": list(columns),
            "needs_mapping": True,
            "record_count": None,
            "records": [],
        }

    parsed = parse_import(safe_filename, content, mapping)
    _check_record_count(parsed)
    return {
        "format": parsed.format,
        "columns": list(parsed.columns),
        "needs_mapping": False,
        "record_count": len(parsed.records),
        "records": [_conversation_payload(row) for row in parsed.records[:PREVIEW_LIMIT]],
    }


def import_source(
    database_path: Path,
    uploads_dir: Path,
    filename: str,
    content: bytes,
    mapping: CsvColumnMapping | None = None,
    *,
    vector_index: VectorIndex,
) -> dict[str, object]:
    """Persist an uploaded source and its normalized records idempotently."""
    safe_filename = _safe_filename(filename)
    _check_upload_size(content)
    parsed = parse_import(safe_filename, content, mapping)
    _check_record_count(parsed)
    content_hash = _content_hash(parsed)
    mapping_json = _mapping_json(mapping)

    existing = _source_by_hash(database_path, content_hash)
    if existing is not None:
        return {"source": _source_summary(existing), "duplicate": True}

    source_id = uuid.uuid4().hex
    stored_name = f"{source_id}{Path(safe_filename).suffix.lower()}"
    try:
        _write_upload(uploads_dir, stored_name, content)
    except OSError:
        raise SourceError(
            500,
            "upload_write_failed",
            "ذخیره فایل اصلی منبع انجام نشد؛ فضای ذخیره‌سازی را بررسی و دوباره تلاش کنید.",
        ) from None

    now = _now()
    try:
        with _database(database_path) as connection:
            connection.execute(
                "INSERT INTO sources (id, original_filename, stored_name, format, content_hash, "
                "mapping_json, status, record_count, created_at, updated_at) "
                "VALUES (?, ?, ?, ?, ?, ?, 'pending', 0, ?, ?)",
                (
                    source_id,
                    safe_filename,
                    stored_name,
                    parsed.format,
                    content_hash,
                    mapping_json,
                    now,
                    now,
                ),
            )
    except sqlite3.IntegrityError:
        _remove_upload(uploads_dir, stored_name)
        existing = _source_by_hash(database_path, content_hash)
        if existing is not None:
            return {"source": _source_summary(existing), "duplicate": True}
        raise
    except Exception:
        _remove_upload(uploads_dir, stored_name)
        raise

    try:
        _set_state(database_path, source_id, "processing")
        _persist_records(database_path, source_id, parsed.records)
        _index_source(database_path, source_id, vector_index)
    except SourceError:
        raise
    except Exception:
        _set_state(
            database_path,
            source_id,
            "failed",
            error_code="import_failed",
            error_message="هنگام ذخیره‌سازی منبع خطایی رخ داد. می‌توانید دوباره تلاش کنید.",
        )
        raise SourceError(
            500,
            "import_failed",
            "هنگام ذخیره‌سازی منبع خطایی رخ داد. می‌توانید دوباره تلاش کنید.",
        ) from None

    source = _source_by_id(database_path, source_id)
    assert source is not None
    return {"source": _source_summary(source), "duplicate": False}


def list_sources(database_path: Path) -> list[dict[str, object]]:
    """Return the newest imported sources first."""
    with _database(database_path) as connection:
        rows = connection.execute(
            "SELECT * FROM sources ORDER BY created_at DESC, id DESC"
        ).fetchall()
    return [_source_summary(row) for row in rows]


def get_source_detail(database_path: Path, source_id: str) -> dict[str, object]:
    """Return source metadata with the first page of ordered conversations."""
    source = _source_by_id(database_path, source_id)
    if source is None:
        raise SourceError(404, "source_not_found", "منبع موردنظر پیدا نشد.")
    with _database(database_path) as connection:
        rows = connection.execute(
            "SELECT position, conversation_id, date, product, category, messages_json "
            "FROM support_records WHERE source_id = ? ORDER BY position LIMIT ?",
            (source_id, PREVIEW_LIMIT),
        ).fetchall()
    records = [
        {
            "position": row["position"],
            "conversation_id": row["conversation_id"],
            "date": row["date"],
            "product": row["product"],
            "category": row["category"],
            "messages": json.loads(row["messages_json"]),
        }
        for row in rows
    ]
    return {"source": _source_summary(source), "records": records}


def retry_source(
    database_path: Path, uploads_dir: Path, source_id: str, vector_index: VectorIndex
) -> dict[str, object]:
    """Retry a failed source from its stored original bytes."""
    source = _source_by_id(database_path, source_id)
    if source is None:
        raise SourceError(404, "source_not_found", "منبع موردنظر پیدا نشد.")
    if source["status"] != "failed":
        raise SourceError(409, "source_not_failed", "فقط منبع ناموفق را می‌توانید دوباره وارد کنید.")

    stored_name = source["stored_name"]
    if Path(stored_name).name != stored_name:
        raise SourceError(
            409,
            "upload_missing",
            "فایل اصلی منبع پیدا نشد؛ فایل را دوباره بارگذاری کنید.",
        )
    upload_path = uploads_dir / stored_name
    try:
        content = upload_path.read_bytes()
    except OSError:
        raise SourceError(
            409,
            "upload_missing",
            "فایل اصلی منبع پیدا نشد؛ فایل را دوباره بارگذاری کنید.",
        ) from None

    mapping = _mapping_from_json(source["mapping_json"])
    parsed = parse_import(source["original_filename"], content, mapping)
    _check_record_count(parsed)
    if _content_hash(parsed) != source["content_hash"]:
        raise SourceError(
            409,
            "source_content_changed",
            "محتوای فایل ذخیره‌شده با منبع هماهنگ نیست.",
        )

    _set_state(database_path, source_id, "processing")
    try:
        _persist_records(database_path, source_id, parsed.records)
        _index_source(database_path, source_id, vector_index)
    except SourceError:
        raise
    except Exception:
        _set_state(
            database_path,
            source_id,
            "failed",
            error_code="import_failed",
            error_message="هنگام ذخیره‌سازی منبع خطایی رخ داد. می‌توانید دوباره تلاش کنید.",
        )
        raise SourceError(
            500,
            "import_failed",
            "هنگام ذخیره‌سازی منبع خطایی رخ داد. می‌توانید دوباره تلاش کنید.",
        ) from None

    retried = _source_by_id(database_path, source_id)
    assert retried is not None
    return {"source": _source_summary(retried), "duplicate": False}


def delete_source(
    database_path: Path, uploads_dir: Path, source_id: str, vector_index: VectorIndex
) -> None:
    """Delete a source, its foreign-keyed records, and its original upload."""
    source = _source_by_id(database_path, source_id)
    if source is None:
        raise SourceError(404, "source_not_found", "منبع موردنظر پیدا نشد.")
    try:
        vector_index.delete_source(source_id)
    except RetrievalError as error:
        raise SourceError(500, error.code, error.message) from None
    except Exception:
        raise SourceError(
            500,
            "vector_delete_failed",
            "حذف بردارهای منبع انجام نشد. فضای ذخیره‌سازی را بررسی کنید و دوباره تلاش کنید.",
        ) from None
    stored_name = source["stored_name"]
    if Path(stored_name).name == stored_name:
        try:
            (uploads_dir / stored_name).unlink(missing_ok=True)
        except OSError:
            raise SourceError(
                500,
                "upload_delete_failed",
                "حذف فایل اصلی منبع انجام نشد؛ دسترسی پوشه را بررسی و دوباره تلاش کنید.",
            ) from None
    with _database(database_path) as connection:
        connection.execute("DELETE FROM sources WHERE id = ?", (source_id,))


def recover_interrupted_sources(database_path: Path, uploads_dir: Path) -> None:
    """Mark imports interrupted by a restart as failed and retryable."""
    with _database(database_path) as connection:
        connection.execute(
            "UPDATE sources SET status = 'failed', error_code = 'import_interrupted', "
            "error_message = ?, updated_at = ? WHERE status IN ('pending', 'processing')",
            ("ورود منبع پیش از پایان برنامه متوقف شد. برای ادامه دوباره تلاش کنید.", _now()),
        )
        referenced_uploads = {
            row[0] for row in connection.execute("SELECT stored_name FROM sources").fetchall()
        }
    for path in uploads_dir.iterdir():
        if not path.is_file():
            continue
        temporary_upload = path.name.endswith(".tmp")
        generated_orphan = (
            path.name not in referenced_uploads
            and len(path.stem) == 32
            and all(character in "0123456789abcdef" for character in path.stem)
            and path.suffix.lower() in {".csv", ".json", ".txt"}
        )
        if temporary_upload or generated_orphan:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                _logger.warning("Could not remove interrupted upload artifact %s", path.name)


def mark_sources_missing_vectors(database_path: Path, vector_index: VectorIndex) -> None:
    """Mark ready sources without vectors as retryable after an upgrade or restart."""
    with _database(database_path) as connection:
        source_ids = [
            row[0]
            for row in connection.execute(
                "SELECT id FROM sources WHERE status = 'ready' ORDER BY id"
            ).fetchall()
        ]

    for source_id in source_ids:
        if not vector_index.has_source(source_id):
            _set_state(
                database_path,
                source_id,
                "failed",
                error_code="index_missing",
                error_message=(
                    "برای این منبع برداری ذخیره نشده است. "
                    "Ollama را اجرا و سپس منبع را دوباره وارد یا نمایه را بازسازی کنید."
                ),
            )


def _check_upload_size(content: bytes) -> None:
    if len(content) > MAX_UPLOAD_BYTES:
        raise SourceError(413, "file_too_large", "حجم فایل نباید بیشتر از ۵ مگابایت باشد.")


def _check_record_count(parsed: ParsedImport) -> None:
    if len(parsed.records) > MAX_RECORDS:
        raise SourceError(413, "too_many_records", "هر فایل می‌تواند حداکثر ۲۰۰۰ گفت‌وگو داشته باشد.")


def _safe_filename(filename: str) -> str:
    basename = filename.replace("\\", "/").rsplit("/", 1)[-1].strip()
    if not basename or basename in {".", ".."}:
        raise ImportParseError("missing_filename", "نام فایل معتبر نیست.")
    suffix = Path(basename).suffix.lower()
    if suffix in {".csv", ".json", ".txt"}:
        stem = basename[: -len(suffix)]
        return f"{stem[: 180 - len(suffix)]}{suffix}"
    return basename[:180]


def _conversation_payload(conversation: Conversation) -> dict[str, object]:
    return {
        "conversation_id": conversation.conversation_id,
        "date": conversation.date,
        "product": conversation.product,
        "category": conversation.category,
        "messages": [asdict(message) for message in conversation.messages],
    }


def _content_hash(parsed: ParsedImport) -> str:
    canonical = json.dumps(
        [_conversation_payload(record) for record in parsed.records],
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _mapping_json(mapping: CsvColumnMapping | None) -> str | None:
    if mapping is None:
        return None
    return json.dumps(asdict(mapping), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def _mapping_from_json(value: str | None) -> CsvColumnMapping | None:
    if value is None:
        return None
    mapping = json.loads(value)
    if not isinstance(mapping, dict):
        raise SourceError(409, "invalid_saved_mapping", "نگاشت ستون منبع ذخیره‌شده معتبر نیست.")
    return CsvColumnMapping(**mapping)


def _write_upload(uploads_dir: Path, stored_name: str, content: bytes) -> None:
    uploads_dir.mkdir(parents=True, exist_ok=True)
    temporary_path = uploads_dir / f"{stored_name}.tmp"
    final_path = uploads_dir / stored_name
    try:
        temporary_path.write_bytes(content)
        os.replace(temporary_path, final_path)
    finally:
        temporary_path.unlink(missing_ok=True)


def _remove_upload(uploads_dir: Path, stored_name: str) -> None:
    try:
        (uploads_dir / stored_name).unlink(missing_ok=True)
    except OSError:
        _logger.warning("Could not remove unreferenced upload %s", stored_name)


def _persist_records(
    database_path: Path, source_id: str, records: tuple[Conversation, ...]
) -> None:
    with _database(database_path) as connection:
        connection.execute("DELETE FROM support_records WHERE source_id = ?", (source_id,))
        connection.executemany(
            "INSERT INTO support_records (id, source_id, position, conversation_id, date, product, "
            "category, messages_json) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            [
                (
                    f"{source_id}:{position}",
                    source_id,
                    position,
                    record.conversation_id,
                    record.date,
                    record.product,
                    record.category,
                    json.dumps(
                        [asdict(message) for message in record.messages],
                        ensure_ascii=False,
                        separators=(",", ":"),
                    ),
                )
                for position, record in enumerate(records, start=1)
            ],
        )
        connection.execute(
            "UPDATE sources SET status = 'processing', record_count = ?, error_code = NULL, "
            "error_message = NULL, updated_at = ? WHERE id = ?",
            (len(records), _now(), source_id),
        )


def _index_source(database_path: Path, source_id: str, vector_index: VectorIndex) -> None:
    try:
        vector_index.index_source(database_path, source_id)
    except (EmbeddingError, RetrievalError) as error:
        _set_state(
            database_path,
            source_id,
            "failed",
            error_code=error.code,
            error_message=error.message,
        )
        raise SourceError(503, error.code, error.message) from None
    except Exception:
        message = "نمایه‌سازی منبع انجام نشد. Ollama و فضای ذخیره‌سازی را بررسی و دوباره تلاش کنید."
        _set_state(
            database_path,
            source_id,
            "failed",
            error_code="indexing_failed",
            error_message=message,
        )
        raise SourceError(503, "indexing_failed", message) from None

    _set_state(database_path, source_id, "ready")


def _set_state(
    database_path: Path,
    source_id: str,
    status: str,
    *,
    error_code: str | None = None,
    error_message: str | None = None,
) -> None:
    with _database(database_path) as connection:
        connection.execute(
            "UPDATE sources SET status = ?, error_code = ?, error_message = ?, updated_at = ? "
            "WHERE id = ?",
            (status, error_code, error_message, _now(), source_id),
        )


def _source_by_id(database_path: Path, source_id: str) -> sqlite3.Row | None:
    with _database(database_path) as connection:
        return connection.execute("SELECT * FROM sources WHERE id = ?", (source_id,)).fetchone()


def _source_by_hash(database_path: Path, content_hash: str) -> sqlite3.Row | None:
    with _database(database_path) as connection:
        return connection.execute(
            "SELECT * FROM sources WHERE content_hash = ?", (content_hash,)
        ).fetchone()


def _source_summary(source: sqlite3.Row) -> dict[str, object]:
    return {
        "id": source["id"],
        "filename": source["original_filename"],
        "format": source["format"],
        "status": source["status"],
        "record_count": source["record_count"],
        "error_code": source["error_code"],
        "error_message": source["error_message"],
        "retryable": source["status"] == "failed",
        "created_at": source["created_at"],
        "updated_at": source["updated_at"],
    }


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
