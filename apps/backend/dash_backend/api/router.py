"""Top-level API router."""

from fastapi import APIRouter

from dash_backend.api.routes.auth import router as auth_router
from dash_backend.api.routes.conversations import router as conversations_router
from dash_backend.api.routes.health import router as health_router
from dash_backend.api.routes.memories import router as memories_router
from dash_backend.api.routes.websocket import router as websocket_router


api_router = APIRouter()


api_router.include_router(
    auth_router,
    prefix="/auth",
    tags=["auth"],
)

api_router.include_router(
    health_router,
    tags=["health"],
)

api_router.include_router(
    conversations_router,
    tags=["conversations"],
)

api_router.include_router(
    memories_router,
    tags=["memories"],
)

api_router.include_router(
    websocket_router,
    tags=["websocket"],
)
