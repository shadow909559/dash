"""Top-level API router."""

from fastapi import APIRouter

from dash_backend.api.routes.auth import router as auth_router
from dash_backend.api.routes.health import router as health_router
from dash_backend.api.routes.websocket import router as websocket_router


api_router = APIRouter()


api_router.include_router(
    auth_router,
    tags=["auth"],
)

api_router.include_router(
    health_router,
    tags=["health"],
)

api_router.include_router(
    websocket_router,
    tags=["websocket"],
)