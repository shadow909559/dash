"""Regression pin: executive stale-task reclaimer vs naive datetime columns (#135).

``reset_stuck_tasks`` built a tz-aware UTC cutoff and compared it against the
naive TIMESTAMP WITHOUT TIME ZONE column ``last_heartbeat``; asyncpg raises
"can't subtract offset-naive and offset-aware datetimes" on every worker poll
against Postgres (surfaced by the packaged-backend boot probe). The pin asserts
the honest contract: the reclaimer binds a naive UTC cutoff, never raises, and
only requeues genuinely stale claims.
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone

import pytest

from dash_backend.executive import service as exec_service
from dash_backend.executive.models import ExecutiveTask, Goal


def _naive_now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _make_goal(session) -> Goal:
    goal = Goal(user_id=uuid.uuid4(), name="audit-goal", status="active")
    session.add(goal)
    await session.flush()
    return goal


@pytest.mark.asyncio
async def test_stale_claim_resets_to_pending(db_session):
    goal = await _make_goal(db_session)
    task = ExecutiveTask(
        goal_id=goal.id,
        name="stale",
        status="running",
        claimed_by=uuid.uuid4(),
        claimed_at=_naive_now() - timedelta(seconds=600),
        last_heartbeat=_naive_now() - timedelta(seconds=600),
    )
    db_session.add(task)
    await db_session.commit()

    reset = await exec_service.reset_stuck_tasks(db_session, stuck_seconds=60.0)
    assert reset >= 1
    await db_session.refresh(task)
    assert task.status == "pending"
    assert task.claimed_by is None
    assert task.last_heartbeat is None


@pytest.mark.asyncio
async def test_fresh_heartbeat_claim_survives(db_session):
    goal = await _make_goal(db_session)
    task = ExecutiveTask(
        goal_id=goal.id,
        name="fresh",
        status="running",
        claimed_by=uuid.uuid4(),
        claimed_at=_naive_now(),
        last_heartbeat=_naive_now(),
    )
    db_session.add(task)
    await db_session.commit()

    await exec_service.reset_stuck_tasks(db_session, stuck_seconds=60.0)
    await db_session.refresh(task)
    assert task.status == "running"
    assert task.claimed_by is not None


@pytest.mark.asyncio
async def test_null_heartbeat_claim_is_reset(db_session):
    goal = await _make_goal(db_session)
    task = ExecutiveTask(
        goal_id=goal.id,
        name="no-beat",
        status="running",
        claimed_by=uuid.uuid4(),
        last_heartbeat=None,
    )
    db_session.add(task)
    await db_session.commit()

    reset = await exec_service.reset_stuck_tasks(db_session, stuck_seconds=60.0)
    assert reset >= 1
    await db_session.refresh(task)
    assert task.status == "pending"
