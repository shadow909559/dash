"""Workflow event triggers + real delay semantics (decisions.md #57).

What is under test:
- engine event triggers: attach validation, replace semantics, matching
  (topic + payload keys), disabled/template rejections, persistence,
- the fire_event path: payload lands as run input `event`, source=tagged,
- the event bridge: bus delivery, direct producer entry points,
- the polling file watcher (driven with a short poll — no watchdog),
- real producers: email ingest publishes exactly once per NEW message,
  reminder firing publishes,
- delay nodes: real sleep on trigger paths, instant on manual runs,
  clamped to the honesty cap,
- routes: set/clear/list event triggers through the real app.

Everything hermetic: engine state in temp files, fake bus fakes, no
network, no long sleeps (delay tests use sub-second values).
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import pytest

from dash_backend.services.workflow_builder import WorkflowEngine
from dash_backend.services.workflow_event_bridge import (
    WorkflowEventBridge,
    _watch_paths_from_env,
)


# ── Fixtures ──────────────────────────────────────────────────────────────


@pytest.fixture()
def workflow_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    state = tmp_path / "wf_state.json"
    monkeypatch.setenv("DASH_WORKFLOW_STATE", str(state))
    return state


@pytest.fixture()
def eng(workflow_state: Path) -> WorkflowEngine:
    return WorkflowEngine()


@pytest.fixture()
def fake_bus(monkeypatch: pytest.MonkeyPatch) -> Any:
    """Minimal stand-in for EventBus covering what the bridge uses."""

    class FakeBus:
        def __init__(self) -> None:
            self.subs: dict[str, list] = {}

        def subscribe(self, topic, callback, filter_fn=None, name=""):
            self.subs.setdefault(topic, []).append(callback)
            return f"sub-{len(self.subs)}"

        def unsubscribe_all(self, prefix: str) -> int:
            n = sum(len(v) for v in self.subs.values())
            self.subs.clear()
            return n

        async def publish_sync(self, topic, data=None, source="", **kw):
            for cb in self.subs.get(topic, []):
                await cb(type("E", (), {"topic": topic, "data": data or {}})())

    return FakeBus()


@pytest.fixture()
def bridge(eng: WorkflowEngine, fake_bus: Any) -> WorkflowEventBridge:
    return WorkflowEventBridge(engine=eng, bus=fake_bus)


def _make(engine: WorkflowEngine, name: str = "event flow") -> str:
    res = engine.create(
        name,
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "email.received"}, "x": 0, "y": 0},
            {"id": "n2", "type": "action", "config": {"tool": "notification.send"}, "x": 1, "y": 0},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"] is True
    return res["workflow"]["id"]


# ── Engine: attach / validate ─────────────────────────────────────────────


def test_add_event_trigger_validates(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    assert eng.add_event_trigger("wf_missing", "email.received")["ok"] is False
    assert eng.add_event_trigger(wf_id, "")["ok"] is False
    assert eng.add_event_trigger(wf_id, "bad..topic")["ok"] is False
    ok = eng.add_event_trigger(wf_id, "email.received", {"importance": 0.9})
    assert ok["ok"] is True and ok["trigger"]["match"] == {"importance": 0.9}


def test_add_event_trigger_rejects_template(eng: WorkflowEngine) -> None:
    templates = [w["id"] for w in eng.list_templates()]
    assert templates, "templates should exist"
    assert eng.add_event_trigger(templates[0], "email.received")["ok"] is False


def test_add_event_trigger_replaces_previous(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    eng.add_event_trigger(wf_id, "reminder.fired")
    assert eng.get_event_triggers()[wf_id]["event"] == "reminder.fired"


# ── Engine: fire matching ─────────────────────────────────────────────────


def test_fire_event_matches_topic_and_payload(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received", {"importance": 0.9})

    assert eng.fire_event("reminder.fired", {}) == []          # wrong topic
    assert eng.fire_event("email.received", {"importance": 0.2}) == []  # no match
    fired = eng.fire_event("email.received", {"importance": 0.9})
    assert fired == [wf_id]


def test_fire_event_tags_source_and_payload(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    eng.fire_event("email.received", {"subject": "hi"})
    rec = eng.get_executions(wf_id)[0]
    assert rec["source"] == "event"
    assert rec["input"] == {"event": {"topic": "email.received", "subject": "hi"}}


def test_fire_event_skips_disabled_workflow(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    eng.update(wf_id, enabled=False)
    assert eng.fire_event("email.received", {}) == []


def test_fire_event_counts_and_persists(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    eng.fire_event("email.received", {})
    eng.fire_event("email.received", {})
    eng2 = WorkflowEngine()
    restored = eng2.get_event_triggers()[wf_id]
    assert restored["trigger_count"] == 2
    assert restored["last_fired_at"] is not None


def test_remove_event_trigger(eng: WorkflowEngine) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    assert eng.remove_event_trigger(wf_id)["ok"] is True
    assert wf_id not in eng.get_event_triggers()


# ── Bridge: bus delivery + producers ──────────────────────────────────────


async def test_bridge_bus_delivery_fires_engine(
    eng: WorkflowEngine, bridge: WorkflowEventBridge, fake_bus: Any
) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    await bridge.start()
    assert bridge.subscribed is True

    await fake_bus.publish_sync("email.received", {"subject": "hello"})
    rec = eng.get_executions(wf_id)[0]
    assert rec["source"] == "event"
    assert rec["input"]["event"]["subject"] == "hello"

    await bridge.stop()
    assert bridge.subscribed is False


async def test_bridge_direct_fire_without_subscription(
    eng: WorkflowEngine, bridge: WorkflowEventBridge, fake_bus: Any
) -> None:
    """With no subscription active, producer entry points fire directly."""
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "reminder.fired")
    fired = await bridge.notify_reminder_fired({"title": "Stretch"})
    assert fired == [wf_id]
    rec = eng.get_executions(wf_id)[0]
    assert rec["input"]["event"]["title"] == "Stretch"


async def test_bridge_watches_files(
    eng: WorkflowEngine, bridge: WorkflowEventBridge, tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "file.changed", {"kind": "modified"})
    monkeypatch.setenv("DASH_WATCH_PATHS", str(tmp_path))
    watched = _watch_paths_from_env()
    assert watched == [tmp_path]

    from dash_backend.services.workflow_event_bridge import FileWatcher

    watcher = FileWatcher(bridge._on_file_event, paths=watched, poll_seconds=0.2)
    watcher.start()
    try:
        (tmp_path / "note.txt").write_text("v1", encoding="utf-8")
        created = time.time()
        while time.time() - created < 5 and eng.get_executions(wf_id) == []:
            await asyncio.sleep(0.05)
        # 'created' was filtered out by the match; modify it now.
        (tmp_path / "note.txt").write_text("v2", encoding="utf-8")
        deadline = time.time() + 5
        while time.time() < deadline:
            recs = eng.get_executions(wf_id)
            if recs:
                break
            await asyncio.sleep(0.05)
        recs = eng.get_executions(wf_id)
        assert recs, "modification should have fired the trigger"
        assert recs[0]["input"]["event"]["kind"] == "modified"
    finally:
        watcher.stop()
    assert not watcher.running


def test_file_watcher_stop_is_idempotent(tmp_path: Path) -> None:
    from dash_backend.services.workflow_event_bridge import FileWatcher

    watcher = FileWatcher(lambda payload: None, paths=[tmp_path], poll_seconds=0.2)
    watcher.stop()  # never started: must be a no-op, not a crash
    watcher.start()
    watcher.stop()
    assert not watcher.running


# ── Real producers ────────────────────────────────────────────────────────


async def test_email_ingest_publishes_once_per_new_message(tmp_path, monkeypatch) -> None:
    from dash_backend.services.email_calendar_sync import ExtendedEmailService
    from dash_backend.services.local_store import LocalStore

    seen: list[tuple] = []

    def fake_publish(topic: str, data: dict) -> None:
        seen.append((topic, data["subject"]))

    # The producer does a lazy `from ...workflow_event_bridge import
    # schedule_event_publish` at call time — patch the bridge module.
    monkeypatch.setattr(
        "dash_backend.services.workflow_event_bridge.schedule_event_publish",
        fake_publish,
    )
    svc = ExtendedEmailService(store=LocalStore(db_path=tmp_path / "t.db"))
    eml = (
        b"From: a@b.c\r\nTo: me@here\r\nSubject: Hello workflow\r\n"
        b"Message-ID: <m1@b.c>\r\n\r\nbody"
    )
    assert svc.ingest_eml(eml)["created"] is True
    assert svc.ingest_eml(eml)["created"] is False  # deduped: no second event
    assert seen == [("email.received", "Hello workflow")]


async def test_reminder_firing_publishes(monkeypatch) -> None:
    from dash_backend.autonomous.reminder_service import ReminderService

    seen: list[dict] = []
    monkeypatch.setattr(
        "dash_backend.services.workflow_event_bridge.schedule_event_publish",
        lambda topic, data: seen.append({"topic": topic, **data}),
    )
    svc = ReminderService()
    rid = await svc.set("Water plants", seconds=999)
    svc._reminders[rid].trigger_at = time.time() - 1  # due on the first tick
    await svc.start()
    try:
        deadline = time.time() + 2
        while not seen and time.time() < deadline:
            await asyncio.sleep(0.02)
    finally:
        await svc.stop()
    assert seen and seen[0]["title"] == "Water plants"
    assert seen[0]["topic"] == "reminder.fired"


# ── Delay nodes: real semantics ───────────────────────────────────────────


def _delay_flow(engine: WorkflowEngine, seconds: float) -> str:
    res = engine.create(
        "delay flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"schedule": "* * * * *"}, "x": 0, "y": 0},
            {"id": "n2", "type": "delay", "config": {"seconds": seconds}, "x": 1, "y": 0},
            {"id": "n3", "type": "action", "config": {"tool": "noop"}, "x": 2, "y": 0},
        ],
        edges=[{"from": "n1", "to": "n2"}, {"from": "n2", "to": "n3"}],
    )
    assert res["ok"] is True
    return res["workflow"]["id"]


async def test_delay_is_real_on_scheduled_path(eng: WorkflowEngine) -> None:
    wf_id = _delay_flow(eng, 0.4)
    result = await asyncio.to_thread(eng.execute, wf_id, None, "scheduled")
    rec = result["execution"]
    assert rec["status"] == "completed"
    assert rec["duration_ms"] >= 380  # the delay genuinely elapsed


async def test_delay_is_real_on_event_path(eng: WorkflowEngine) -> None:
    wf_id = _delay_flow(eng, 0.3)
    eng.add_event_trigger(wf_id, "email.received")
    await asyncio.to_thread(
        eng.fire_event, "email.received", {}
    )
    rec = eng.get_executions(wf_id)[0]
    assert rec["source"] == "event"
    assert rec["duration_ms"] >= 280


async def test_manual_run_skips_delays(eng: WorkflowEngine) -> None:
    wf_id = _delay_flow(eng, 0.5)
    result = eng.execute(wf_id, source="manual")
    assert result["execution"]["status"] == "completed"
    assert result["execution"]["duration_ms"] < 250


async def test_delay_is_clamped(eng: WorkflowEngine, monkeypatch) -> None:
    # Shrink the cap instead of sleeping the real one out: this stays a
    # millisecond-scale test while proving oversized delays are clamped.
    import dash_backend.services.workflow_builder as wb

    monkeypatch.setattr(wb, "MAX_DELAY_SECONDS", 0.15)
    wf_id = _delay_flow(eng, 9999)
    result = await asyncio.to_thread(eng.execute, wf_id, None, "scheduled")
    assert result["execution"]["status"] == "completed"
    assert result["execution"]["duration_ms"] < 5000


async def test_delay_bad_config_is_zero(eng: WorkflowEngine) -> None:
    res = eng.create(
        "bad delay",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0},
            {"id": "n2", "type": "delay", "config": {"seconds": "soon"}, "x": 1, "y": 0},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    wf_id = res["workflow"]["id"]
    result = await asyncio.to_thread(eng.execute, wf_id, None, "scheduled")
    assert result["execution"]["status"] == "completed"


async def test_scheduler_tick_survives_delay_workflow(eng: WorkflowEngine) -> None:
    """The poll loop offloads execution: a due delay-workflow must not
    block tick() beyond the run itself (here: sub-second)."""
    from dash_backend.services.workflow_builder import WorkflowTriggerScheduler
    from datetime import datetime

    wf_id = _delay_flow(eng, 0.2)
    eng.add_schedule(wf_id, "* * * * *")
    sched = WorkflowTriggerScheduler(engine=eng, poll_seconds=60)
    started = time.perf_counter()
    fired = await sched.tick(now=datetime(2026, 9, 13, 12, 0))
    elapsed = time.perf_counter() - started
    assert fired == [wf_id]
    assert elapsed < 5


# ── Routes ────────────────────────────────────────────────────────────────


@pytest.fixture()
def _patched_engine(monkeypatch: pytest.MonkeyPatch, eng: WorkflowEngine):
    import dash_backend.services.workflow_builder as wb

    monkeypatch.setattr(wb, "workflow_engine", eng)
    return eng


async def test_event_trigger_routes(client, _patched_engine: WorkflowEngine) -> None:
    wf_id = _make(_patched_engine, "routed flow")
    base = f"/api/v1/enhanced/workflows/{wf_id}"

    r = await client.put(
        f"{base}/event-trigger",
        json={"event": "file.changed", "match": {"glob": "**/*.py"}},
    )
    assert r.status_code == 200 and r.json()["ok"] is True

    r = await client.get("/api/v1/enhanced/workflows/event-triggers/all")
    assert r.status_code == 200
    assert r.json()["triggers"][wf_id]["event"] == "file.changed"

    r = await client.delete(f"{base}/event-trigger")
    assert r.status_code == 200 and r.json()["ok"] is True

    r = await client.get("/api/v1/enhanced/workflows/event-triggers/all")
    assert r.json()["triggers"] == {}


async def test_event_trigger_route_requires_auth() -> None:
    """A client with NO auth headers must never mutate trigger state."""
    from fastapi.testclient import TestClient

    from dash_backend.main import create_app

    sync_client = TestClient(create_app())
    r = sync_client.put(
        "/api/v1/enhanced/workflows/wf_x/event-trigger", json={"event": "x.y"}
    )
    assert r.status_code in (401, 403)


# ── Pause/resume (decisions.md #79) ───────────────────────────────────────


def test_event_pause_gates_fire_event(eng: WorkflowEngine) -> None:
    """The real gap (#79): fire_event must skip a paused trigger — no run,
    no count, no last_fired_at. Resume re-arms it."""
    wf_id = _make(eng)
    assert eng.add_event_trigger(wf_id, "email.received")["ok"] is True

    # Baseline fire so count/last_fired exist before pausing.
    assert eng.fire_event("email.received", {"n": 1}) == [wf_id]
    trig = eng.get_event_triggers()[wf_id]
    assert trig["trigger_count"] == 1
    assert trig["last_fired_at"] is not None

    off = eng.set_event_trigger_enabled(wf_id, False)
    assert off["ok"] is True and off["trigger"]["enabled"] is False

    # A matching event while paused changes nothing at all.
    assert eng.fire_event("email.received", {"n": 2}) == []
    trig = eng.get_event_triggers()[wf_id]
    assert trig["trigger_count"] == 1
    assert trig["last_fired_at"] == eng.get_event_triggers()[wf_id]["last_fired_at"]
    assert len(eng.get_executions(wf_id)) == 1  # only the baseline run

    # Resume re-arms: the next matching event fires again.
    assert eng.set_event_trigger_enabled(wf_id, True)["ok"] is True
    assert eng.fire_event("email.received", {"n": 3}) == [wf_id]
    assert eng.get_event_triggers()[wf_id]["trigger_count"] == 2


def test_event_pause_keeps_topic_and_match(eng: WorkflowEngine) -> None:
    """Pause is not destructive: topic, match keys, and history survive."""
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "file.changed", {"glob": "**/*.py"})
    eng.set_event_trigger_enabled(wf_id, False)

    trig = eng.get_event_triggers()[wf_id]
    assert trig["event"] == "file.changed"
    assert trig["match"] == {"glob": "**/*.py"}

    # Non-matching-topic events never fired it either — control check.
    assert eng.fire_event("email.received", {}) == []


def test_event_pause_persists_across_restart(workflow_state: Path) -> None:
    eng = WorkflowEngine()
    wf_id = _make(eng)
    eng.add_event_trigger(wf_id, "email.received")
    eng.set_event_trigger_enabled(wf_id, False)

    eng2 = WorkflowEngine()
    assert eng2.get_event_triggers()[wf_id]["enabled"] is False
    assert eng2.fire_event("email.received", {}) == []


def test_event_setter_unknown_workflow(eng: WorkflowEngine) -> None:
    res = eng.set_event_trigger_enabled("wf_nobody", True)
    assert res["ok"] is False
    assert "reason" in res


async def test_event_pause_resume_route_round_trip(
    client, _patched_engine: WorkflowEngine
) -> None:
    wf_id = _make(_patched_engine, "pause route flow")
    base = f"/api/v1/enhanced/workflows/{wf_id}"

    r = await client.put(
        f"{base}/event-trigger", json={"event": "email.received"}
    )
    assert r.status_code == 200, r.text

    r = await client.put(f"{base}/event-trigger/enabled", json={"enabled": False})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True and body["trigger"]["enabled"] is False

    r = await client.put(f"{base}/event-trigger/enabled", json={"enabled": True})
    assert r.status_code == 200 and r.json()["trigger"]["enabled"] is True


async def test_event_pause_route_unknown_workflow(
    client, _patched_engine: WorkflowEngine
) -> None:
    r = await client.put(
        "/api/v1/enhanced/workflows/wf_missing/event-trigger/enabled",
        json={"enabled": False},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is False
    assert "reason" in r.json()
