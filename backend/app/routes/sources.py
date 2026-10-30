"""HTTP API for previewing, importing, inspecting, and deleting sources."""

from __future__ import annotations

import json

from fastapi import APIRouter, File, Form, HTTPException, Request, Response, UploadFile

from app.imports.parsers import CsvColumnMapping, ImportParseError
from app.settings import Settings
from app.sources import (
    MAX_UPLOAD_BYTES,
    SourceError,
    delete_source,
    get_source_detail,
    import_source,
    list_sources,
    preview_upload,
    retry_source,
)

router = APIRouter(prefix="/api/sources", tags=["sources"])
_MAPPING_FIELDS = {"question", "answer", "conversation_id", "date", "product", "category"}


@router.post("/preview")
async def preview(
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
) -> dict[str, object]:
    filename, content = await _read_upload(file)
    mapping = _mapping_from_form(mapping_json)
    try:
        return preview_upload(filename, content, mapping)
    except ImportParseError as error:
        raise _http_error(422, error.code, error.message) from None
    except SourceError as error:
        raise _http_error(error.status_code, error.code, error.message) from None


@router.post("/import")
async def import_file(
    request: Request,
    file: UploadFile = File(...),
    mapping_json: str | None = Form(default=None),
) -> dict[str, object]:
    filename, content = await _read_upload(file)
    mapping = _mapping_from_form(mapping_json)
    settings = _settings(request)
    try:
        return import_source(
            settings.database_path, settings.uploads_dir, filename, content, mapping
        )
    except ImportParseError as error:
        raise _http_error(422, error.code, error.message) from None
    except SourceError as error:
        raise _http_error(error.status_code, error.code, error.message) from None


@router.get("")
def sources(request: Request) -> list[dict[str, object]]:
    return list_sources(_settings(request).database_path)


@router.get("/{source_id}")
def source_detail(source_id: str, request: Request) -> dict[str, object]:
    try:
        return get_source_detail(_settings(request).database_path, source_id)
    except SourceError as error:
        raise _http_error(error.status_code, error.code, error.message) from None


@router.post("/{source_id}/retry")
def retry(source_id: str, request: Request) -> dict[str, object]:
    settings = _settings(request)
    try:
        return retry_source(settings.database_path, settings.uploads_dir, source_id)
    except ImportParseError as error:
        raise _http_error(422, error.code, error.message) from None
    except SourceError as error:
        raise _http_error(error.status_code, error.code, error.message) from None


@router.delete("/{source_id}", status_code=204)
def remove_source(source_id: str, request: Request) -> Response:
    settings = _settings(request)
    try:
        delete_source(settings.database_path, settings.uploads_dir, source_id)
    except SourceError as error:
        raise _http_error(error.status_code, error.code, error.message) from None
    return Response(status_code=204)


async def _read_upload(file: UploadFile) -> tuple[str, bytes]:
    if not file.filename:
        raise _http_error(422, "missing_filename", "نام فایل معتبر نیست.")
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    if len(content) > MAX_UPLOAD_BYTES:
        raise _http_error(413, "file_too_large", "حجم فایل نباید بیشتر از ۵ مگابایت باشد.")
    return file.filename, content


def _mapping_from_form(value: str | None) -> CsvColumnMapping | None:
    if value is None or not value.strip():
        return None
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        raise _http_error(422, "invalid_mapping", "نگاشت ستون‌های CSV معتبر نیست.") from None
    if not isinstance(payload, dict) or not set(payload) <= _MAPPING_FIELDS:
        raise _http_error(422, "invalid_mapping", "نگاشت ستون‌های CSV معتبر نیست.")
    if any(item is not None and not isinstance(item, str) for item in payload.values()):
        raise _http_error(422, "invalid_mapping", "نام ستون‌های انتخاب‌شده باید متن باشد.")
    return CsvColumnMapping(
        question=payload.get("question", ""),
        answer=payload.get("answer", ""),
        conversation_id=payload.get("conversation_id"),
        date=payload.get("date"),
        product=payload.get("product"),
        category=payload.get("category"),
    )


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(
        status_code=status_code,
        detail={"code": code, "message": message},
    )
