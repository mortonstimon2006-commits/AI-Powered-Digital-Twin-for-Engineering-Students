"""TwinPath AI API — application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.config import get_settings
from app.errors import install_error_handlers
from app.logging_config import configure_logging
from app.middleware import SecurityMiddleware

log = logging.getLogger("twinpath")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    for sub in ("uploads", "chroma", "outbox"):
        (settings.data_dir / sub).mkdir(parents=True, exist_ok=True)
    from app.ml.registry import registry

    registry.warm()  # loads + checksum-verifies the active model if one is registered
    log.info(
        "startup complete", extra={"ctx": {"env": settings.twinpath_env.value, "readiness_model": registry.active_available()}}
    )
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    docs = settings.api_docs_enabled
    app = FastAPI(
        title="TwinPath AI API",
        version="0.1.0",
        description="Career digital-twin platform: readiness modelling, skill gaps, simulation, roadmaps, local AI mentor.",
        docs_url="/api/docs" if docs else None,
        redoc_url="/api/redoc" if docs else None,
        openapi_url="/api/openapi.json" if docs else None,
        lifespan=lifespan,
        debug=False,  # never expose tracebacks, in any environment
    )
    install_error_handlers(app)
    app.add_middleware(SecurityMiddleware, max_body_bytes=settings.max_upload_bytes + 64 * 1024)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.origins,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
        allow_headers=["content-type", "x-csrf-token", "x-requested-with"],
        max_age=600,
    )
    app.include_router(api_router, prefix="/api/v1")
    return app


app = create_app()
