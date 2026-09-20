"""WebSocket trigger pushes (decisions.md #80).

The Triggers tab polls every 5 s (#76); pushes deliver fires and
pause/resume changes the moment they happen over the EXISTING /ws
connection. What is under test:

- snapshot honesty: the payload is the engine's own state, sections
  present only for triggers that exist, unknown workflow -> no push,
  webhook secret never included,
- emission: fire_webhook / fire_event and the three pause/resume
  setters all push; paused/failed paths push nothing,
- delivery: a real WS client over the real /ws endpoint receives the
  push, fired from a foreign thread (the scheduler's to_thread shape),
- lifecycle: a dead socket is pruned, not fanned to forever,
- honesty: a push failure never breaks the fire (the poll reconciles).

Sync tests have no running loop, so registration happens without one
and the push service's documented fallback delivers synchronously —
the same semantics a standalone script sees. The real-socket test
exercises the production shape: app loop in the TestClient portal
thread, fire from the test thread, call_soon_threadsafe marshalling.
"""

from __future__ import annotations

import queue
import threading
import time
from pathlib import Path

import pytest

import dash_backend.services.trigger_push as tp
from dash_backend.services.workflow_builder import WorkflowEngine


@pytest.fixture()
def workflow_state(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Isolated engine state file (same convention as the trigger suites)."""
    state = tmp_path / "wf_state.json"
    monkeypatch.setenv("DASH_WORKFLOW_STATE", str(state))
    return state


@pytest.fixture(autouse=True)
def _clean_registry():
    """Isolate the module-level registry between tests."""
    tp._TRIGGER_CONNECTIONS.clear()
    tp._main_loop = None
    tp._seq = 0
    yield
    tp._TRIGGER_CONNECTIONS.clear()
    tp._main_loop = None


class FakeSocket:
    """Records send_json calls; optionally raises (dead socket)."""

    def __init__(self, fail: bool = False):
        self.sent: list[dict] = []
        self.fail = fail
        self.closed = False

    async def send_json(self, payload: dict) -> None:
        if self.fail:
            raise RuntimeError("connection closed")
        self.sent.append(payload)


_NODES = [{"id": "n1", "type": "trigger", "config": {}, "x": 0, "y": 0}]


def _make_workflow(engine: WorkflowEngine, name: str = "push flow") -> str:
    res = engine.create(name, nodes=[dict(n) for n in _NODES], edges=[])
    assert res["ok"] is True
    return res["workflow"]["id"]


# ── Snapshot honesty ──────────────────────────────────────────────────────


def test_webhook_fire_pushes_engine_snapshot(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    hook = engine.add_webhook(wf_id, secret="s3cret")["webhook"]

    ws = FakeSocket()
    tp.register_trigger_socket("owner", ws)

    res = engine.fire_webhook(hook["webhook_id"], "s3cret")
    assert res["ok"] is True

    # No loop exists here: the push service's sync fallback delivers
    # before fire_webhook returns, so the assertion is deterministic.
    assert len(ws.sent) == 1
    push = ws.sent[0]
    assert push["type"] == "trigger.update"
    assert push["seq"] == 1
    snap = push["trigger"]
    assert snap["workflow_id"] == wf_id
    assert snap["webhook"]["webhook_id"] == hook["webhook_id"]
    assert snap["webhook"]["trigger_count"] == 1
    assert snap["webhook"]["enabled"] is True
    assert "secret" not in snap["webhook"], "push must never carry the secret"
    assert "schedule" not in snap, "no schedule attached -> no schedule section"
    assert "event" not in snap, "no event trigger -> no event section"


def test_snapshot_unknown_workflow_is_none(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    assert tp._snapshot(engine, "wf_nobody") is None


def test_push_noop_without_connections(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    hook = engine.add_webhook(wf_id, secret="k")["webhook"]
    # No sockets registered: fire must succeed and push must not explode.
    assert engine.fire_webhook(hook["webhook_id"], "k")["ok"] is True
    assert engine.get_webhooks()[wf_id]["trigger_count"] == 1


# ── Emission points ───────────────────────────────────────────────────────


def test_pause_setters_push(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    engine.add_schedule(wf_id, "0 9 * * *")
    engine.add_webhook(wf_id, secret="k")
    engine.add_event_trigger(wf_id, "email.received")

    ws = FakeSocket()
    tp.register_trigger_socket("owner", ws)

    engine.set_schedule_enabled(wf_id, False)
    engine.set_webhook_enabled(wf_id, False)
    engine.set_event_trigger_enabled(wf_id, False)

    assert len(ws.sent) == 3
    paused = ws.sent[2]["trigger"]
    assert paused["schedule"]["enabled"] is False
    assert paused["webhook"]["enabled"] is False
    assert paused["event"]["enabled"] is False

    # Resume pushes too — same three setters, True side.
    engine.set_schedule_enabled(wf_id, True)
    engine.set_webhook_enabled(wf_id, True)
    engine.set_event_trigger_enabled(wf_id, True)

    assert len(ws.sent) == 6
    resumed = ws.sent[5]["trigger"]
    assert resumed["schedule"]["enabled"] is True
    assert resumed["webhook"]["enabled"] is True
    assert resumed["event"]["enabled"] is True


def test_event_fire_pushes(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    engine.add_event_trigger(wf_id, "email.received")

    ws = FakeSocket()
    tp.register_trigger_socket("owner", ws)

    fired = engine.fire_event("email.received", {"from": "x@y.z"})
    assert fired == [wf_id]

    assert len(ws.sent) == 1
    snap = ws.sent[0]["trigger"]
    assert snap["workflow_id"] == wf_id
    assert snap["event"]["event"] == "email.received"
    assert snap["event"]["trigger_count"] == 1
    assert snap["event"]["enabled"] is True


def test_failed_and_refused_fires_push_nothing(workflow_state: Path) -> None:
    """Honesty: a fire that did NOT happen must not push a change."""
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    hook = engine.add_webhook(wf_id, secret="k")["webhook"]

    ws = FakeSocket()
    tp.register_trigger_socket("owner", ws)

    # Bad secret -> 401 -> no count change -> no push.
    engine.fire_webhook(hook["webhook_id"], "wrong")
    assert ws.sent == []

    # Paused webhook -> 409 -> no push. Pause AND resume are both real
    # changes, so both push; neither changes the count.
    engine.set_webhook_enabled(wf_id, False)
    engine.set_webhook_enabled(wf_id, True)
    engine.fire_webhook(hook["webhook_id"], "wrong")  # still no push

    assert len(ws.sent) == 2, f"only the pause/resume may push: {ws.sent}"
    assert ws.sent[0]["trigger"]["webhook"]["enabled"] is False
    assert ws.sent[1]["trigger"]["webhook"]["enabled"] is True
    assert ws.sent[1]["trigger"]["webhook"]["trigger_count"] == 0


def test_push_failure_never_breaks_the_fire(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    hook = engine.add_webhook(wf_id, secret="k")["webhook"]

    ws = FakeSocket(fail=True)
    tp.register_trigger_socket("owner", ws)

    result = engine.fire_webhook(hook["webhook_id"], "k")
    assert result["ok"] is True, "a dead socket must not fail the fire"
    assert engine.get_webhooks()[wf_id]["trigger_count"] == 1
    assert "owner" not in tp._TRIGGER_CONNECTIONS, "dead socket is pruned"


def test_dead_socket_pruned(workflow_state: Path) -> None:
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    engine.add_webhook(wf_id, secret="k")
    ws = FakeSocket(fail=True)
    tp.register_trigger_socket("owner", ws)
    assert tp._TRIGGER_CONNECTIONS.get("owner")

    engine.set_webhook_enabled(wf_id, False)  # triggers a push -> prune

    assert "owner" not in tp._TRIGGER_CONNECTIONS, "dead socket must be pruned"
    # A later push must not touch the pruned socket again.
    engine.set_webhook_enabled(wf_id, True)
    assert ws.sent == []


def test_push_from_other_thread(workflow_state: Path) -> None:
    """The scheduler fires via asyncio.to_thread: with no app loop
    registered the push delivers synchronously inside the worker thread
    (the fallback's documented semantics); the real-socket test below
    exercises the production call_soon_threadsafe marshalling."""
    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    hook = engine.add_webhook(wf_id, secret="k")["webhook"]

    ws = FakeSocket()
    tp.register_trigger_socket("owner", ws)

    def fire_in_thread() -> None:
        engine.fire_webhook(hook["webhook_id"], "k")

    t = threading.Thread(target=fire_in_thread)
    t.start()
    t.join(5)
    assert not t.is_alive()

    assert any(
        p["type"] == "trigger.update" and p["trigger"]["webhook"]["trigger_count"] == 1
        for p in ws.sent
    ), f"push from foreign thread must arrive: {ws.sent}"


# ── Real /ws socket, real app, real cross-thread delivery ─────────────────


def test_real_ws_socket_receives_trigger_update(workflow_state: Path) -> None:
    """End to end, hermetic: a real authenticated WebSocket handshake to
    /api/v1/ws (device token, like the desktop client — the pattern the
    existing test_websocket.py suite pins), a webhook fired from the
    TEST thread while the app loop lives in the TestClient portal
    thread, and the trigger.update message actually read off the socket.
    Bounded wait, no sleeps."""
    from fastapi.testclient import TestClient

    from dash_backend.main import app
    from tests.conftest import _TEST_TOKEN

    engine = WorkflowEngine()
    wf_id = _make_workflow(engine)
    engine.add_schedule(wf_id, "0 9 * * *")
    hook = engine.add_webhook(wf_id, secret="route-secret")["webhook"]

    received: queue.Queue = queue.Queue()

    def _reader(sock) -> None:
        try:
            while True:
                received.put(sock.receive_json())
        except Exception:
            received.put({"type": "_socket_closed"})

    with TestClient(app).websocket_connect(f"/api/v1/ws?token={_TEST_TOKEN}") as ws:
        reader = threading.Thread(target=_reader, args=(ws,), daemon=True)
        reader.start()

        # The handshake greets with session.info AFTER registering the
        # socket for pushes — wait for it, then pin the invariant.
        first = received.get(timeout=5)
        assert first["type"] == "session.info", first
        assert any(tp._TRIGGER_CONNECTIONS.values()), (
            "/ws handshake did not register the socket for trigger pushes"
        )

        # Fire from the TEST thread while the app's loop lives in the
        # portal thread — exercises call_soon_threadsafe marshalling.
        engine.fire_webhook(hook["webhook_id"], "route-secret")

        deadline = time.time() + 10
        got: dict | None = None
        while time.time() < deadline:
            try:
                msg = received.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg.get("type") == "trigger.update":
                got = msg
                break
            if msg.get("type") == "_socket_closed":
                break  # connection died before the push arrived

    assert got is not None, "no trigger.update within 10s on a real /ws socket"
    trig = got["trigger"]
    assert trig["workflow_id"] == wf_id
    assert trig["webhook"]["trigger_count"] == 1
    assert trig["schedule"]["cron"] == "0 9 * * *"
    assert "secret" not in trig["webhook"]
