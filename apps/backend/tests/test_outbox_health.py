"""Tests for GET /sync/outbox/health (decisions.md #46).

The endpoint makes Supabase outbox failures visible instead of silent:
queue counts, dead-letter split (retryable vs recovery-exhausted), recent
dead letters with errors, and last successful delivery — DB-only, no
network. Events are enqueued through the app's own AsyncSessionLocal (the
conftest temp app-DB), because that is the database the endpoint reads —
the per-test db_session fixture is a different (in-memory) database.
"""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

from dash_backend.sync import outbox
from dash_backend.sync.outbox import (
    MAX_RECOVERY_ATTEMPTS,
    OPERATION_UPSERT,
    STATUS_DEAD_LETTER,
    SyncOutboxEvent,
    enqueue_event,
    fail_event,
)
from dash_backend.db.session import AsyncSessionLocal

URL = "/api/v1/sync/outbox/health"


def _patch_settings(monkeypatch: pytest.MonkeyPatch, *, sync_enabled: bool) -> None:
    import dash_backend.sync.router as router_module

    monkeypatch.setattr(
        router_module,
        "get_settings",
        lambda: SimpleNamespace(supabase_sync_enabled=sync_enabled),
    )


async def _dead_letter_event(monkeypatch: pytest.MonkeyPatch, *, recoveries: int = 0) -> SyncOutboxEvent:
    """Enqueue via the app DB and fail the event to dead letter."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    async with AsyncSessionLocal() as session:
        event = await enqueue_event(
            session, record_type="project", record_id=uuid.uuid4(),
            owner_id=uuid.uuid4(), operation=OPERATION_UPSERT, payload={"name": "x"},
        )
        assert event is not None
        for _ in range(5):
            await fail_event(session, event, "cloud unreachable")
        assert event.status == STATUS_DEAD_LETTER
        event.recovery_count = recoveries
        await session.commit()
        return event


@pytest.mark.asyncio
async def test_outbox_health_disabled_is_local_only(client, monkeypatch):
    _patch_settings(monkeypatch, sync_enabled=False)
    resp = await client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"state": "LOCAL_ONLY", "sync_enabled": False}


@pytest.mark.asyncio
async def test_outbox_health_healthy_when_queue_empty(client, monkeypatch):
    _patch_settings(monkeypatch, sync_enabled=True)
    resp = await client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "HEALTHY"
    assert body["sync_enabled"] is True
    assert body["pending"] == 0
    assert body["dead_letter"] == 0
    assert body["dead_letter_retryable"] == 0
    assert body["dead_letter_exhausted"] == 0
    assert body["recent_dead_letters"] == []
    assert body["last_successful_sync"] is None
    assert body["checked_at"]


@pytest.mark.asyncio
async def test_outbox_health_counts_pending_and_dead_letters(client, monkeypatch):
    _patch_settings(monkeypatch, sync_enabled=True)

    # Two pending events (retry-scheduled backlog).
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    async with AsyncSessionLocal() as session:
        for _ in range(2):
            await enqueue_event(
                session, record_type="task", record_id=uuid.uuid4(),
                owner_id=uuid.uuid4(), operation=OPERATION_UPSERT,
                payload={"project_id": str(uuid.uuid4()), "title": "t"},
            )
    # One dead letter with recovery budget remaining, one exhausted.
    await _dead_letter_event(monkeypatch, recoveries=0)
    await _dead_letter_event(monkeypatch, recoveries=MAX_RECOVERY_ATTEMPTS)

    resp = await client.get(URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["state"] == "DEGRADED"
    assert body["pending"] == 2
    assert body["dead_letter"] == 2
    assert body["dead_letter_retryable"] == 1
    assert body["dead_letter_exhausted"] == 1
    assert len(body["recent_dead_letters"]) == 2
    entry = body["recent_dead_letters"][0]
    assert set(entry) == {
        "id", "record_type", "record_id", "operation", "error",
        "attempt_count", "recovery_count", "last_attempt_at",
    }
    assert entry["error"] == "cloud unreachable"
    assert entry["attempt_count"] == 5
    assert entry["recovery_count"] in (0, MAX_RECOVERY_ATTEMPTS)


@pytest.mark.asyncio
async def test_outbox_health_requires_auth(app):
    """The endpoint must not answer without the device token."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get(URL)
    assert resp.status_code in (401, 403)
