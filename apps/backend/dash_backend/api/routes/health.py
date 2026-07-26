"""Health check endpoint."""

from datetime import UTC, datetime
import time

from fastapi import APIRouter
from pydantic import BaseModel, Field

from dash_backend import __version__
from dash_backend.config import get_settings

router = APIRouter()

# Server start time for uptime calculation
_start_time = time.time()


class HealthResponse(BaseModel):
    """Health check response payload."""

    status: str = Field(examples=["ok"])
    service: str
    version: str
    environment: str
    uptime: float
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
        uptime=time.time() - _start_time,
        timestamp=datetime.now(UTC),
    )
