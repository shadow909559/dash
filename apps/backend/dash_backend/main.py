"""FastAPI application entry point."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dash_backend.api.router import api_router
from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger, setup_logging

settings = get_settings()
setup_logging(settings.log_level)  # type: ignore[arg-type]
logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks."""
    logger.info("Starting %s backend (env=%s)", settings.app_name, settings.env)
    yield
    logger.info("Shutting down %s backend", settings.app_name)


def create_app() -> FastAPI:
    """Application factory."""
    app = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
        docs_url=f"{settings.api_prefix}/docs" if settings.is_development else None,
        redoc_url=f"{settings.api_prefix}/redoc" if settings.is_development else None,
        openapi_url=f"{settings.api_prefix}/openapi.json" if settings.is_development else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(api_router, prefix=settings.api_prefix)

    return app


app = create_app()


def run() -> None:
    """Run the application with Uvicorn."""
    uvicorn.run(
        "dash_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )


if __name__ == "__main__":
    run()
