"""FastAPI application entry point.

Creates and configures the DASH backend application with all routers,
middleware, lifespan events, and startup/shutdown hooks.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from dash_backend.config import get_settings
from dash_backend.logging_config import setup_logging, get_logger
from dash_backend.api.router import api_router
from dash_backend.automation.scheduler import get_scheduler

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager.

    Handles startup and shutdown events for the application.
    """
    settings = get_settings()
    setup_logging(settings.log_level)
    logger.info("Starting DASH backend (env=%s, debug=%s)", settings.env, settings.debug)

    # Eagerly register skills and tools on startup so they are available
    # for WebSocket handlers and background tasks.
    try:
        import dash_backend.skills.register as _skills_register  # noqa: F401
    except Exception:
        logger.exception("Failed to import skills registration")

    try:
        import dash_backend.tools.register_desktop as _tools_register  # noqa: F401
    except Exception:
        logger.exception("Failed to import tools registration")

    # Start automation scheduler
    try:
        scheduler = get_scheduler()
        scheduler.start()
    except Exception:
        logger.exception("Failed to start automation scheduler")

    yield

    # Shutdown
    try:
        scheduler = get_scheduler()
        await scheduler.stop()
    except Exception:
        logger.exception("Failed to stop automation scheduler")

    logger.info("DASH backend stopped")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    settings = get_settings()

    application = FastAPI(
        title=settings.app_name,
        version="0.1.0",
        debug=settings.debug,
        lifespan=lifespan,
    )

    if settings.is_development:
        application.docs_url = f"{settings.api_prefix}/docs"
        application.redoc_url = f"{settings.api_prefix}/redoc"
        application.openapi_url = f"{settings.api_prefix}/openapi.json"
    else:
        application.docs_url = None
        application.redoc_url = None
        application.openapi_url = None

    # CORS middleware
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Include API router
    application.include_router(api_router, prefix=settings.api_prefix)

    # Production sanity checks
    if settings.is_development is False:
        if settings.debug:
            logger.warning("Debug mode is enabled in non-development environment")
        if settings.jwt_secret_key is None or settings.jwt_secret_key == "changeme":
            logger.warning("JWT secret key is not configured securely")
        if "sqlite" in settings.database_url:
            logger.warning("Using SQLite database in non-development environment")

    return application


def run() -> None:
    """Run the application with uvicorn."""
    settings = get_settings()
    import uvicorn

    uvicorn.run(
        "dash_backend.main:app",
        host=settings.host,
        port=settings.port,
        reload=settings.is_development,
        log_level=settings.log_level.lower(),
    )


app = create_app()
