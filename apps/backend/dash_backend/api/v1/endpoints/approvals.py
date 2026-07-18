from __future__ import annotations

from typing import Any, Dict
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from dash_backend.tools.tool_manager import get_tool_manager
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)
router = APIRouter()


class ApprovalItem(BaseModel):
    confirmation_token: str
    summary: str


@router.get("/approvals", response_model=list[ApprovalItem])
async def list_approvals() -> list[ApprovalItem]:
    """List pending tool confirmations."""
    manager = get_tool_manager()
    executor = manager.executor
    pending = []
    try:
        for token, info in list(getattr(executor, "_pending_confirmations", {}).items()):
            summary = info.get("tool").name if info.get("tool") else "pending"
            pending.append(ApprovalItem(confirmation_token=token, summary=summary))
    except Exception:
        logger.exception("Failed to list pending approvals")
    return pending


@router.post("/approvals/{token}/confirm")
async def confirm_approval(token: str) -> Dict[str, Any]:
    """Confirm a pending tool execution and run it to completion."""
    manager = get_tool_manager()
    try:
        # collect streamed events and return final result
        final = None
        async for _event, data in manager.confirm_execution(token):
            final = data
        return {"status": "ok", "result": final}
    except Exception as exc:
        logger.exception("Failed to confirm approval %s", token)
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/approvals/{token}/reject")
async def reject_approval(token: str) -> Dict[str, Any]:
    manager = get_tool_manager()
    try:
        res = await manager.reject_execution(token)
        return {"status": "ok", "result": res}
    except Exception as exc:
        logger.exception("Failed to reject approval %s", token)
        raise HTTPException(status_code=400, detail=str(exc))
