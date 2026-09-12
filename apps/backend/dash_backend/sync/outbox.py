"""Durable, local-first outbox for optional one-way Supabase project sync."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import DateTime, Integer, JSON, String, Text, select
from sqlalchemy.dialects.postgresql import UUID as PGUUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped, mapped_column

from dash_backend.config import get_settings
from dash_backend.db.base import Base
from dash_backend.db.mixins import TimestampMixin, UUIDPrimaryKeyMixin
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

DOMAIN_PROJECTS = "projects"
OPERATION_UPSERT = "upsert"
OPERATION_TOMBSTONE = "tombstone"
STATUS_PENDING = "pending"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_DEAD_LETTER = "dead_letter"
MAX_ATTEMPTS = 5

# Dead-letter recovery (decisions.md #43): a dead-lettered event is not
# necessarily broken forever — Supabase outages and schema drift are often
# transient or fixed later. The worker re-arms dead letters hourly, up to
# MAX_RECOVERY_ATTEMPTS recoveries (each re-armed event gets a fresh
# attempt budget of MAX_ATTEMPTS), before giving up permanently.
MAX_RECOVERY_ATTEMPTS = 3
DEAD_LETTER_RETRY_DELAY = timedelta(hours=1)


class SyncOutboxEvent(Base, UUIDPrimaryKeyMixin, TimestampMixin):
    """A local event. It is never a source of truth for DASH domain data."""

    __tablename__ = "sync_outbox_events"

    domain: Mapped[str] = mapped_column(String(32), nullable=False, default=DOMAIN_PROJECTS)
    record_type: Mapped[str] = mapped_column(String(32), nullable=False)
    record_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    owner_id: Mapped[uuid.UUID] = mapped_column(PGUUID(as_uuid=True), nullable=False)
    operation: Mapped[str] = mapped_column(String(16), nullable=False)
    payload: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default=STATUS_PENDING)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    # How many times this event was re-armed from dead-letter back to
    # pending. Re-arm resets attempt_count; this counter is what bounds
    # total recovery lifetime.
    recovery_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    last_attempt_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    next_retry_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)


def sync_is_enabled() -> bool:
    return get_settings().supabase_sync_enabled


async def enqueue_event(
    session: AsyncSession,
    *,
    record_type: str,
    record_id: uuid.UUID,
    owner_id: uuid.UUID,
    operation: str,
    payload: dict[str, Any],
) -> SyncOutboxEvent | None:
    """Persist a safe sync event only when explicit opt-in is active.

    This intentionally has no network side effects. The caller already
    committed its local domain change, so an outbox error can never roll it
    back or make Supabase a prerequisite for local operation.
    """
    if not sync_is_enabled():
        return None
    event = SyncOutboxEvent(
        record_type=record_type,
        record_id=record_id,
        owner_id=owner_id,
        operation=operation,
        payload=payload,
    )
    session.add(event)
    try:
        await session.commit()
        await session.refresh(event)
        return event
    except Exception:
        await session.rollback()
        logger.exception("Failed to persist optional Supabase sync outbox event")
        return None


def retry_at(attempt_count: int) -> datetime:
    """Bound exponential retry; attempt 1 waits 2 seconds, max 5 minutes."""
    return datetime.now(UTC) + timedelta(seconds=min(2 ** max(attempt_count, 1), 300))


async def claim_pending_events(session: AsyncSession, limit: int = 25) -> list[SyncOutboxEvent]:
    now = datetime.now(UTC)
    query = (
        select(SyncOutboxEvent)
        .where(
            SyncOutboxEvent.status == STATUS_PENDING,
            (SyncOutboxEvent.next_retry_at.is_(None)) | (SyncOutboxEvent.next_retry_at <= now),
        )
        .order_by(SyncOutboxEvent.created_at.asc())
        .limit(limit)
    )
    events = list((await session.execute(query)).scalars().all())
    for event in events:
        event.status = STATUS_PROCESSING
        event.last_attempt_at = now
    if events:
        await session.commit()
    return events


async def claim_dead_letter_events(session: AsyncSession, limit: int = 25) -> list[SyncOutboxEvent]:
    """Re-arm due dead-lettered events that still have recovery budget.

    "Due" means next_retry_at has passed (the worker schedules dead letters
    hourly). Events that exhausted MAX_RECOVERY_ATTEMPTS recoveries stay
    dead-lettered permanently — surfaced for manual inspection via their
    error and recovery_count fields.
    """
    now = datetime.now(UTC)
    query = (
        select(SyncOutboxEvent)
        .where(
            SyncOutboxEvent.status == STATUS_DEAD_LETTER,
            SyncOutboxEvent.recovery_count < MAX_RECOVERY_ATTEMPTS,
            (SyncOutboxEvent.next_retry_at.is_(None)) | (SyncOutboxEvent.next_retry_at <= now),
        )
        .order_by(SyncOutboxEvent.created_at.asc())
        .limit(limit)
    )
    events = list((await session.execute(query)).scalars().all())
    for event in events:
        # Re-arm with a fresh attempt budget: the original 5 attempts were
        # spent against whatever condition dead-lettered it; conditions can
        # change (config fix, service recovery) between recoveries.
        event.recovery_count += 1
        event.attempt_count = 0
        event.status = STATUS_PENDING
        event.next_retry_at = now
    if events:
        await session.commit()
    return events


async def complete_event(session: AsyncSession, event: SyncOutboxEvent) -> None:
    event.status = STATUS_COMPLETED
    event.completed_at = datetime.now(UTC)
    event.error = None
    event.next_retry_at = None
    await session.commit()


async def fail_event(session: AsyncSession, event: SyncOutboxEvent, error: str) -> None:
    event.attempt_count += 1
    event.error = error[:512]
    if event.attempt_count >= MAX_ATTEMPTS:
        event.status = STATUS_DEAD_LETTER
        # Schedule automatic recovery instead of parking the event forever:
        # the worker re-checks hourly while recovery budget remains. For an
        # already-recovered event (recovery_count > 0), the NEXT retry is
        # still scheduled — claim_dead_letter_events re-arms when due.
        event.next_retry_at = datetime.now(UTC) + DEAD_LETTER_RETRY_DELAY
    else:
        event.status = STATUS_PENDING
        event.next_retry_at = retry_at(event.attempt_count)
    await session.commit()
