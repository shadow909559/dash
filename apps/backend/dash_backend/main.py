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

# Ensure runtime registration of skills and desktop tools occurs on startup
try:
    import dash_backend.skills.register  as _skills_register  # registers skills
    import dash_backend.tools.register_desktop as _desktop_tools_register  # registers desktop tools
except Exception:
    logger.exception("Failed to import skill/tool registration modules")


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Application lifespan hooks.

    Start the automation scheduler here so it runs for the lifetime of the
    application process. The scheduler is lightweight and in-process; for
    production use a dedicated worker or external scheduler.
    """
    from dash_backend.automation.scheduler import get_scheduler

    logger.info("Starting %s backend (env=%s)", settings.app_name, settings.env)

    # Start scheduler
    scheduler = get_scheduler()
    try:
        scheduler.start()
    except Exception:
        logger.exception("Failed to start automation scheduler")

    try:
        yield
    finally:
        # Stop scheduler on shutdown
        try:
            await scheduler.stop()
        except Exception:
            logger.exception("Failed to stop automation scheduler")
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

    # Production sanity checks
    try:
        if settings.env == "production" and settings.debug:
            logger.warning("Application running in production with debug=True — this is unsafe")
        if not settings.jwt_secret_key and settings.env == "production":
            logger.warning("JWT secret key not configured for production environment")
        if "******" in (settings.database_url or ""):
            logger.warning("Database URL appears to be a placeholder. Ensure DASH_DATABASE_URL is set in production.")
    except Exception:
        logger.exception("Failed to run startup configuration checks")

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
