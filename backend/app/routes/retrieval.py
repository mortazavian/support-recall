"""HTTP endpoint for inspecting source-linked retrieval results."""

from __future__ import annotations

import sqlite3
from contextlib import closing
from pathlib import Path

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app.retrieval.embeddings import EmbeddingError
from app.retrieval.index import RetrievalError
from app.settings import Settings

router = APIRouter(prefix="/api/retrieval", tags=["retrieval"])


class InspectRequest(BaseModel):
    query: str = Field(min_length=1)
    limit: int = Field(default=5, ge=1, le=10, strict=True)


@router.post("/inspect")
def inspect_retrieval(payload: InspectRequest, request: Request) -> dict[str, object]:
    query = payload.query.strip()
    if not query:
        raise _http_error(
            422,
            "blank_query",
            "عبارت جست‌وجو نمی‌تواند خالی باشد.",
        )

    try:
        matches = request.app.state.vector_index.search(query, limit=payload.limit)
    except (EmbeddingError, RetrievalError) as error:
        raise _http_error(503, error.code, error.message) from None

    filenames = _source_filenames(_settings(request).database_path, matches)
    results = []
    for match in matches:
        metadata = match["metadata"]
        source_id = str(metadata["source_id"])
        filename = filenames.get(source_id)
        if filename is None:
            continue
        results.append(
            {
                "source_id": source_id,
                "filename": filename,
                "record_id": metadata["record_id"],
                "conversation_id": metadata.get("conversation_id"),
                "position": metadata["position"],
                "product": metadata.get("product"),
                "category": metadata.get("category"),
                "excerpt": match["text"],
                "distance": match["distance"],
            }
        )
    return {"results": results}


def _source_filenames(
    database_path: Path, matches: list[dict[str, object]]
) -> dict[str, str]:
    source_ids = list({str(match["metadata"]["source_id"]) for match in matches})
    if not source_ids:
        return {}
    placeholders = ",".join("?" for _ in source_ids)
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            f"SELECT id, original_filename FROM sources "
            f"WHERE status = 'ready' AND id IN ({placeholders})",
            source_ids,
        ).fetchall()
    return {source_id: filename for source_id, filename in rows}


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})
