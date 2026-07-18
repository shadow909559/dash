"""Health check endpoint."""

from datetime import UTC, datetime

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dash_backend import __version__
from dash_backend.config import get_settings

router = APIRouter()


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = Field(examples=["ok"])
    service: str
    version: str
    environment: str
    timestamp: datetime


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Return service health status."""
    settings = get_settings()
    return HealthResponse(
        status="ok",
        service=settings.app_name,
        version=__version__,
        environment=settings.env,
        timestamp=datetime.now(UTC),
    )
