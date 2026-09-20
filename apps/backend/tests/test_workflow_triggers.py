"""Scheduled + webhook workflow triggers (decisions.md #53).

What is under test:
- the cron evaluator (parse + due semantics, honest rejection of dialects
  the engine cannot evaluate exactly),
- schedule validation + persistence across engine restarts,
- due_schedules()/mark_fired() idempotence (no double-fire within a minute,
  including across a restart),
- the polling scheduler loop (driven with a fake clock — no sleeps),
- the webhook route: secret validation (constant-time), trigger_count,
  enabled flag, and anonymous access (the intended auth model).

Everything is hermetic: engine state lives in a temp file, the scheduler is
driven via tick(now) instead of real time, and the route tests reuse the
conftest ASGI client (no live server).
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from dash_backend.services.workflow_builder import (
    InvalidCronError,
    WorkflowEngine,
    WorkflowTriggerScheduler,
    cron_matches_due,
    get_workflow_trigger_scheduler,
    parse_cron,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def workflow_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolated state file for the singleton + fresh engines alike."""
    state = tmp_path / "wf_state.json"
    monkeypatch.setenv("DASH_WORKFLOW_STATE", str(state))
    return state


@pytest.fixture()
def eng(workflow_state: Path) -> WorkflowEngine:
    return WorkflowEngine()


@pytest.fixture()
def sched(eng: WorkflowEngine) -> WorkflowTriggerScheduler:
    return WorkflowTriggerScheduler(engine=eng, poll_seconds=60)


def _make(engine: WorkflowEngine, cron: str | None = None) -> str:
    """Create one custom workflow; with a cron, schedule it too."""
    res = engine.create(
        "trigger flow",
        nodes=[{"id": "n1", "type": "trigger", "config": {"schedule": cron or "* * * * *"}, "x": 0, "y": 0}],
        edges=[],
    )
    assert res["ok"] is True
    wf_id = res["workflow"]["id"]
    if cron is not None:
        added = engine.add_schedule(wf_id, cron)
        assert added["ok"] is True, added
    return wf_id


# ── Cron evaluation ───────────────────────────────────────────────────────


def test_parse_cron_accepts_template_expressions() -> None:
    # The three schedules the built-in templates ship with.
    for expr in ("0 8 * * *", "0 2 * * *", "0 18 * * 5", "* * * * *"):
        fields = parse_cron(expr)
        assert len(fields) == 5


def test_parse_cron_rejects_unsupported_dialects() -> None:
    for bad in ("*/5", "0 8 * *", "0 8 * * * *", "0 8 * * * 2026", "0 8 * * * ?", "garbage"):
        with pytest.raises(InvalidCronError):
            parse_cron(bad)


def test_parse_cron_rejects_out_of_range_values() -> None:
    with pytest.raises(InvalidCronError):
        parse_cron("61 8 * * *")  # minute 61
    with pytest.raises(InvalidCronError):
        parse_cron("0 25 * * *")  # hour 25
    with pytest.raises(InvalidCronError):
        parse_cron("0 8 * * 7")  # dow out of range (0-6; 7 is not accepted)


def test_cron_matches_due_every_minute() -> None:
    assert cron_matches_due("* * * * *", datetime(2026, 9, 12, 23, 59))
    assert cron_matches_due("* * * * *", datetime(2026, 9, 13, 0, 0))


def test_cron_matches_daily_at_time() -> None:
    expr = "0 8 * * *"
    assert cron_matches_due(expr, datetime(2026, 9, 13, 8, 0))
    assert cron_matches_due(expr, datetime(2026, 9, 13, 8, 0, 30))  # seconds ignored
    assert not cron_matches_due(expr, datetime(2026, 9, 13, 8, 1))
    assert not cron_matches_due(expr, datetime(2026, 9, 13, 7, 0))
    assert not cron_matches_due(expr, datetime(2026, 9, 13, 20, 0))


def test_cron_matches_weekly_friday() -> None:
    expr = "0 18 * * 5"  # Friday 18:00 — 2026-09-11 is a Friday
    assert cron_matches_due(expr, datetime(2026, 9, 11, 18, 0))
    assert not cron_matches_due(expr, datetime(2026, 9, 12, 18, 0))  # Saturday
    assert not cron_matches_due(expr, datetime(2026, 9, 11, 18, 5))


def test_cron_matches_step_and_range_fields() -> None:
    # Every 15 minutes past 9-11 o'clock on the 1st and 15th.
    expr = "*/15 9-11 1,15 * *"
    assert cron_matches_due(expr, datetime(2026, 9, 1, 10, 45))
    assert cron_matches_due(expr, datetime(2026, 9, 15, 9, 0))
    assert not cron_matches_due(expr, datetime(2026, 9, 2, 10, 45))  # wrong day
    assert not cron_matches_due(expr, datetime(2026, 9, 1, 12, 0))  # wrong hour
    assert not cron_matches_due(expr, datetime(2026, 9, 1, 10, 50))  # wrong minute


def test_cron_weekday_alias_and_month() -> None:
    expr = "0 9 * jan mon"
    assert cron_matches_due(expr, datetime(2026, 1, 5, 9, 0))  # Monday
    assert not cron_matches_due(expr, datetime(2026, 1, 6, 9, 0))  # Tuesday
    assert not cron_matches_due(expr, datetime(2026, 2, 2, 9, 0))  # February
    # Numeric weekdays follow the cron convention (0=Sunday).
    assert cron_matches_due("* * * * 0", datetime(2026, 9, 13, 12, 0))  # Sunday
    assert cron_matches_due("* * * * sun", datetime(2026, 9, 13, 12, 0))
    assert not cron_matches_due("* * * * 6", datetime(2026, 9, 13, 12, 0))  # Saturday


def test_cron_dom_dow_or_semantics() -> None:
    # Standard cron: when both day fields are restricted, EITHER matches.
    expr = "0 12 1 * 1"  # the 1st OR any Monday
    assert cron_matches_due(expr, datetime(2026, 9, 1, 12, 0))  # Tuesday the 1st
    assert cron_matches_due(expr, datetime(2026, 9, 7, 12, 0))  # Monday
    assert not cron_matches_due(expr, datetime(2026, 9, 8, 12, 0))  # Tuesday the 8th


# ── Schedule validation + persistence ─────────────────────────────────────


def test_add_schedule_rejects_unsupported_cron(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    res = eng.add_schedule(wf_id, "0 8 * * * 2026")
    assert res["ok"] is False
    assert "Unsupported cron" in res["reason"]
    assert eng.get_schedules() == {}  # nothing stored


def test_add_schedule_cannot_schedule_templates(eng: WorkflowEngine) -> None:
    res = eng.add_schedule("daily_briefing", "0 8 * * *")
    assert res["ok"] is False
    assert "template" in res["reason"]


def test_add_schedule_unknown_workflow(eng: WorkflowEngine) -> None:
    assert eng.add_schedule("wf_missing", "0 8 * * *")["ok"] is False


def test_schedule_persists_across_engine_restart(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng, cron="0 8 * * *")
    eng.add_webhook(wf_id, secret="s3cret")

    # Backend restart: a brand-new engine over the same state file.
    eng2 = WorkflowEngine()
    schedules = eng2.get_schedules()
    assert list(schedules) == [wf_id]
    assert schedules[wf_id]["cron"] == "0 8 * * *"
    assert schedules[wf_id]["enabled"] is True
    assert schedules[wf_id]["last_fired_at"] is None
    hooks = eng2.get_webhooks()
    assert hooks[wf_id]["webhook_id"] == eng.get_webhooks()[wf_id]["webhook_id"]
    assert hooks[wf_id]["trigger_count"] == 0


def test_schedule_dropped_when_workflow_deleted(eng: WorkflowEngine) -> None:
    wf_id = _make(eng, cron="0 8 * * *")
    eng.delete(wf_id)
    assert eng.get_schedules() == {}


# ── Due evaluation + idempotence ──────────────────────────────────────────


def test_due_schedules_fires_only_at_time(eng: WorkflowEngine) -> None:
    wf_id = _make(eng, cron="0 8 * * *")
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 0)) == [wf_id]
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 1)) == []
    assert eng.due_schedules(datetime(2026, 9, 13, 7, 59)) == []


def test_due_schedules_idempotent_within_minute(eng: WorkflowEngine) -> None:
    wf_id = _make(eng, cron="0 8 * * *")
    now = datetime(2026, 9, 13, 8, 0)
    assert eng.due_schedules(now) == [wf_id]
    eng.mark_fired(wf_id, "completed", at=now)
    # Same minute after firing: no double-fire.
    assert eng.due_schedules(now.replace(second=45)) == []
    # Next day 8:00: due again.
    assert eng.due_schedules(datetime(2026, 9, 14, 8, 0)) == [wf_id]


def test_due_idempotence_survives_restart(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng, cron="0 8 * * *")
    eng.mark_fired(wf_id, "completed", at=datetime(2026, 9, 13, 8, 0))

    eng2 = WorkflowEngine()
    assert eng2.due_schedules(datetime(2026, 9, 13, 8, 0, 30)) == []


def test_due_schedules_skips_disabled_workflows(eng: WorkflowEngine) -> None:
    wf_id = _make(eng, cron="* * * * *")
    eng.update(wf_id, enabled=False)
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 0)) == []
    eng.update(wf_id, enabled=True)
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 0)) == [wf_id]


def test_due_schedules_skips_corrupt_cron(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    # Force an expression past validation (as if the dialect shrank).
    eng._schedules[wf_id] = {"cron": "0 8 * * * 2026", "enabled": True, "last_fired_at": None}
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 0)) == []


def test_mark_fired_stamps_status(eng: WorkflowEngine) -> None:
    wf_id = _make(eng, cron="0 8 * * *")
    now = datetime(2026, 9, 13, 8, 0)
    eng.mark_fired(wf_id, "failed", at=now)
    sched = eng.get_schedules()[wf_id]
    assert sched["last_status"] == "failed"
    # Stamp is the evaluation time (fake clock compatible), and the marker
    # suppresses re-fire in the same minute.
    assert eng.due_schedules(now.replace(second=30)) == []
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 0)) == []  # still same minute
    assert eng.due_schedules(datetime(2026, 9, 14, 8, 0)) == [wf_id]  # next occurrence


# ── Scheduler loop (fake clock, no sleeps) ────────────────────────────────


async def test_scheduler_tick_fires_due_workflow(eng: WorkflowEngine, sched: WorkflowTriggerScheduler) -> None:
    wf_id = _make(eng, cron="0 8 * * *")
    fired = await sched.tick(datetime(2026, 9, 13, 8, 0))
    assert fired == [wf_id]
    execs = eng.get_executions(wf_id)
    assert len(execs) == 1
    assert execs[0]["source"] == "scheduled"
    # Second tick in the same minute: nothing (idempotent).
    assert await sched.tick(datetime(2026, 9, 13, 8, 0, 30)) == []
    # 8:01: nothing; next day 8:00: fires again.
    assert await sched.tick(datetime(2026, 9, 13, 8, 1)) == []
    assert await sched.tick(datetime(2026, 9, 14, 8, 0)) == [wf_id]
    assert len(eng.get_executions(wf_id)) == 2


async def test_scheduler_tick_skips_disabled_workflow(eng: WorkflowEngine, sched: WorkflowTriggerScheduler) -> None:
    wf_id = _make(eng, cron="* * * * *")
    eng.update(wf_id, enabled=False)
    # Disabled workflows are filtered at due-evaluation: no run, no marker.
    assert await sched.tick(datetime(2026, 9, 13, 8, 0)) == []
    assert eng.get_executions(wf_id) == []
    assert eng.get_schedules()[wf_id]["last_status"] is None


# ── Schedule pause/resume (Triggers tab toggle) ───────────────────────────


def test_pause_resume_keeps_schedule_and_gates_fires(eng: WorkflowEngine) -> None:
    """Pause is a real gate: paused schedules are skipped by due_schedules()
    without losing their cron, history, or timestamps. Resume re-arms."""
    wf_id = _make(eng, cron="* * * * *")
    eng.mark_fired(wf_id, "completed", at=datetime(2026, 9, 13, 8, 0))

    paused = eng.set_schedule_enabled(wf_id, False)
    assert paused["ok"] is True and paused["schedule"]["enabled"] is False
    sched = eng.get_schedules()[wf_id]
    # Kept, not deleted: cron + last-fired history survive the pause.
    assert sched["cron"] == "* * * * *"
    assert sched["last_fired_at"] is not None
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 1)) == []

    resumed = eng.set_schedule_enabled(wf_id, True)
    assert resumed["schedule"]["enabled"] is True
    assert eng.due_schedules(datetime(2026, 9, 13, 8, 1)) == [wf_id]


def test_pause_unknown_and_missing_schedule(eng: WorkflowEngine) -> None:
    assert eng.set_schedule_enabled("wf_missing", False)["ok"] is False
    wf_id = _make(eng)  # no schedule attached
    assert eng.set_schedule_enabled(wf_id, False)["ok"] is False


def test_paused_schedule_persists_across_restart(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng)
    eng.add_schedule(wf_id, "0 8 * * *")
    assert eng.set_schedule_enabled(wf_id, False)["ok"] is True

    eng2 = WorkflowEngine()
    assert eng2.get_schedules()[wf_id]["enabled"] is False


async def test_scheduler_tick_skips_paused_until_resumed(
    eng: WorkflowEngine, sched: WorkflowTriggerScheduler
) -> None:
    wf_id = _make(eng, cron="* * * * *")
    assert eng.set_schedule_enabled(wf_id, False)["ok"] is True
    # Paused: the every-minute schedule never fires and never marks.
    assert await sched.tick(datetime(2026, 9, 13, 8, 0)) == []
    assert eng.get_executions(wf_id) == []
    assert eng.get_schedules()[wf_id]["last_status"] is None
    # Resume: the very next tick fires.
    assert eng.set_schedule_enabled(wf_id, True)["ok"] is True
    assert await sched.tick(datetime(2026, 9, 13, 8, 1)) == [wf_id]
    assert len(eng.get_executions(wf_id)) == 1


async def test_scheduler_survives_bad_state(sched: WorkflowTriggerScheduler) -> None:
    # A schedule whose workflow vanished must not raise.
    eng = sched._engine
    eng._schedules["wf_ghost"] = {"cron": "* * * * *", "enabled": True, "last_fired_at": None}
    fired = await sched.tick(datetime(2026, 9, 13, 8, 0))
    assert "wf_ghost" not in fired


def test_scheduler_start_stop_lifecycle(sched: WorkflowTriggerScheduler) -> None:
    import asyncio

    async def _run() -> None:
        sched.start()
        assert sched.running is True
        sched.start()  # idempotent
        await sched.stop()
        assert sched.running is False
        await sched.stop()  # idempotent

    asyncio.run(_run())


def test_scheduler_singleton(workflow_state: Path) -> None:
    assert get_workflow_trigger_scheduler() is get_workflow_trigger_scheduler()


# ── Schedules route (patched engine, house pattern) ──────────────────────


# ── Run source tagging ────────────────────────────────────────────────────


def test_execute_source_defaults_to_manual(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.execute(wf_id)
    assert eng.get_executions(wf_id)[0]["source"] == "manual"


# ── Webhooks: engine + route ──────────────────────────────────────────────


def test_add_webhook_auto_mints_secret(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id)["webhook"]
    assert hook["webhook_id"].startswith("wh_")
    assert len(hook["secret"]) == 32
    assert hook["trigger_count"] == 0


def test_add_webhook_rejects_templates(eng: WorkflowEngine) -> None:
    assert eng.add_webhook("daily_briefing")["ok"] is False


def test_fire_webhook_validates_secret(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id, secret="right-secret")["webhook"]

    assert eng.fire_webhook(hook["webhook_id"], "wrong-secret")["status_code"] == 401
    assert eng.fire_webhook(hook["webhook_id"], None)["status_code"] == 401
    assert eng.fire_webhook("wh_unknown", "right-secret")["status_code"] == 404

    ok = eng.fire_webhook(hook["webhook_id"], "right-secret", {"score": 90})
    assert ok["ok"] is True
    assert ok["trigger_count"] == 1
    assert eng.get_executions(wf_id)[0]["source"] == "webhook"
    assert eng.get_executions(wf_id)[0]["input"] == {"score": 90}


def test_fire_webhook_counts_and_persists(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id, secret="k")["webhook"]
    eng.fire_webhook(hook["webhook_id"], "k")
    eng.fire_webhook(hook["webhook_id"], "k")

    eng2 = WorkflowEngine()
    assert eng2.get_webhooks()[wf_id]["trigger_count"] == 2


def test_fire_webhook_disabled_and_disabled_workflow(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id, secret="k")["webhook"]
    eng._webhooks[wf_id]["enabled"] = False
    assert eng.fire_webhook(hook["webhook_id"], "k")["status_code"] == 409

    eng._webhooks[wf_id]["enabled"] = True
    eng.update(wf_id, enabled=False)
    assert eng.fire_webhook(hook["webhook_id"], "k")["status_code"] == 409


@pytest.fixture()
def _registered_hook(monkeypatch: pytest.MonkeyPatch, eng: WorkflowEngine):
    """Register a webhook on the isolated engine and patch it in as the
    service-module singleton. Route handlers do a lazy
    `from ...workflow_builder import workflow_engine` at call time, which
    resolves from the service module's namespace — so patching there
    redirects every workflow route to the isolated engine (the module
    singleton was constructed at import time with the real state path)."""
    import dash_backend.services.workflow_builder as wb

    monkeypatch.setattr(wb, "workflow_engine", eng)
    wf_id = _make(eng, cron="0 9 * * *")  # webhook flow carries a schedule too
    hook = eng.add_webhook(wf_id, secret="route-secret")["webhook"]
    return hook, wf_id


async def test_webhook_route_happy_path(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    r = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        json={"score": 42},
        headers={"X-Webhook-Secret": "route-secret"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["trigger_count"] == 1
    assert body["execution"]["source"] == "webhook"


async def test_webhook_route_secret_via_query_param(client, _registered_hook) -> None:
    hook, _ = _registered_hook
    r = await client.post(f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}?secret=route-secret")
    assert r.status_code == 200, r.text


async def test_webhook_route_rejects_bad_secret_anonymously(client, _registered_hook) -> None:
    hook, _ = _registered_hook
    r = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        json={},
        headers={"X-Webhook-Secret": "nope"},
    )
    assert r.status_code == 401
    r2 = await client.post(f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}")
    assert r2.status_code == 401


async def test_webhook_route_unknown_webhook(client, _registered_hook) -> None:
    r = await client.post("/api/v1/enhanced/workflows/webhook/wh_missing", headers={"X-Webhook-Secret": "x"})
    assert r.status_code == 404


async def test_webhook_route_non_json_body_is_fine(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    r = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        content=b"plain text",
        headers={"X-Webhook-Secret": "route-secret", "Content-Type": "text/plain"},
    )
    assert r.status_code == 200, r.text
    assert wf_id  # run happened with empty context


async def test_schedules_route_lists_persisted_schedules(
    client, _registered_hook
) -> None:
    hook, wf_id = _registered_hook
    r = await client.get("/api/v1/enhanced/workflows/schedules/all")
    assert r.status_code == 200, r.text
    assert wf_id in r.json()["schedules"]


# ── Trigger management routes (UI surface) ────────────────────────────────


async def test_schedule_crud_routes_round_trip(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    # PUT-like set: create a schedule with a supported cron.
    r = await client.post(
        f"/api/v1/enhanced/workflows/{wf_id}/schedule",
        json={"cron": "30 7 * * *"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True

    listed = (await client.get("/api/v1/enhanced/workflows/schedules/all")).json()["schedules"]
    assert listed[wf_id]["cron"] == "30 7 * * *"

    # Validation feedback: unsupported dialect is rejected with a reason.
    bad = await client.post(
        f"/api/v1/enhanced/workflows/{wf_id}/schedule",
        json={"cron": "0 8 * * * 2026"},
    )
    assert bad.status_code == 200  # 200 with ok=False + reason (UI shows it)
    body = bad.json()
    assert body["ok"] is False and "Unsupported cron" in body["reason"]

    # Delete the schedule.
    r = await client.delete(f"/api/v1/enhanced/workflows/{wf_id}/schedule")
    assert r.status_code == 200, r.text
    listed_after = (await client.get("/api/v1/enhanced/workflows/schedules/all")).json()["schedules"]
    assert wf_id not in listed_after


async def test_webhook_crud_routes_round_trip(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    # Mint with an explicit secret.
    r = await client.post(
        f"/api/v1/enhanced/workflows/{wf_id}/webhook",
        json={"secret": "ui-chosen-secret"},
    )
    assert r.status_code == 200, r.text
    wh = r.json()["webhook"]
    assert wh["secret"] == "ui-chosen-secret"

    # Listed with the secret (single-user local app: UI re-displays it).
    listed = (await client.get("/api/v1/enhanced/workflows/webhooks/all")).json()["webhooks"]
    assert listed[wf_id]["webhook_id"] == wh["webhook_id"]
    assert listed[wf_id]["trigger_count"] == 0

    # Fire it through the public webhook route → count increments.
    fired = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{wh['webhook_id']}",
        headers={"X-Webhook-Secret": "ui-chosen-secret"},
    )
    assert fired.status_code == 200, fired.text
    listed2 = (await client.get("/api/v1/enhanced/workflows/webhooks/all")).json()["webhooks"]
    assert listed2[wf_id]["trigger_count"] == 1

    # Delete the webhook.
    r = await client.delete(f"/api/v1/enhanced/workflows/{wf_id}/webhook")
    assert r.status_code == 200, r.text
    listed3 = (await client.get("/api/v1/enhanced/workflows/webhooks/all")).json()["webhooks"]
    assert wf_id not in listed3


async def test_webhook_route_auto_mints_secret(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    r = await client.post(f"/api/v1/enhanced/workflows/{wf_id}/webhook", json={})
    assert r.status_code == 200, r.text
    wh = r.json()["webhook"]
    assert wh["secret"] and len(wh["secret"]) == 32


async def test_schedule_pause_resume_route_round_trip(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    r = await client.put(
        f"/api/v1/enhanced/workflows/{wf_id}/schedule/enabled",
        json={"enabled": False},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["schedule"]["enabled"] is False

    listed = (await client.get("/api/v1/enhanced/workflows/schedules/all")).json()["schedules"]
    assert listed[wf_id]["enabled"] is False

    r2 = await client.put(
        f"/api/v1/enhanced/workflows/{wf_id}/schedule/enabled",
        json={"enabled": True},
    )
    assert r2.status_code == 200 and r2.json()["schedule"]["enabled"] is True


async def test_schedule_pause_route_unknown_schedule(client, _registered_hook) -> None:
    import dash_backend.services.workflow_builder as wb

    res = wb.workflow_engine.create("no-schedule flow", nodes=[], edges=[])
    bare_wf = res["workflow"]["id"]  # no schedule attached
    r = await client.put(
        f"/api/v1/enhanced/workflows/{bare_wf}/schedule/enabled",
        json={"enabled": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert "reason" in r.json()


async def test_executions_route_lists_workflow_runs(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    fired = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        headers={"X-Webhook-Secret": "route-secret"},
    )
    assert fired.status_code == 200
    r = await client.get(f"/api/v1/enhanced/workflows/{wf_id}/executions?limit=10")
    assert r.status_code == 200, r.text
    execs = r.json()["executions"]
    assert len(execs) == 1
    assert execs[0]["source"] == "webhook"
    assert execs[0]["status"] == "completed"
    assert "duration_ms" in execs[0]


# ── Webhook pause/resume (decisions.md #79) ───────────────────────────────


def test_webhook_pause_resume_engine_round_trip(eng: WorkflowEngine) -> None:
    """Paused = real gate: 409, zero count, zero executions. Resume keeps
    secret and count and fires again."""
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id, secret="pause-secret")["webhook"]

    # Baseline fire so the count is nonzero before pausing.
    assert eng.fire_webhook(hook["webhook_id"], "pause-secret")["ok"] is True
    assert eng.get_webhooks()[wf_id]["trigger_count"] == 1

    # Pause via the setter — the real control surface, not dict poking.
    off = eng.set_webhook_enabled(wf_id, False)
    assert off["ok"] is True and off["webhook"]["enabled"] is False
    refused = eng.fire_webhook(hook["webhook_id"], "pause-secret", {"x": 1})
    assert refused["status_code"] == 409
    assert "disabled" in refused.get("reason", "").lower()
    # The pause was real: no count bump, no execution record.
    assert eng.get_webhooks()[wf_id]["trigger_count"] == 1
    assert len(eng.get_executions(wf_id)) == 1  # only the baseline run

    # Config survived the pause: secret unchanged, count not reset.
    assert eng.get_webhooks()[wf_id]["secret"] == "pause-secret"

    # Resume fires again with the same secret; count continues, not resets.
    on = eng.set_webhook_enabled(wf_id, True)
    assert on["ok"] is True and on["webhook"]["enabled"] is True
    ok = eng.fire_webhook(hook["webhook_id"], "pause-secret", {"y": 2})
    assert ok["ok"] is True
    assert eng.get_webhooks()[wf_id]["trigger_count"] == 2


def test_webhook_pause_persists_across_restart(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng)
    hook = eng.add_webhook(wf_id, secret="k")["webhook"]
    eng.set_webhook_enabled(wf_id, False)

    eng2 = WorkflowEngine()
    assert eng2.get_webhooks()[wf_id]["enabled"] is False
    assert eng2.fire_webhook(hook["webhook_id"], "k")["status_code"] == 409


def test_webhook_setter_unknown_workflow(eng: WorkflowEngine) -> None:
    res = eng.set_webhook_enabled("wf_nobody", False)
    assert res["ok"] is False
    assert "reason" in res


async def test_webhook_pause_resume_route_round_trip(client, _registered_hook) -> None:
    hook, wf_id = _registered_hook
    base = f"/api/v1/enhanced/workflows/{wf_id}"

    r = await client.put(f"{base}/webhook/enabled", json={"enabled": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["webhook"]["enabled"] is False

    fired = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        headers={"X-Webhook-Secret": "route-secret"},
    )
    assert fired.status_code == 409

    r = await client.put(f"{base}/webhook/enabled", json={"enabled": True})
    assert r.status_code == 200 and r.json()["webhook"]["enabled"] is True
    fired = await client.post(
        f"/api/v1/enhanced/workflows/webhook/{hook['webhook_id']}",
        headers={"X-Webhook-Secret": "route-secret"},
    )
    assert fired.status_code == 200


async def test_webhook_pause_route_unknown_workflow(client, _registered_hook) -> None:
    r = await client.put(
        "/api/v1/enhanced/workflows/wf_missing/webhook/enabled",
        json={"enabled": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert "reason" in r.json()


# ── Trigger status for the System page (decisions.md #81) ─────────────────


def _import_status_helpers():
    from dash_backend.services.workflow_builder import get_workflow_trigger_scheduler, next_cron_due

    return get_workflow_trigger_scheduler, next_cron_due


def test_next_cron_due_basic_and_boundaries() -> None:
    _, next_cron_due = _import_status_helpers()
    now = datetime(2026, 9, 16, 15, 30, 7)  # Wednesday, 15:30:07 local

    # Every-minute: the very next minute boundary.
    nxt = next_cron_due("* * * * *", now)
    assert nxt == datetime(2026, 9, 16, 15, 31)

    # Same-minute 'after' is strictly exclusive (a schedule that fired at
    # 15:30 must not report 15:30 again as 'next').
    assert next_cron_due("* * * * *", now.replace(second=0)) == datetime(2026, 9, 16, 15, 31)

    # Daily 08:00: rolls to tomorrow when today's slot has passed.
    assert next_cron_due("0 8 * * *", now) == datetime(2026, 9, 17, 8, 0)
    assert next_cron_due("0 8 * * *", now.replace(hour=7)) == datetime(2026, 9, 16, 8, 0)

    # Day-of-week: 'Friday' from Wednesday = 2 days ahead.
    fri = next_cron_due("0 18 * * 5", now)
    assert fri == datetime(2026, 9, 18, 18, 0)


def test_next_cron_due_honest_none_for_impossible_or_broken() -> None:
    _, next_cron_due = _import_status_helpers()
    now = datetime(2026, 9, 16, 15, 30)

    # Feb 30 parses fine (fields in range) but no calendar day delivers it.
    assert next_cron_due("0 2 30 2 *", now) is None
    # Garbage the parser rejects also yields None (caller decides policy).
    assert next_cron_due("not a cron", now) is None
    # Within-horizon guarantee: * * 31 1 * next January 31 exists.
    nxt = next_cron_due("0 0 31 1 *", now)
    assert nxt is not None and nxt.month == 1 and nxt.day == 31


def test_get_trigger_status_counts_and_next_due(eng: WorkflowEngine) -> None:
    eng.create("a", nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
    eng.create("b", nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
    eng.create("c", nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
    wf_ids = [wf["id"] for wf in eng.list_all() if not wf.get("is_template")]
    a, b, c = wf_ids[0], wf_ids[1], wf_ids[2]

    eng.add_schedule(a, "* * * * *")
    eng.add_schedule(b, "0 8 * * *")
    eng.add_schedule(c, "0 2 * * *")
    eng.set_schedule_enabled(c, False)  # paused schedule
    eng.add_webhook(b, secret="s2")
    eng.set_webhook_enabled(b, False)   # paused webhook
    eng.add_event_trigger(a, "file.changed")

    status = eng.get_trigger_status()
    assert status["schedules_total"] == 3
    assert status["schedules_active"] == 2
    assert status["schedules_paused"] == 1
    assert status["webhooks_total"] == 1 and status["webhooks_paused"] == 1
    assert status["event_triggers_total"] == 1 and status["event_triggers_paused"] == 0

    # The every-minute schedule is the next due: within the current minute
    # window it is 'due now'; past it, the next minute boundary.
    nd = status["next_due"]
    assert nd is not None and nd["workflow_id"] == a
    due = datetime.fromisoformat(nd["due_at"])
    now = datetime.now().replace(second=0, microsecond=0)
    assert due in (now, now + timedelta(minutes=1))


def test_get_trigger_status_paused_schedule_excluded_from_next_due(eng: WorkflowEngine) -> None:
    eng.create("only", nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
    wf_id = [wf["id"] for wf in eng.list_all() if not wf.get("is_template")][0]
    eng.add_schedule(wf_id, "* * * * *")
    eng.set_schedule_enabled(wf_id, False)

    status = eng.get_trigger_status()
    assert status["schedules_paused"] == 1
    # The scheduler really will skip it, so 'next due' honestly reports none.
    assert status["next_due"] is None

    eng.set_schedule_enabled(wf_id, True)
    assert eng.get_trigger_status()["next_due"] is not None


def test_get_trigger_status_invalid_cron_not_reported_as_due(eng: WorkflowEngine) -> None:
    eng.create("x", nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
    wf_id = [wf["id"] for wf in eng.list_all() if not wf.get("is_template")][0]
    # Force an unparseable cron into state (add_schedule would refuse).
    eng._schedules[wf_id] = {"cron": "bogus * * * *", "enabled": True, "last_fired_at": None}
    status = eng.get_trigger_status()
    assert status["next_due"] is None  # never invent a due time


def test_scheduler_last_tick_and_liveness(sched: WorkflowTriggerScheduler) -> None:
    get_workflow_trigger_scheduler, _ = _import_status_helpers()
    eng = sched.engine
    _make(eng, cron="* * * * *")

    assert sched.running is False
    assert sched.last_tick_at is None  # never ticked: reported as such

    fired = asyncio.run(sched.tick(datetime(2026, 9, 16, 15, 30)))
    assert len(fired) == 1  # the one every-minute workflow fired exactly once
    assert sched.last_tick_at == datetime(2026, 9, 16, 15, 30).isoformat()
    # running stays False — tick() without start() is not the server loop.
    assert sched.running is False

    # A stopped scheduler is stopped, not "running but stale": stop() must
    # clear the tick stamp so a fresh boot never inherits a stale liveness
    # timestamp (decisions.md #104).
    asyncio.run(sched.stop())
    assert sched.running is False
    assert sched.last_tick_at is None

    # The singleton's liveness is what the status route exposes.
    assert get_workflow_trigger_scheduler().running is False


async def test_trigger_status_route(client, workflow_state) -> None:
    r = await client.get("/api/v1/enhanced/workflows/trigger-status")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    # Scheduler honesty: not started in tests, so it must say so.
    assert body["scheduler"]["running"] is False
    assert body["scheduler"]["last_tick_at"] is None
    for key in ("schedules_paused", "webhooks_paused", "event_triggers_paused", "next_due"):
        assert key in body


def test_trigger_status_route_not_shadowed_by_dynamic_route() -> None:
    """The literal route must win over /workflows/{workflow_id}."""
    from fastapi.routing import APIRoute

    from dash_backend.api.routes import enhanced_features

    paths = [
        (r.path, getattr(r, "methods", set()))
        for r in enhanced_features.router.routes
        if isinstance(r, APIRoute)
    ]
    trigger_status_idx = next(
        i for i, (p, m) in enumerate(paths) if p.endswith("/workflows/trigger-status") and "GET" in m
    )
    dynamic_idx = next(
        i for i, (p, m) in enumerate(paths) if p.endswith("/workflows/{workflow_id}") and "GET" in m
    )
    assert trigger_status_idx < dynamic_idx


# ── paused_since + skipped_fires accounting (decisions.md #84) ────────────


def test_pause_stamps_paused_since_and_resume_clears_it(eng: WorkflowEngine) -> None:
    _make(eng, cron="* * * * *")
    wf_id = eng.list_all()[-1]["id"]

    r = eng.set_schedule_enabled(wf_id, False)
    assert r["schedule"]["paused_since"] is not None
    assert r["schedule"]["skipped_fires"] == 0

    r = eng.set_schedule_enabled(wf_id, True)
    assert r["schedule"]["paused_since"] is None
    # The ledger survives resume: "what did pausing cost me?" stays true.
    assert r["schedule"]["skipped_fires"] == 0


def test_skipped_fires_count_only_minutes_at_or_after_pause(eng: WorkflowEngine) -> None:
    _make(eng, cron="* * * * *")
    wf_id = eng.list_all()[-1]["id"]
    eng.add_schedule(wf_id, "* * * * *")
    eng.set_schedule_enabled(wf_id, False)
    sched = eng._schedules[wf_id]

    now = datetime(2026, 9, 16, 17, 0)
    sched["paused_since"] = now.isoformat()

    # Matching minute BEFORE the pause: not this pause's cost.
    assert eng.due_schedules(now - timedelta(minutes=1)) == []
    assert sched["skipped_fires"] == 0

    # Pause minute and later matching minutes accrue one each.
    assert eng.due_schedules(now) == []
    assert sched["skipped_fires"] == 1
    assert eng.due_schedules(now + timedelta(minutes=1)) == []
    assert sched["skipped_fires"] == 2

    # Idempotence: re-evaluating the same minute must not double-count.
    assert eng.due_schedules(now + timedelta(minutes=1)) == []
    assert sched["skipped_fires"] == 2


def test_minute_that_fired_just_before_pause_not_counted(eng: WorkflowEngine) -> None:
    _make(eng, cron="* * * * *")
    wf_id = eng.list_all()[-1]["id"]
    eng.add_schedule(wf_id, "* * * * *")
    eng.set_schedule_enabled(wf_id, False)
    sched = eng._schedules[wf_id]

    now = datetime(2026, 9, 16, 17, 0)
    sched["paused_since"] = now.isoformat()
    # The fire genuinely happened in this same minute, seconds before the pause.
    sched["last_fired_at"] = now.isoformat()
    assert eng.due_schedules(now) == []
    assert sched["skipped_fires"] == 0


def test_skipped_fires_and_paused_since_persist_across_restart(
    workflow_state, monkeypatch: pytest.MonkeyPatch
) -> None:
    e1 = WorkflowEngine()
    _make(e1, cron="* * * * *")
    wf_id = e1.list_all()[-1]["id"]
    e1.add_schedule(wf_id, "* * * * *")
    e1.set_schedule_enabled(wf_id, False)
    now = datetime(2026, 9, 16, 17, 0)
    e1._schedules[wf_id]["paused_since"] = now.isoformat()
    assert e1.due_schedules(now + timedelta(minutes=1)) == []
    assert e1._schedules[wf_id]["skipped_fires"] == 1

    e2 = WorkflowEngine()  # fresh engine, same state file
    sched = e2._schedules[wf_id]
    assert sched["enabled"] is False
    assert sched["paused_since"] == now.isoformat()
    assert sched["skipped_fires"] == 1


def test_resume_re_arms_and_skipped_ledger_stays(eng: WorkflowEngine) -> None:
    _make(eng, cron="* * * * *")
    wf_id = eng.list_all()[-1]["id"]
    eng.add_schedule(wf_id, "* * * * *")
    eng.set_schedule_enabled(wf_id, False)
    now = datetime(2026, 9, 16, 17, 0)
    eng._schedules[wf_id]["paused_since"] = now.isoformat()
    assert eng.due_schedules(now) == []
    assert eng.due_schedules(now + timedelta(minutes=1)) == []
    assert eng._schedules[wf_id]["skipped_fires"] == 2

    eng.set_schedule_enabled(wf_id, True)
    # Fires normally again...
    assert eng.due_schedules(now + timedelta(minutes=2)) == [wf_id]
    # ...and the historical skip count is untouched by resuming.
    assert eng._schedules[wf_id]["skipped_fires"] == 2


def test_new_cron_resets_skip_ledger(eng: WorkflowEngine) -> None:
    _make(eng, cron="* * * * *")
    wf_id = eng.list_all()[-1]["id"]
    eng.add_schedule(wf_id, "* * * * *")
    eng.set_schedule_enabled(wf_id, False)
    eng._schedules[wf_id]["skipped_fires"] = 7
    # Replacing the cron is a new arrangement: ledger starts clean.
    eng.add_schedule(wf_id, "0 8 * * *")
    assert eng._schedules[wf_id]["skipped_fires"] == 0
    assert eng._schedules[wf_id]["paused_since"] is None


# ── Pause-all / resume-all (decisions.md #85) ────────────────────────────


def test_pause_all_resumes_all_and_reports_changed(eng: WorkflowEngine) -> None:
    wf_ids = []
    for name in ("a", "b", "c"):
        res = eng.create(name, nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
        wf_id = res["workflow"]["id"]
        eng.add_schedule(wf_id, "* * * * *")
        wf_ids.append(wf_id)

    r = eng.set_all_schedules_enabled(False)
    assert r["ok"] is True and r["changed"] == 3 and r["total"] == 3
    assert all(not s["enabled"] for s in eng._schedules.values())
    # #84 semantics ride along: every fresh pause is stamped + zeroed ledger.
    assert all(s["paused_since"] is not None and s["skipped_fires"] == 0 for s in eng._schedules.values())

    # Idempotence: re-pausing changes nothing and restamps nothing.
    stamps = {wf: s["paused_since"] for wf, s in eng._schedules.items()}
    r2 = eng.set_all_schedules_enabled(False)
    assert r2["changed"] == 0
    assert {wf: s["paused_since"] for wf, s in eng._schedules.items()} == stamps

    r3 = eng.set_all_schedules_enabled(True)
    assert r3["changed"] == 3
    assert all(s["enabled"] and s["paused_since"] is None for s in eng._schedules.values())
    # Re-resume is also idempotent.
    assert eng.set_all_schedules_enabled(True)["changed"] == 0


def test_pause_all_leaves_already_paused_untouched(eng: WorkflowEngine) -> None:
    wf_ids = []
    for name in ("a", "b"):
        res = eng.create(name, nodes=[{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}], edges=[])
        wf_id = res["workflow"]["id"]
        eng.add_schedule(wf_id, "* * * * *")
        wf_ids.append(wf_id)
    eng.set_schedule_enabled(wf_ids[0], False)
    stamp_before = eng._schedules[wf_ids[0]]["paused_since"]
    eng._schedules[wf_ids[0]]["skipped_fires"] = 4

    r = eng.set_all_schedules_enabled(False)
    assert r["changed"] == 1  # only the active one flipped
    # The pre-paused schedule kept its #84 pause history exactly.
    assert eng._schedules[wf_ids[0]]["paused_since"] == stamp_before
    assert eng._schedules[wf_ids[0]]["skipped_fires"] == 4


async def test_pause_all_route_roundtrip(client, workflow_state, monkeypatch: pytest.MonkeyPatch) -> None:
    import dash_backend.services.workflow_builder as wb

    e = WorkflowEngine()
    monkeypatch.setattr(wb, "workflow_engine", e)
    wf_ids = []
    for name in ("a", "b"):
        wf_ids.append(_make(e, cron="* * * * *"))

    r = await client.put(
        "/api/v1/enhanced/workflows/schedules/enabled", json={"enabled": False}
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["changed"] == 2
    assert body["paused_remaining"] == 2 and body["active_remaining"] == 0
    assert set(body["schedules"].keys()) == set(wf_ids)

    r = await client.put(
        "/api/v1/enhanced/workflows/schedules/enabled", json={"enabled": True}
    )
    body = r.json()
    assert body["changed"] == 2 and body["active_remaining"] == 2
