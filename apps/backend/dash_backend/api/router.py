"""Top-level API router."""

from fastapi import APIRouter

from dash_backend.api.routes.auth import router as auth_router
from dash_backend.api.routes.conversations import router as conversations_router
from dash_backend.api.routes.health import router as health_router
from dash_backend.api.routes.memories import router as memories_router
from dash_backend.api.routes.websocket import router as websocket_router
from dash_backend.api.routes.projects import router as projects_router
from dash_backend.api.routes.notifications import router as notifications_router
from dash_backend.api.routes.automation_rules import router as automation_rules_router
from dash_backend.rag.router import router as rag_router
from dash_backend.automation.router import router as automation_router
from dash_backend.personal import router as personal_router
from dash_backend.sync.router import router as sync_router
from dash_backend.api.routes.system_ws import router as system_ws_router
from dash_backend.api.routes.remote_desktop import router as remote_desktop_router
from dash_backend.api.routes.ai_os import router as ai_os_router
from dash_backend.api.routes.desktop_control import router as desktop_control_router
from dash_backend.api.routes.window_manager import router as window_manager_router
from dash_backend.api.routes.files_rest import router as files_rest_router


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
    prefix="/memory",
    tags=["memory"],
)

api_router.include_router(
    projects_router,
    tags=["projects"],
)

api_router.include_router(
    notifications_router,
    tags=["notifications"],
)

api_router.include_router(
    automation_rules_router,
    tags=["automation-rules"],
)

api_router.include_router(
    rag_router,
    prefix="/rag",
    tags=["rag"],
)

api_router.include_router(
    automation_router,
    prefix="/automation",
    tags=["automation"],
)

# Personal assistant endpoints (single-user personal profile, tasks, reminders)
api_router.include_router(
    personal_router,
    prefix="/personal",
    tags=["personal"],
)

api_router.include_router(
    websocket_router,
    tags=["websocket"],
)

api_router.include_router(
    sync_router,
    tags=["sync"],
)

api_router.include_router(
    system_ws_router,
    tags=["system"],
)

api_router.include_router(
    remote_desktop_router,
    tags=["remote-desktop"],
)

api_router.include_router(
    ai_os_router,
    tags=["ai-os"],
)

api_router.include_router(
    desktop_control_router,
    tags=["desktop"],
)

api_router.include_router(
    window_manager_router,
    tags=["windows"],
)

api_router.include_router(
    files_rest_router,
    tags=["files"],
)
