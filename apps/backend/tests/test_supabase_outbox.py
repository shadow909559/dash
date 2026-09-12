"""Regression tests for Phase 2's optional local-first Supabase outbox."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
import uuid

import pytest
from sqlalchemy import select

from dash_backend.executive.service import create_goal
from dash_backend.sync import outbox
from dash_backend.sync.outbox import (
    MAX_RECOVERY_ATTEMPTS,
    OPERATION_TOMBSTONE,
    OPERATION_UPSERT,
    STATUS_COMPLETED,
    STATUS_DEAD_LETTER,
    STATUS_PENDING,
    SyncOutboxEvent,
    claim_dead_letter_events,
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

    def update(self, payload: dict):
        self._update_payload = payload
        return self

    def match(self, filters: dict):
        self._match_filters = filters
        return self

    def execute(self) -> None:
        if hasattr(self, "_update_payload"):
            # PATCH semantics: only touch rows that already exist.
            target = self._state.get(self._match_filters["id"])
            if target is not None:
                target.update(self._update_payload)
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
async def test_tombstone_for_never_synced_record_is_a_noop(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    """A tombstone for a record the cloud has never seen must NOT insert a
    bare row (POSTgREST upsert would violate dash_tasks.project_id NOT NULL);
    PATCH semantics make it a harmless no-op."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    record_id = uuid.uuid4()
    await enqueue_event(
        db_session, record_type="task", record_id=record_id, owner_id=uuid.uuid4(),
        operation=OPERATION_TOMBSTONE, payload={},
    )

    cloud: dict[str, dict] = {}  # cloud has never seen this task
    settings = SimpleNamespace(supabase_sync_enabled=True, supabase_sync_owner_id=str(uuid.uuid4()))
    service = SimpleNamespace(sync_configuration_error=lambda: None, get_sync_client=lambda: _FakeSupabaseClient(cloud))
    import dash_backend.sync.supabase_outbox_worker as worker_module

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_supabase_service", lambda: service)
    assert await SupabaseOutboxWorker().deliver_once() == 1
    assert cloud == {}  # nothing was inserted
    events = list((await db_session.execute(select(SyncOutboxEvent))).scalars())
    assert all(event.status == STATUS_COMPLETED for event in events)


@pytest.mark.asyncio
async def test_delivery_strips_columns_missing_from_cloud_schema(db_session, monkeypatch: pytest.MonkeyPatch) -> None:
    """Local payloads carry fields the cloud tables don't have (priority,
    deadline, depends_on); PostgREST rejects unknown columns with HTTP 400,
    so delivery must strip them before upserting."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    record_id = uuid.uuid4()
    await enqueue_event(
        db_session, record_type="task", record_id=record_id, owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT,
        payload={"project_id": str(uuid.uuid4()), "title": "t", "priority": 2, "deadline": "2026-01-01T00:00:00", "depends_on": "[]"},
    )

    cloud: dict[str, dict] = {}
    settings = SimpleNamespace(supabase_sync_enabled=True, supabase_sync_owner_id=str(uuid.uuid4()))
    service = SimpleNamespace(sync_configuration_error=lambda: None, get_sync_client=lambda: _FakeSupabaseClient(cloud))
    import dash_backend.sync.supabase_outbox_worker as worker_module

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_supabase_service", lambda: service)
    assert await SupabaseOutboxWorker().deliver_once() == 1
    delivered = cloud[str(record_id)]
    assert delivered["title"] == "t"
    assert "priority" not in delivered
    assert "deadline" not in delivered
    assert "depends_on" not in delivered


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


class _FlakyTable(_FakeTable):
    """Upsert executor that raises for the first N calls (cloud outage),
    then behaves like the normal fake table."""

    def __init__(self, state: dict[str, dict], fail_first: list[bool]) -> None:
        super().__init__(state)
        self._fail_first = fail_first

    def execute(self) -> None:
        if getattr(self, "_update_payload", None) is not None:
            return super().execute()  # tombstone path never fails here
        if self._fail_first:
            self._fail_first.pop()
            raise RuntimeError("supabase unreachable")
        return super().execute()


class _FlakyClient(_FakeSupabaseClient):
    def __init__(self, state: dict[str, dict], fail_first: list[bool]) -> None:
        super().__init__(state)
        self._fail_first = fail_first

    def table(self, name: str) -> _FlakyTable:
        assert name in {"dash_projects", "dash_tasks"}
        return _FlakyTable(self._state, self._fail_first)


def _wire_worker(monkeypatch: pytest.MonkeyPatch, db_session, settings, service) -> None:
    import dash_backend.sync.supabase_outbox_worker as worker_module

    monkeypatch.setattr(worker_module, "AsyncSessionLocal", lambda: db_session)
    monkeypatch.setattr(worker_module, "get_settings", lambda: settings)
    monkeypatch.setattr(worker_module, "get_supabase_service", lambda: service)


@pytest.mark.asyncio
async def test_dead_letter_is_recovered_hourly_with_fresh_attempt_budget(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A dead-lettered event is re-armed to pending no sooner than one hour
    later, with attempt_count reset so it gets a full retry budget again."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    event = await enqueue_event(
        db_session, record_type="project", record_id=uuid.uuid4(), owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT, payload={"name": "recover me"},
    )
    assert event is not None
    for _ in range(4):
        await fail_event(db_session, event, "network unavailable")
    assert event.status == STATUS_PENDING
    await fail_event(db_session, event, "network unavailable")
    assert event.status == STATUS_DEAD_LETTER
    assert event.recovery_count == 0
    # Hourly gate: scheduled ~1h out, so an immediate claim finds nothing.
    assert event.next_retry_at is not None
    assert event.next_retry_at > datetime.now(UTC) + timedelta(minutes=59)
    assert await claim_dead_letter_events(db_session) == []

    # One hour passes: the event becomes due and is re-armed.
    event.next_retry_at = datetime.now(UTC) - timedelta(minutes=1)
    await db_session.commit()
    requeued = await claim_dead_letter_events(db_session)
    assert len(requeued) == 1
    assert requeued[0].id == event.id
    assert event.status == STATUS_PENDING
    assert event.recovery_count == 1
    assert event.attempt_count == 0  # fresh budget


@pytest.mark.asyncio
async def test_dead_letter_recovery_budget_exhausts_permanently(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """After MAX_RECOVERY_ATTEMPTS recoveries the event is never re-armed
    again — it stays dead-lettered for manual inspection."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    event = await enqueue_event(
        db_session, record_type="project", record_id=uuid.uuid4(), owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT, payload={"name": "hopeless"},
    )
    assert event is not None
    for _ in range(5):
        await fail_event(db_session, event, "still broken")
    assert event.status == STATUS_DEAD_LETTER

    event.recovery_count = MAX_RECOVERY_ATTEMPTS  # budget already spent
    event.next_retry_at = datetime.now(UTC) - timedelta(hours=2)
    await db_session.commit()
    assert await claim_dead_letter_events(db_session) == []
    await db_session.refresh(event)
    assert event.status == STATUS_DEAD_LETTER
    assert event.recovery_count == MAX_RECOVERY_ATTEMPTS


async def _fetch_event(session, event_id: uuid.UUID) -> SyncOutboxEvent:
    """Re-fetch the event by id. Needed because deliver_once's
    `async with AsyncSessionLocal()` closes the shared session between
    passes, detaching previously returned instances."""
    result = await session.execute(select(SyncOutboxEvent).where(SyncOutboxEvent.id == event_id))
    return result.scalar_one()


@pytest.mark.asyncio
async def test_worker_recovers_dead_lettered_event_after_outage_heals(
    db_session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """End-to-end: an outage dead-letters the event, the worker re-arms it on
    the next pass, exhausts that budget while the cloud is still down (dead
    letter again, recovery_count=1), and delivers successfully once the
    cloud heals — proving the full failure → recovery → success path."""
    monkeypatch.setattr(outbox, "sync_is_enabled", lambda: True)
    # Collapse all retry delays to zero so the test runs without sleeps;
    # the hourly cadence itself is asserted in the claim-level tests above.
    monkeypatch.setattr(outbox, "DEAD_LETTER_RETRY_DELAY", timedelta(0))
    monkeypatch.setattr(outbox, "retry_at", lambda attempt_count: datetime.now(UTC))

    record_id = uuid.uuid4()
    event = await enqueue_event(
        db_session, record_type="task", record_id=record_id, owner_id=uuid.uuid4(),
        operation=OPERATION_UPSERT,
        payload={"project_id": str(uuid.uuid4()), "title": "survives outage"},
    )
    assert event is not None
    event_id = event.id

    cloud: dict[str, dict] = {}
    # Fail the first 10 delivery attempts (5 initial + 5 recovered budget).
    fail_first = [True] * 10
    settings = SimpleNamespace(supabase_sync_enabled=True, supabase_sync_owner_id=str(uuid.uuid4()))
    service = SimpleNamespace(
        sync_configuration_error=lambda: None,
        get_sync_client=lambda: _FlakyClient(cloud, fail_first),
    )
    _wire_worker(monkeypatch, db_session, settings, service)
    worker = SupabaseOutboxWorker()

    # Five failed passes → dead letter.
    for _ in range(5):
        assert await worker.deliver_once() == 0
    event = await _fetch_event(db_session, event_id)
    assert event.status == STATUS_DEAD_LETTER
    assert event.recovery_count == 0

    # Recovery pass: re-armed and re-failed within the same deliver_once.
    assert await worker.deliver_once() == 0
    event = await _fetch_event(db_session, event_id)
    assert event.status == STATUS_PENDING  # new budget, attempt 1 spent
    assert event.recovery_count == 1
    assert event.attempt_count == 1

    # Remaining budget burns down while the cloud is still unreachable.
    for _ in range(4):
        assert await worker.deliver_once() == 0
    event = await _fetch_event(db_session, event_id)
    assert event.status == STATUS_DEAD_LETTER
    assert event.recovery_count == 1
    assert fail_first == []  # 10 failures consumed

    # Cloud heals; the dead letter is re-armed once more and delivered.
    assert await worker.deliver_once() == 1
    event = await _fetch_event(db_session, event_id)
    assert event.status == STATUS_COMPLETED
    assert event.recovery_count == 2
    assert cloud[str(record_id)]["title"] == "survives outage"


def test_supabase_schema_has_owner_only_rls_policies() -> None:
    from pathlib import Path

    sql = (Path(__file__).parents[1] / "supabase" / "migrations" / "202608230001_dash_projects_tasks.sql").read_text()
    assert "enable row level security" in sql.lower()
    # SELECT, INSERT, UPDATE (USING + WITH CHECK), DELETE for each table.
    assert sql.lower().count("auth.uid()") == 10
    assert "to anon" not in sql.lower()
    assert "references auth.users(id)" in sql.lower()
