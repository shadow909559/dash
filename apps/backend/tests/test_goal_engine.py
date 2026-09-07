"""Tests for the DASH Goal Engine (spec Part 6 / 38).

Covers structured goals (priority/deadline), task dependencies with gated
completion, goal progress + auto-completion, deadline queries, REST
endpoints (self-cleaning against the shared dev DB), and the integration of
deadlines into context / briefing / proactive signals.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from dash_backend.context.engine import EnvironmentContext
from dash_backend.context.collectors import collect_activity_context
from dash_backend.executive import service as exec_service
from dash_backend.executive.models import Goal, ExecutiveTask
from dash_backend.proactive.briefing import format_briefing
from dash_backend.proactive.signals import detect_signals

NOW = datetime.now(timezone.utc)


def _due(days: float) -> datetime:
    return NOW + timedelta(days=days)


# ── Service: goals ──────────────────────────────────────────────


async def test_create_goal_with_planning_fields(db_session, test_user):
    goal = await exec_service.create_goal(
        db_session, test_user.id, "Ship DASH 2.0", "Release the OS", priority=1, deadline=_due(3)
    )
    assert goal.priority == 1
    assert goal.deadline is not None
    assert goal.status == "pending"


async def test_update_goal_fields(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Plan launch")
    goal = await exec_service.update_goal(db_session, goal, {"status": "completed", "priority": 2, "deadline": _due(1)})
    assert goal.status == "completed"
    assert goal.completed_at is not None
    assert goal.priority == 2


async def test_delete_goal_removes_tasks(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Delete me")
    t1 = await exec_service.create_task(db_session, goal, "subtask a")
    t2 = await exec_service.create_task(db_session, goal, "subtask b")
    await exec_service.delete_goal(db_session, goal)
    assert await db_session.get(Goal, goal.id) is None
    assert await db_session.get(ExecutiveTask, t1.id) is None
    assert await db_session.get(ExecutiveTask, t2.id) is None


async def test_goal_progress_counts_completed(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Progress goal")
    await exec_service.create_task(db_session, goal, "a")
    b = await exec_service.create_task(db_session, goal, "b")
    await exec_service.complete_task(db_session, b)
    progress = await exec_service.goal_progress(db_session, goal)
    assert progress == {"total_tasks": 2, "completed_tasks": 1, "percent": 50}


# ── Service: task dependencies ──────────────────────────────────


async def test_complete_task_blocked_by_open_dependency(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Deps")
    dep = await exec_service.create_task(db_session, goal, "prereq")
    task = await exec_service.create_task(db_session, goal, "depends", depends_on=[str(dep.id)])
    result = await exec_service.complete_task(db_session, task)
    assert result["completed"] is False
    assert len(result["blocked_by"]) == 1
    assert result["blocked_by"][0]["id"] == str(dep.id)
    assert task.status == "pending"


async def test_complete_task_after_dependency_finishes(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Deps ok")
    dep = await exec_service.create_task(db_session, goal, "prereq")
    task = await exec_service.create_task(db_session, goal, "depends", depends_on=[str(dep.id)])
    await exec_service.complete_task(db_session, dep)
    result = await exec_service.complete_task(db_session, task)
    assert result["completed"] is True
    assert result["goal_completed"] is True  # both tasks done -> goal auto-completes
    assert goal.status == "completed"
    assert goal.completed_at is not None


async def test_goal_not_auto_completed_while_tasks_open(db_session, test_user):
    goal = await exec_service.create_goal(db_session, test_user.id, "Not done yet")
    t = await exec_service.create_task(db_session, goal, "only")
    open_task = await exec_service.create_task(db_session, goal, "still open")
    result = await exec_service.complete_task(db_session, t)
    assert result["completed"] is True
    assert result["goal_completed"] is False
    assert goal.status == "pending"


# ── Service: deadline queries ───────────────────────────────────


async def test_upcoming_deadlines_window(db_session, test_user):
    soon = await exec_service.create_goal(db_session, test_user.id, "Due soon", deadline=_due(1))
    later = await exec_service.create_goal(db_session, test_user.id, "Due much later", deadline=_due(60))
    task_goal = await exec_service.create_goal(db_session, test_user.id, "Has task deadline")
    await exec_service.create_task(db_session, task_goal, "urgent subtask", deadline=_due(2))
    items = await exec_service.upcoming_deadlines(db_session, test_user.id, days=7)
    kinds = {(it["type"], it["name"]) for it in items}
    assert ("goal", "Due soon") in kinds
    assert ("task", "urgent subtask") in kinds
    assert all(it["id"] != str(later.id) for it in items)  # outside window
    assert items == sorted(items, key=lambda it: it["deadline"])


async def test_overdue_goal_reported(db_session, test_user):
    await exec_service.create_goal(db_session, test_user.id, "Late goal", deadline=_due(-2))
    items = await exec_service.upcoming_deadlines(db_session, test_user.id, days=7)
    assert any(it["name"] == "Late goal" and it["overdue"] for it in items)


# ── Context / briefing / signal integration ─────────────────────


async def test_activity_collector_includes_deadlines(db_session, test_user):
    await exec_service.create_goal(db_session, test_user.id, "Context deadline", deadline=_due(1))
    ctx = await collect_activity_context(db_session, test_user.id)
    items = ctx.get("deadline_items") or []
    assert any(it["name"] == "Context deadline" and it["type"] == "goal" for it in items)


def test_deadline_signals_detected():
    snap = EnvironmentContext(
        activity={
            "deadline_items": [
                {"id": "aaaa", "type": "goal", "name": "Overdue goal", "deadline": (NOW - timedelta(hours=5)).isoformat(), "overdue": True},
                {"id": "bbbb", "type": "task", "name": "Urgent task", "deadline": (NOW + timedelta(hours=20)).isoformat(), "overdue": False},
            ]
        }
    )
    ids = {s.id for s in detect_signals(snap)}
    assert any(i.startswith("deadline_overdue_") for i in ids)
    assert any(i.startswith("deadline_approaching_") for i in ids)


def test_briefing_formats_deadlines():
    text = format_briefing(
        {
            "date": "Monday, 2026-09-07",
            "system": "ok",
            "project": "dash",
            "goals": ["- Ship [pending]"],
            "deadlines": ["- [goal] Ship DASH 2.0 due 2026-09-09 (OVERDUE)"],
            "attention": [],
        }
    )
    assert "Deadlines:" in text
    assert "Ship DASH 2.0 due 2026-09-09" in text


def test_briefing_omits_deadlines_when_absent():
    text = format_briefing({"date": "x", "system": "ok", "project": "p", "goals": [], "deadlines": [], "attention": []})
    assert "Deadlines:" not in text


# ── REST endpoints (self-cleaning against the shared dev DB) ────


async def test_goal_engine_endpoint_flow(client):
    # Create a goal with planning fields.
    r = await client.post(
        "/api/v1/executive/goals",
        json={"name": "API goal engine flow", "description": "temporary test", "priority": 1, "deadline": _due(3).isoformat()},
    )
    assert r.status_code == 201
    goal = r.json()
    assert goal["priority"] == 1
    assert goal["deadline"] is not None
    try:

        # Detail shows progress.
        r = await client.get(f"/api/v1/executive/goals/{goal['id']}")
        assert r.status_code == 200
        assert r.json()["progress"]["percent"] == 0

        # Add two tasks with a dependency.
        r = await client.post(f"/api/v1/executive/goals/{goal['id']}/tasks", json={"name": "first"})
        assert r.status_code == 201
        first = r.json()
        r = await client.post(
            f"/api/v1/executive/goals/{goal['id']}/tasks",
            json={"name": "second", "depends_on": [first["id"]], "deadline": _due(1).isoformat()},
        )
        assert r.status_code == 201
        second = r.json()

        # Completing the dependent task first is refused.
        r = await client.post(f"/api/v1/executive/tasks/{second['id']}/complete")
        assert r.status_code == 200
        assert r.json()["completed"] is False
        assert r.json()["blocked_by"]

        # Complete first, then second -> goal auto-completes.
        assert (await client.post(f"/api/v1/executive/tasks/{first['id']}/complete")).json()["completed"] is True
        r = await client.post(f"/api/v1/executive/tasks/{second['id']}/complete")
        body = r.json()
        assert body["completed"] is True
        assert body["goal_completed"] is True

        # Upcoming feed sees nothing now (goal completed), then cleanup.
        r = await client.get("/api/v1/executive/goals/upcoming?days=7")
        assert r.status_code == 200
        assert "items" in r.json()
    finally:
        # Always clean up, even when an assertion above failed mid-flow.
        await client.delete(f"/api/v1/executive/goals/{goal['id']}")


async def test_activity_collector_accepts_string_user_id(db_session, test_user):
    """Regression: routes hand the owner id as a string; PGUUID comparison must
    still work so activity context (goals/deadlines) is not silently empty."""
    await exec_service.create_goal(db_session, test_user.id, "Str-id goal", deadline=_due(1))
    ctx = await collect_activity_context(db_session, str(test_user.id))
    items = ctx.get("deadline_items") or []
    assert any(it["name"] == "Str-id goal" for it in items)
    assert ctx.get("goal_status_counts") is not None


async def test_goal_endpoints_require_auth(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        assert (await bare.get("/api/v1/executive/goals/upcoming")).status_code == 401
        assert (await bare.post("/api/v1/executive/goals", json={"name": "x"})).status_code == 401
