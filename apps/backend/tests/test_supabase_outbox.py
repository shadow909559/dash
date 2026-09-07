"""Regression tests for Phase 2's optional local-first Supabase outbox."""

from __future__ import annotations

from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

from dash_backend.executive.service import create_goal
from dash_backend.sync import outbox
from dash_backend.sync.outbox import (
    OPERATION_TOMBSTONE,
    OPERATION_UPSERT,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_PENDING,
    SyncOutboxEvent,
    enqueue_event,
    fail_event,
)
from dash_backend.sync.supabase_outbox_worker import SupabaseOutboxWorker


@pytest.mark.asyncio
async def test_sync_disabled_creates_no_outbox_event(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: False)
    result = await enqueue_event(
        db_session, record_type="project", record_id=uuid.uuid4(), owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT, payload={"name": "private"},
    )
    assert result is None
    assert list((await db_session.execute(select(SyncOutboxEvent))).scalars()) == []


@pytest.mark.asyncio
async def test_enabled_goal_write_creates_local_outbox_event(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    owner_id = uuid.uuid4()
    goal = await create_goal(db_session, owner_id, "Ship DASH", "Controlled cloud mirror")
    event = (await db_session.execute(select(SyncOutboxEvent))).scalar_one()
    assert event.record_type == "project"
    assert event.record_id == goal.id
    assert event.owner_id == owner_id
    assert event.payload["name"] == "Ship DASH"
    assert event.status == STATUS_PENDING


@pytest.mark.asyncio
async def test_failure_retries_then_dead_letters(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    event = await enqueue_event(
        db_session, record_type="project", record_id=uuid.uuid4(), owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT, payload={"name": "retry"},
    )
    assert event is not None
    await fail_event(db_session, event, "network unavailable")
    assert event.status == STATUS_PENDING
    assert event.next_retry_at is not None
    for _ in range(4):
        await fail_event(db_session, event, "network unavailable")
    assert event.status == STATUS_DEAD_LETTER
    assert event.error == "network unavailable"


class _FakeTable:
    def __init__(self, state: dict[str, dict]) -> None:
        self._state = state

    def upsert(self, payload: dict, *, on_conflict: str):
        assert on_conflict == "id"
        self._state[payload["id"]] = payload
        return self

    def execute(self) -> None:
        return None


class _FakeSupabaseClient:
    def __init__(self, state: dict[str, dict]) -> None:
        self._state = state

    def table(self, name: str) -> _FakeTable:
        assert name in {"dash_projects", "dash_tasks"}
        return _FakeTable(self._state)


@pytest.mark.asyncio
async def test_success_duplicate_and_tombstone_delivery_are_idempotent(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    owner_id, record_id = uuid.uuid4(), uuid.uuid4()
    for operation, payload in (
        (OPERATION_UPSERT, {"name": "same state"}),
        (OPERATION_UPSERT, {"name": "same state"}),
        (OPERATION_TOMBSTONE, {}),
    ):
        await enqueue_event(
            db_session, record_type="project", record_id=record_id, owner_id=owner_id,
            operation=operation, payload=payload,
        )

    cloud: dict[str, dict] = {}
    settings = SimpleNamespace(supabase_sync_enabled=True, supabase_sync_owner_id=str(uuid.uuid4()))
    service = SimpleNamespace(sync_configuration_error=lambda: None, get_sync_client=lambda: _FakeSupabaseClient(cloud))
    import dash_backend.sync.supabase_outbox_worker as worker_module

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_supabase_service", lambda: service)
    delivered = await SupabaseOutboxWorker().deliver_once()
    assert delivered == 3
    assert len(cloud) == 1
    assert cloud[str(record_id)]["deleted_at"] is not None
    events = list((await db_session.execute(select(SyncOutboxEvent))).scalars())
    assert all(event.status == STATUS_COMPLETED for event in events)


@pytest.mark.asyncio
async def test_unavailable_cloud_does_not_lose_local_event(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    event = await enqueue_event(
        db_session, record_type="task", record_id=uuid.uuid4(), owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT, payload={"project_id": str(uuid.uuid4()), "title": "local first"},
    )
    assert event is not None
    settings = SimpleNamespace(supabase_sync_enabled=True, supabase_sync_owner_id=str(uuid.uuid4()))
    unavailable = SimpleNamespace(sync_configuration_error=lambda: "service role missing")
    import dash_backend.sync.supabase_outbox_worker as worker_module

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_supabase_service", lambda: unavailable)
    assert await SupabaseOutboxWorker().deliver_once() == 0
    assert event.status == STATUS_PENDING
    assert event.attempt_count == 1


def test_supabase_schema_has_owner_only_rls_policies() -> None:
    from pathlib import Path

    sql = (Path(__file__).parents[1] / "supabase" / "migrations" / "202608230001_dash_projects_tasks.sql").read_text()
    assert "enable row level security" in sql.lower()
    # SELECT, INSERT, UPDATE (USING + WITH CHECK), DELETE for each table.
    assert sql.lower().count("auth.uid()") == 10
    assert "to anon" not in sql.lower()
    assert "references auth.users(id)" in sql.lower()
