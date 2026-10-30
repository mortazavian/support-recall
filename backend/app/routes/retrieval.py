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

    settings = _settings(request)
    ready_sources = _ready_sources(settings.database_path)
    if not ready_sources:
        return {"results": []}

    try:
        matches = request.app.state.vector_index.search(
            query, limit=payload.limit, source_ids=list(ready_sources)
        )
    except (EmbeddingError, RetrievalError) as error:
        raise _http_error(503, error.code, error.message) from None

    results = []
    for match in matches:
        metadata = match["metadata"]
        source_id = str(metadata["source_id"])
        filename = ready_sources.get(source_id)
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


def _ready_sources(database_path: Path) -> dict[str, str]:
    with closing(sqlite3.connect(database_path)) as connection:
        rows = connection.execute(
            "SELECT id, original_filename FROM sources "
            "WHERE status = 'ready'"
        ).fetchall()
    return {source_id: filename for source_id, filename in rows}


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _http_error(status_code: int, code: str, message: str) -> HTTPException:
    return HTTPException(status_code, detail={"code": code, "message": message})
