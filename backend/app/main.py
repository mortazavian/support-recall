"""FastAPI application entry point."""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import Literal

from fastapi import FastAPI
from pydantic import BaseModel

from app.routes.sources import router as sources_router
from app.settings import Settings
from app.sources import recover_interrupted_sources
from app.storage import check_storage, initialize_storage


class HealthResponse(BaseModel):
    status: Literal["ok"]
    storage: Literal["ready"]
    service: Literal["supportrecall"]


def create_app(settings: Settings | None = None) -> FastAPI:
    """Build the API and initialize persistent storage during startup."""
    app_settings = settings or Settings.from_environment()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        initialize_storage(app_settings.database_path)
        app_settings.uploads_dir.mkdir(parents=True, exist_ok=True)
        recover_interrupted_sources(app_settings.database_path, app_settings.uploads_dir)
        yield

    application = FastAPI(title="SupportRecall API", lifespan=lifespan)
    application.state.settings = app_settings
    application.include_router(sources_router)

    @application.get("/api/health", response_model=HealthResponse)
    def health() -> HealthResponse:
        check_storage(app_settings.database_path)
        return HealthResponse(status="ok", storage="ready", service="supportrecall")

    return application


app = create_app()
