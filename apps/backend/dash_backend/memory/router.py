"""FastAPI router for Phase 3 persistent memory.

Routes are already implemented in `dash_backend.api.routes.memories`.
To avoid duplicating endpoints (and keep changes minimal), this router module
provides the required package structure and mounts the existing router.

Public path is enforced by `dash_backend.api.router` as `/api/v1/memory`.
"""

from __future__ import annotations

from dash_backend.api.routes.memories import router as memories_router

router = memories_router

__all__ = ["router"]

