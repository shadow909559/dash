"""One-way delivery worker for the optional local Supabase outbox."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from dash_backend.config import get_settings
from dash_backend.db.session import AsyncSessionLocal
from dash_backend.logging_config import get_logger
from dash_backend.services.supabase import get_supabase_service
from dash_backend.sync.outbox import (
    MAX_RECOVERY_ATTEMPTS,
    OPERATION_TOMBSTONE,
    OPERATION_UPSERT,
    SyncOutboxEvent,
    claim_dead_letter_events,
    claim_pending_events,
    complete_event,
    fail_event,
)

logger = get_logger(__name__)

# Columns accepted by the cloud tables (supabase/migrations/202608230001_...).
# Local payloads may carry extra fields (priority, deadline, depends_on) that
# the cloud schema intentionally omits — PostgREST rejects unknown columns
# with HTTP 400, so delivery strips everything not listed here.
_TABLE_COLUMNS: dict[str, frozenset[str]] = {
    "dash_projects": frozenset({"id", "owner_id", "name", "description", "status", "created_at", "updated_at", "deleted_at"}),
    "dash_tasks": frozenset({"id", "owner_id", "project_id", "title", "description", "status", "created_at", "updated_at", "deleted_at"}),
}


class SupabaseOutboxWorker:
    """Delivers project/task events; it never reads cloud data back into DASH."""

    async def deliver_once(self, limit: int = 25) -> int:
        if not get_settings().supabase_sync_enabled:
            return 0
        async with AsyncSessionLocal() as session:
            # Automatic dead-letter recovery (decisions.md #43): re-arm due
            # dead letters (hourly via next_retry_at, max 3 recoveries) back
            # to pending; the claim below then treats them like any other
            # event. No separate timer needed — the hourly cadence is the
            # next_retry_at gate, not the 5s poll loop.
            requeued = await claim_dead_letter_events(session, limit)
            if requeued:
                logger.info(
                    "Re-armed %d dead-lettered outbox event(s) for recovery attempt %d",
                    len(requeued),
                    requeued[0].recovery_count,
                )
            events = await claim_pending_events(session, limit)
            delivered = 0
            for event in events:
                try:
                    await self._deliver(event)
                except ValueError as exc:
                    # Invalid payloads/operations are not transient; exhaust
                    # immediately AND spend the whole recovery budget — a
                    # deterministic error cannot be fixed by retrying later,
                    # so the event stays dead-lettered for manual inspection.
                    event.attempt_count = 4
                    event.recovery_count = MAX_RECOVERY_ATTEMPTS
                    await fail_event(session, event, str(exc))
                except Exception as exc:
                    logger.warning("Supabase outbox delivery failed event=%s error=%s", event.id, type(exc).__name__)
                    await fail_event(session, event, "Supabase delivery unavailable")
                else:
                    await complete_event(session, event)
                    delivered += 1
            return delivered

    async def run(self, poll_seconds: float = 5.0) -> None:
        """Run only while the explicit feature flag remains enabled."""
        # Verify the outbox table exists before entering the poll loop.
        # If the table is missing (e.g. migration was skipped) we wait
        # and retry at a slow cadence instead of spamming errors.
        backoff = poll_seconds
        while get_settings().supabase_sync_enabled:
            try:
                await self.deliver_once()
                backoff = poll_seconds  # reset on success
            except Exception as exc:
                msg = str(exc).lower()
                if "no such table" in msg or "table" in msg and "not found" in msg:
                    logger.warning(
                        "Outbox table not ready — retrying in %.0fs (run alembic upgrade head)",
                        backoff,
                    )
                else:
                    logger.exception("Optional Supabase outbox worker iteration failed")
            await asyncio.sleep(backoff)

    async def _deliver(self, event: SyncOutboxEvent) -> None:
        service = get_supabase_service()
        error = service.sync_configuration_error()
        if error:
            raise RuntimeError(error)
        owner_id = get_settings().supabase_sync_owner_id
        table = {"project": "dash_projects", "task": "dash_tasks"}.get(event.record_type)
        if table is None or event.operation not in {OPERATION_UPSERT, OPERATION_TOMBSTONE}:
            raise ValueError("Invalid sync outbox event")

        payload: dict[str, Any] = {
            key: value
            for key, value in {**event.payload, "id": str(event.record_id), "owner_id": owner_id}.items()
            if key in _TABLE_COLUMNS[table]
        }
        # Legacy events may predate the status column in local payloads; the
        # cloud columns are NOT NULL, so inject the local default.
        payload.setdefault("status", "pending")
        payload.setdefault("created_at", datetime.now(UTC).isoformat())
        payload.setdefault("updated_at", payload["created_at"])
        if event.operation == OPERATION_TOMBSTONE:
            # Soft-delete an existing cloud row via PATCH semantics. An upsert
            # would INSERT a bare row when the record was never synced,
            # violating NOT NULL constraints (e.g. dash_tasks.project_id).
            client = service.get_sync_client().table(table)
            await asyncio.to_thread(
                lambda: client
                .update({"deleted_at": datetime.now(UTC).isoformat()})
                .match({"id": str(event.record_id), "owner_id": owner_id})
                .execute()
            )
            return
        await asyncio.to_thread(
            lambda: service.get_sync_client().table(table).upsert(payload, on_conflict="id").execute()
        )


_worker: SupabaseOutboxWorker | None = None


def get_supabase_outbox_worker() -> SupabaseOutboxWorker:
    global _worker
    if _worker is None:
        _worker = SupabaseOutboxWorker()
    return _worker
