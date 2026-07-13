"""Health check endpoint.

Reports basic liveness information about the running backend
process. Intentionally has no dependency on the database or any
external service in this milestone, so it can be used as a simple
container/orchestrator liveness probe.
"""

from datetime import datetime, timezone

from fastapi import APIRouter
from pydantic import BaseModel

from dash_backend import __version__
from dash_backend.core.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Response schema for the health check endpoint."""

    status: str
    service: str
    version: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check() -> HealthResponse:
    """Return service liveness status."""

    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.APP_NAME,
        version=__version__,
        environment=settings.ENVIRONMENT,
        timestamp=datetime.now(timezone.utc),
    )
