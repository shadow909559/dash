"""Sync API routes for desktop/mobile synchronization."""

from __future__ import annotations

import uuid
from typing import Any

from fastapi import APIRouter, Depends

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger
from dash_backend.sync.service import (
    SyncRequest,
    get_sync_service,
)

router = APIRouter(prefix="/sync", tags=["sync"])
logger = get_logger(__name__)


@router.post("/register")
async def register_sync_session(
    client_id: str,
    client_type: str = "mobile",
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Register a new sync session or recover an existing one."""
    service = get_sync_service()
    session_id = str(uuid.uuid4())
    result = await service.register_session(
        session_id=session_id,
        client_id=client_id,
        client_type=client_type,
        user_id=user_id,
    )
    return result


@router.post("/unregister")
async def unregister_sync_session(
    client_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """Unregister a sync session."""
    service = get_sync_service()
    await service.unregister_session(client_id)
    return {"status": "ok"}


@router.post("/heartbeat")
async def sync_heartbeat(
    client_id: str,
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """Record a heartbeat from a sync client."""
    service = get_sync_service()
    await service.record_heartbeat(client_id)
    return {"status": "ok"}


@router.post("/offline-queue")
async def enqueue_offline(
    client_id: str,
    message: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
) -> dict[str, str]:
    """Queue an offline message for a client."""
    service = get_sync_service()
    await service.enqueue_offline_message(client_id, message)
    return {"status": "queued"}


@router.get("/offline-messages")
async def get_offline_messages(
    client_id: str,
    user_id: str = Depends(get_current_user_id),
) -> list[dict[str, Any]]:
    """Get pending offline messages for a client."""
    service = get_sync_service()
    return await service.get_offline_messages(client_id)


@router.post("/sync")
async def perform_sync(
    request: dict[str, Any],
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Perform a full synchronization cycle."""
    service = get_sync_service()
    sync_request = SyncRequest(
        client_id=request.get("client_id", "unknown"),
        client_type=request.get("client_type", "mobile"),
        last_sync_timestamp=request.get("last_sync_timestamp"),
        conversations_since=request.get("conversations", []),
        memories_since=request.get("memories", []),
        message_ids_seen=set(request.get("message_ids_seen", [])),
        vector_clock=request.get("vector_clock", {}),
    )
    response = await service.perform_full_sync(user_id, sync_request.client_id, sync_request)
    return {
        "conversations": response.conversations,
        "memories": response.memories,
        "conflicts": response.conflicts,
        "server_timestamp": response.server_timestamp,
        "requires_full_sync": response.requires_full_sync,
    }


@router.get("/health")
async def sync_health(
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Get sync service health status."""
    service = get_sync_service()
    return await service.get_health()