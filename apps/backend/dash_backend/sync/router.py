"""Sync API routes for desktop/mobile synchronization."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.config import get_settings
from dash_backend.db.session import AsyncSessionLocal
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


@router.get("/outbox/health")
async def outbox_health(
    user_id: str = Depends(get_current_user_id),
) -> dict[str, Any]:
    """Supabase outbox health: queue counts, dead-letter detail, freshness.

    Makes sync failures visible instead of silent (decisions.md #46):
    pending (backlog incl. retry-scheduled), dead_letter total split into
    retryable (recovery budget remains) and exhausted (permanent), recent
    dead letters with their errors, and the last successful delivery.
    Read-only, DB-only — never touches the network.
    """
    from dash_backend.sync.outbox import (
        MAX_RECOVERY_ATTEMPTS,
        STATUS_DEAD_LETTER,
        STATUS_PENDING,
        STATUS_PROCESSING,
        SyncOutboxEvent,
    )

    enabled = get_settings().supabase_sync_enabled
    if not enabled:
        return {"state": "LOCAL_ONLY", "sync_enabled": False}

    now = datetime.now(UTC)
    async with AsyncSessionLocal() as session:
        rows = (
            await session.execute(
                select(SyncOutboxEvent.status, func.count()).group_by(
                    SyncOutboxEvent.status
                )
            )
        ).all()
        counts = {str(status): int(count) for status, count in rows}

        dead_total = counts.get(STATUS_DEAD_LETTER, 0)
        retryable = int(
            (await session.execute(
                select(func.count())
                .select_from(SyncOutboxEvent)
                .where(
                    SyncOutboxEvent.status == STATUS_DEAD_LETTER,
                    SyncOutboxEvent.recovery_count < MAX_RECOVERY_ATTEMPTS,
                )
            )).scalar()
            or 0
        )

        recent_rows = (
            await session.execute(
                select(SyncOutboxEvent)
                .where(SyncOutboxEvent.status == STATUS_DEAD_LETTER)
                .order_by(SyncOutboxEvent.updated_at.desc())
                .limit(5)
            )
        ).scalars().all()
        recent = [
            {
                "id": str(event.id),
                "record_type": event.record_type,
                "record_id": str(event.record_id),
                "operation": event.operation,
                "error": event.error,
                "attempt_count": event.attempt_count,
                "recovery_count": event.recovery_count,
                "last_attempt_at": (
                    event.last_attempt_at.isoformat() if event.last_attempt_at else None
                ),
            }
            for event in recent_rows
        ]

        last_success = await session.scalar(
            select(func.max(SyncOutboxEvent.completed_at)).where(
                SyncOutboxEvent.status == "completed"
            )
        )

    pending = counts.get(STATUS_PENDING, 0)
    processing = counts.get(STATUS_PROCESSING, 0)
    exhausted = dead_total - retryable
    if processing:
        state = "SYNCING"
    elif dead_total or pending:
        state = "DEGRADED"
    else:
        state = "HEALTHY"

    return {
        "state": state,
        "sync_enabled": True,
        "pending": pending,
        "processing": processing,
        "completed": counts.get("completed", 0),
        "dead_letter": dead_total,
        "dead_letter_retryable": retryable,
        "dead_letter_exhausted": exhausted,
        "recent_dead_letters": recent,
        "last_successful_sync": (
            last_success.astimezone(UTC).isoformat() if last_success else None
        ),
        "checked_at": now.isoformat(),
    }