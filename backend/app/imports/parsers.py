"""Parse supported support-conversation formats into one ordered schema."""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Literal, Mapping

ImportFormat = Literal["csv", "json", "text"]
SpeakerRole = Literal["customer", "support"]
MAX_CSV_FIELD_CHARS = 5 * 1024 * 1024
_INVALID_CSV_MESSAGE = "ساختار CSV معتبر نیست؛ نقل‌قول‌ها و جداکننده‌ها را بررسی کنید."
csv.field_size_limit(MAX_CSV_FIELD_CHARS)


@dataclass(frozen=True, slots=True)
class CsvColumnMapping:
    """Selected CSV headers for required and optional conversation fields."""

    question: str
    answer: str
    conversation_id: str | None = None
    date: str | None = None
    product: str | None = None
    category: str | None = None


@dataclass(frozen=True, slots=True)
class Message:
    """One ordered utterance in a support conversation."""

    role: SpeakerRole
    content: str


@dataclass(frozen=True, slots=True)
class Conversation:
    """Normalized conversation data shared by CSV, JSON, and text imports."""

    conversation_id: str | None
    date: str | None
    product: str | None
    category: str | None
    messages: tuple[Message, ...]


@dataclass(frozen=True, slots=True)
class ParsedImport:
    """Parsed file metadata and its normalized conversations."""

    format: ImportFormat
    columns: tuple[str, ...]
    records: tuple[Conversation, ...]


class ImportParseError(ValueError):
    """An actionable import validation error with a stable API code."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_import(
    filename: str,
    content: bytes,
    mapping: CsvColumnMapping | None = None,
) -> ParsedImport:
    """Parse a supported upload without guessing absent fields."""
    suffix = Path(filename).suffix.lower()
    format_name: ImportFormat
    if suffix == ".csv":
        format_name = "csv"
    elif suffix == ".json":
        format_name = "json"
    elif suffix == ".txt":
        format_name = "text"
    else:
        raise ImportParseError(
            "unsupported_format", "این نوع فایل پشتیبانی نمی‌شود؛ CSV، JSON یا TXT انتخاب کنید."
        )

    if not content or not content.strip():
        raise ImportParseError("empty_file", "فایل خالی است.")

    text = _decode_text(content, allow_windows_csv=format_name == "csv")
    if format_name == "csv":
        return _parse_csv(text, mapping)
    if mapping is not None:
        raise ImportParseError("mapping_not_supported", "نگاشت ستون فقط برای فایل CSV کاربرد دارد.")
    if format_name == "json":
        return _parse_json(text)
    return _parse_text(text)


def inspect_csv_columns(content: bytes) -> tuple[str, ...]:
    """Read a CSV header so the UI can request the required column mapping."""
    if not content or not content.strip():
        raise ImportParseError("empty_file", "فایل خالی است.")
    text = _decode_text(content, allow_windows_csv=True)
    try:
        reader = csv.reader(io.StringIO(text, newline=""), strict=True)
        return _validated_columns(next(reader, []))
    except csv.Error:
        raise ImportParseError("invalid_csv", _INVALID_CSV_MESSAGE) from None


def _decode_text(content: bytes, *, allow_windows_csv: bool) -> str:
    try:
        return content.decode("utf-8-sig")
    except UnicodeDecodeError:
        if allow_windows_csv:
            try:
                return content.decode("cp1256")
            except UnicodeDecodeError:
                pass
        raise ImportParseError(
            "invalid_encoding", "فایل خوانا نیست؛ آن را با رمزگذاری UTF-8 ذخیره کنید."
        ) from None


def _parse_csv(text: str, mapping: CsvColumnMapping | None) -> ParsedImport:
    try:
        return _parse_csv_rows(text, mapping)
    except csv.Error:
        raise ImportParseError("invalid_csv", _INVALID_CSV_MESSAGE) from None


def _parse_csv_rows(text: str, mapping: CsvColumnMapping | None) -> ParsedImport:
    if mapping is None:
        raise ImportParseError(
            "mapping_required", "برای فایل CSV ستون پرسش و پاسخ را انتخاب کنید."
        )

    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    columns = _validated_columns(reader.fieldnames or [])
    if not columns:
        raise ImportParseError("invalid_csv_headers", "سطر نخست CSV باید نام ستون‌ها را داشته باشد.")
    reader.fieldnames = list(columns)
    selected = {
        "question": mapping.question,
        "answer": mapping.answer,
        "conversation_id": mapping.conversation_id,
        "date": mapping.date,
        "product": mapping.product,
        "category": mapping.category,
    }
    if not mapping.question or not mapping.answer:
        raise ImportParseError(
            "mapping_required", "ستون پرسش و ستون پاسخ را برای فایل CSV انتخاب کنید."
        )
    missing = [header for header in selected.values() if header and header not in columns]
    if missing:
        raise ImportParseError(
            "invalid_mapping", "یکی از ستون‌های انتخاب‌شده در فایل CSV وجود ندارد."
        )

    records: list[Conversation] = []
    for row_number, row in enumerate(reader, start=2):
        if None in row:
            raise ImportParseError(
                "invalid_csv_row", f"تعداد خانه‌های سطر {row_number} با سطر عنوان هماهنگ نیست."
            )
        if not any(value and value.strip() for value in row.values() if isinstance(value, str)):
            continue
        question = _required_cell(row, mapping.question, row_number, "پرسش")
        answer = _required_cell(row, mapping.answer, row_number, "پاسخ")
        records.append(
            _conversation(
                {
                    "conversation_id": _optional_cell(row, mapping.conversation_id),
                    "date": _optional_cell(row, mapping.date),
                    "product": _optional_cell(row, mapping.product),
                    "category": _optional_cell(row, mapping.category),
                },
                (
                    Message(role="customer", content=question),
                    Message(role="support", content=answer),
                ),
                row_number,
            )
        )

    _require_records(records)
    return ParsedImport(format="csv", columns=columns, records=tuple(records))


def _validated_columns(raw_columns: list[str | None]) -> tuple[str, ...]:
    if not raw_columns or any(not column or not column.strip() for column in raw_columns):
        raise ImportParseError("invalid_csv_headers", "سطر نخست CSV باید نام ستون‌ها را داشته باشد.")
    columns = tuple(column.strip() for column in raw_columns if column is not None)
    if len(columns) != len(set(columns)):
        raise ImportParseError("duplicate_csv_headers", "نام ستون‌های CSV باید یکتا باشد.")
    return columns


def _parse_json(text: str) -> ParsedImport:
    try:
        payload = json.loads(text)
    except json.JSONDecodeError:
        raise ImportParseError("invalid_json", "ساختار JSON معتبر نیست.") from None
    if _contains_surrogate(payload):
        raise ImportParseError(
            "invalid_unicode",
            "متن JSON دارای نویسه یونیکد نامعتبر است؛ فایل را با UTF-8 معتبر ذخیره کنید.",
        )
    if not isinstance(payload, list) or not payload:
        raise ImportParseError("invalid_json_schema", "JSON باید فهرستی از گفت‌وگوها باشد.")

    records = tuple(_parse_json_record(item, index) for index, item in enumerate(payload, start=1))
    return ParsedImport(format="json", columns=(), records=records)


def _contains_surrogate(value: object) -> bool:
    if isinstance(value, str):
        return any(0xD800 <= ord(character) <= 0xDFFF for character in value)
    if isinstance(value, list):
        return any(_contains_surrogate(item) for item in value)
    if isinstance(value, dict):
        return any(
            _contains_surrogate(key) or _contains_surrogate(item)
            for key, item in value.items()
        )
    return False


def _parse_json_record(value: object, index: int) -> Conversation:
    if not isinstance(value, dict):
        raise _invalid_record(index)
    metadata = {
        key: _json_optional_string(value, key, index)
        for key in ("conversation_id", "date", "product", "category")
    }

    has_messages = "messages" in value
    has_pair = "question" in value or "answer" in value
    if has_messages == has_pair:
        raise _invalid_record(index)

    if has_messages:
        raw_messages = value["messages"]
        if not isinstance(raw_messages, list):
            raise _invalid_record(index)
        messages = tuple(_json_message(message, index) for message in raw_messages)
    else:
        question = _json_required_string(value, "question", index)
        answer = _json_required_string(value, "answer", index)
        messages = (
            Message(role="customer", content=question),
            Message(role="support", content=answer),
        )

    return _conversation(metadata, messages, index)


def _json_message(value: object, record_index: int) -> Message:
    if not isinstance(value, dict):
        raise _invalid_record(record_index)
    role = value.get("role")
    content = value.get("content")
    if not isinstance(role, str) or not isinstance(content, str) or not content.strip():
        raise _invalid_record(record_index)
    normalized_role = role.strip().lower()
    if normalized_role not in ("customer", "support"):
        raise _invalid_record(record_index)
    return Message(role=normalized_role, content=content.strip())  # type: ignore[arg-type]


def _parse_text(text: str) -> ParsedImport:
    blocks = [block for block in _split_text_blocks(text) if block.strip()]
    if not blocks:
        raise ImportParseError("empty_file", "فایل متن گفت‌وگویی برای ورود ندارد.")
    records = tuple(_parse_text_record(block, index) for index, block in enumerate(blocks, start=1))
    return ParsedImport(format="text", columns=(), records=records)


def _split_text_blocks(text: str) -> list[str]:
    blocks: list[str] = []
    current: list[str] = []
    for line in text.splitlines():
        if line.strip() == "---":
            blocks.append("\n".join(current))
            current = []
        else:
            current.append(line)
    blocks.append("\n".join(current))
    return blocks


def _parse_text_record(block: str, index: int) -> Conversation:
    metadata: dict[str, str | None] = {
        "conversation_id": None,
        "date": None,
        "product": None,
        "category": None,
    }
    metadata_prefixes = {
        "گفتگو": "conversation_id",
        "شناسه گفتگو": "conversation_id",
        "تاریخ": "date",
        "محصول": "product",
        "دسته‌بندی": "category",
        "دسته": "category",
    }
    role_prefixes: dict[str, SpeakerRole] = {
        "مشتری": "customer",
        "پشتیبانی": "support",
    }
    messages: list[Message] = []
    seen_metadata: set[str] = set()

    for line_number, line in enumerate(block.splitlines(), start=1):
        if not line.strip():
            continue
        prefix, separator, raw_value = line.partition(":")
        if not separator:
            raise ImportParseError(
                "invalid_text_line",
                f"گفت‌وگوی {index}، سطر {line_number}: هر خط باید با عنوان و دونقطه شروع شود.",
            )
        key = prefix.strip()
        value = raw_value.strip()
        if key in metadata_prefixes:
            field = metadata_prefixes[key]
            if field in seen_metadata or not value:
                raise ImportParseError(
                    "invalid_text_metadata", f"مقدار مشخصات «{key}» در گفت‌وگوی {index} نامعتبر است."
                )
            seen_metadata.add(field)
            metadata[field] = value
            continue
        if key in role_prefixes and value:
            messages.append(Message(role=role_prefixes[key], content=value))
            continue
        raise ImportParseError(
            "invalid_text_line",
            f"گفت‌وگوی {index}، سطر {line_number}: عنوان «{key}» شناخته‌شده نیست.",
        )

    return _conversation(metadata, tuple(messages), index)


def _conversation(
    metadata: Mapping[str, str | None], messages: tuple[Message, ...], index: int
) -> Conversation:
    if len(messages) < 2:
        raise _invalid_record(index)
    roles = {message.role for message in messages}
    if roles != {"customer", "support"}:
        raise _invalid_record(index)
    date_value = metadata.get("date")
    if date_value and not _is_iso_date(date_value):
        raise ImportParseError(
            "invalid_date", f"تاریخ گفت‌وگوی {index} باید با قالب ISO مانند 2026-10-28 باشد."
        )
    return Conversation(
        conversation_id=metadata.get("conversation_id"),
        date=date_value,
        product=metadata.get("product"),
        category=metadata.get("category"),
        messages=messages,
    )


def _is_iso_date(value: str) -> bool:
    try:
        date.fromisoformat(value)
        return True
    except ValueError:
        try:
            datetime.fromisoformat(value.replace("Z", "+00:00"))
            return True
        except ValueError:
            return False


def _required_cell(
    row: Mapping[str | None, str | list[str] | None], column: str, row_number: int, label: str
) -> str:
    value = row.get(column)
    if not isinstance(value, str) or not value.strip():
        raise ImportParseError(
            "missing_required_value", f"سطر {row_number}: خانه «{label}» نباید خالی باشد."
        )
    return value.strip()


def _optional_cell(
    row: Mapping[str | None, str | list[str] | None], column: str | None
) -> str | None:
    value = row.get(column) if column else None
    return value.strip() if isinstance(value, str) and value.strip() else None


def _json_required_string(value: dict[str, object], key: str, index: int) -> str:
    raw = value.get(key)
    if not isinstance(raw, str) or not raw.strip():
        raise _invalid_record(index)
    return raw.strip()


def _json_optional_string(value: dict[str, object], key: str, index: int) -> str | None:
    raw = value.get(key)
    if raw is None:
        return None
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    raise _invalid_record(index)


def _invalid_record(index: int) -> ImportParseError:
    return ImportParseError("invalid_record", f"ساختار گفت‌وگوی شماره {index} معتبر نیست.")


def _require_records(records: list[Conversation]) -> None:
    if not records:
        raise ImportParseError("no_records", "فایل گفت‌وگوی معتبری برای ورود ندارد.")
