"""DASH Context Engine REST API (Phase 1).

Exposes the live environment context so clients and DASH itself can answer:

- "Where am I / what device am I on?"        -> GET /context
- "What project am I working on?"            -> GET /context
- "What changed since yesterday?"            -> GET /context/what-changed
- "What should I tell the LLM about now?"    -> GET /context/brief

All routes require the local device token (same as every other internal API).
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.context.engine import get_context_engine
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/context", tags=["context"])


class SetProjectRequest(BaseModel):
    path: str = Field(..., description="Absolute path to the project to report as active")


@router.get("")
async def get_context(
    refresh: bool = Query(False, description="Bypass the short cache and recollect"),
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Full environment snapshot: device + project + recent activity."""
    engine = get_context_engine()
    snap = await engine.snapshot_async(session=session, user_id=user_id, refresh=refresh)
    return snap.as_dict()


@router.get("/brief")
async def get_context_brief(
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Compact text block ready for LLM prompt injection."""
    engine = get_context_engine()
    return {"block": await engine.context_block_async(session=session, user_id=user_id)}


@router.get("/what-changed")
async def get_what_changed(
    hours: int = Query(24, ge=1, le=24 * 30),
    session=Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Summary of environment changes over the last `hours`."""
    engine = get_context_engine()
    return await engine.what_changed_since(session=session, user_id=user_id, hours=hours)


@router.post("/project")
async def set_active_project(
    payload: SetProjectRequest,
) -> Dict[str, Any]:
    """Pin the project DASH reports as the active repository."""
    import os

    path = payload.path.strip().strip('"')
    if not os.path.isdir(path):
        raise HTTPException(status_code=400, detail=f"Not a directory: {path}")
    engine = get_context_engine()
    engine.set_project_dir(path)
    project = engine.project(refresh=True)
    if not project:
        raise HTTPException(status_code=400, detail=f"No git repository found at: {path}")
    return {"ok": True, "project": project}