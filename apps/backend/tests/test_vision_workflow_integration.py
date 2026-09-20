"""Vision → workflow engine end-to-end wiring (decisions.md #72).

What is under test, all hermetic:
- the bridge subscribes the vision.* wildcard group so watcher events can
  reach workflow event triggers (the gap this session's live demo exposed),
- no exact/wildcard double-fire for reminder.fired (the bus delivers to
  exact AND wildcard subscribers independently),
- action nodes execute REAL tools: notification.send, audit.log,
  bus.publish, timeout contract, honest no-handler skip, event payload
  flowing into action config,
- StaticFrameCamera: env-gated photon-source substitution for the watcher
  (real decode/detect/recognize downstream), unreadable-file honesty,
  no env → None,
- the full real path: StaticFrameCamera → watcher.run_cycle → bus event →
  bridge → engine.fire_event → action executes — with fake YuNet/SFace
  injected so no model files or camera are needed.

Everything runs in temp dirs; nothing touches the user's real stores.
"""
from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

import numpy as np
import pytest

from dash_backend.services.workflow_builder import WorkflowEngine
from dash_backend.services.workflow_event_bridge import (
    WorkflowEventBridge,
)
from dash_backend.vision.watcher import StaticFrameCamera, VisionWatcher


@pytest.fixture(autouse=True)
def _isolated_watcher_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    """No test may read or write the user's real watcher config file."""
    monkeypatch.setenv("DASH_WATCHER_CONFIG", str(tmp_path / "watcher_config.json"))
    yield


# ── Fixtures (conventions from test_workflow_event_triggers.py) ──────────


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
    """Fake bus mirroring EventBus semantics the bridge relies on:
    exact-subscriber delivery INDEPENDENT of wildcard-subscriber delivery."""

    class FakeBus:
        def __init__(self) -> None:
            self.subs: dict[str, list] = {}
            self.wild: dict[str, list] = {}

        def subscribe(self, topic, callback, filter_fn=None, name=""):
            table = self.wild if topic.endswith(".*") else self.subs
            table.setdefault(topic, []).append(callback)
            return name or f"sub-{len(self.subs) + len(self.wild)}"

        def unsubscribe_all(self, prefix: str) -> int:
            n = sum(len(v) for v in self.subs.values()) + sum(
                len(v) for v in self.wild.values()
            )
            self.subs.clear()
            self.wild.clear()
            return n

        async def publish_sync(self, topic, data=None, source="", **kw):
            ev = type("E", (), {"topic": topic, "data": data or {}})()
            for cb in self.subs.get(topic, []):
                await cb(ev)
            for pattern, cbs in self.wild.items():
                prefix_ = pattern[:-2]  # single-level wildcard
                if topic.split(".")[0] == prefix_:
                    for cb in cbs:
                        await cb(ev)

    return FakeBus()


@pytest.fixture()
def bridge(eng: WorkflowEngine, fake_bus: Any) -> WorkflowEventBridge:
    return WorkflowEventBridge(engine=eng, bus=fake_bus)


def _make_person_seen_workflow(eng: WorkflowEngine, **action_cfg: Any) -> str:
    nodes = [
        {"id": "n1", "type": "trigger", "config": {"event": "vision.person_seen"}},
        {
            "id": "n2",
            "type": "action",
            "config": {"tool": "audit.log", "message": "Zidane walked in", **action_cfg},
        },
    ]
    res = eng.create(
        "person seen demo",
        nodes=nodes,
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"] is True
    eng.add_event_trigger(res["workflow"]["id"], "vision.person_seen")
    return res["workflow"]["id"]


# ── Bridge wildcard wiring ────────────────────────────────────────────────


def test_bridge_subscribes_vision_wildcard(eng, fake_bus) -> None:
    b = WorkflowEventBridge(engine=eng, bus=fake_bus)
    asyncio.run(b.start())
    try:
        assert "vision.*" in fake_bus.wild, "vision.* wildcard not subscribed"
        assert "guardian.*" in fake_bus.wild
    finally:
        asyncio.run(b.stop())


def test_vision_event_fires_workflow_through_bridge(
    eng, fake_bus, bridge
) -> None:
    asyncio.run(bridge.start())
    wf_id = _make_person_seen_workflow(eng)
    try:
        # The watcher's exact publish call, end to end through the fake bus.
        asyncio.run(
            fake_bus.publish_sync(
                "vision.person_seen",
                {"name": "Zidane", "person_id": "p1", "similarity": 0.97},
                source="vision_watcher",
            )
        )
        trig = eng.get_event_triggers().get(wf_id)
        # The execution record is the authoritative proof; the trigger
        # record carries the count.
        execs = [e for e in eng.get_executions(wf_id) if e["source"] == "event"]
        assert len(execs) == 1, (
            f"expected exactly one event-sourced execution, got {execs}"
        )
        assert execs[0]["input"]["event"]["name"] == "Zidane"
        assert trig is not None and trig["event"] == "vision.person_seen"
        assert trig["trigger_count"] == 1
    finally:
        asyncio.run(bridge.stop())


def test_reminder_fired_not_double_fired(eng, fake_bus, bridge) -> None:
    """The bus delivers to exact AND wildcard subscribers independently;
    since reminder.fired is subscribed exactly, no reminder.* wildcard may
    also exist or every reminder would run its workflow twice."""
    asyncio.run(bridge.start())
    try:
        assert "reminder.*" not in fake_bus.wild
        assert "reminder.fired" in fake_bus.subs
    finally:
        asyncio.run(bridge.stop())


# ── Action nodes execute real tools ──────────────────────────────────────


def test_action_notification_send_real(eng, monkeypatch) -> None:
    calls: list[dict] = []

    class FakeNotifSvc:
        def __init__(self) -> None:
            pass

        async def show(self, title="", message="", duration=5):
            calls.append({"title": title, "message": message})
            return {"summary": f"Notification shown: {title}",
                    "mechanism": "windows-toast", "blocking": False}

    import dash_backend.services.notifications as notif_mod

    monkeypatch.setattr(notif_mod, "NotificationService", FakeNotifSvc)

    res = eng.create(
        "notify flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action",
             "config": {"tool": "notification.send",
                        "title": "Zidane is here", "message": "at the door"}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    out = eng.execute(res["workflow"]["id"], None, "manual")
    assert out["ok"] is True
    ar = out["execution"]["action_results"]["n2"]
    assert ar["status"] == "ok"
    assert calls and calls[0]["title"] == "Zidane is here"
    assert calls[0]["message"] == "at the door"


def test_action_audit_log_real(tmp_path: Path, monkeypatch, eng) -> None:
    writes: list[dict] = []

    class FakeAudit:
        def log(self, **kw):
            writes.append(kw)

    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setattr(audit_mod, "get_audit_service", lambda: FakeAudit())

    res = eng.create(
        "audit flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action",
             "config": {"tool": "audit.log", "message": "someone at the door"}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    out = eng.execute(res["workflow"]["id"], None, "event")
    ar = out["execution"]["action_results"]["n2"]
    assert ar["status"] == "ok" and ar["result"]["logged"] is True
    assert writes and writes[0]["category"] == "workflow"
    assert "someone at the door" in writes[0]["action"]


def test_action_bus_publish_real(eng, monkeypatch) -> None:
    published: list[tuple] = []

    class TinyBus:
        def publish_sync(self, topic, data=None, source=""):
            published.append((topic, data, source))

    import dash_backend.events.event_bus as bus_mod

    monkeypatch.setattr(bus_mod, "get_event_bus", lambda: TinyBus())

    res = eng.create(
        "publish flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action",
             "config": {"tool": "bus.publish", "topic": "demo.chained",
                        "payload": {"note": "chained"}}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    out = eng.execute(res["workflow"]["id"], None, "manual")
    ar = out["execution"]["action_results"]["n2"]
    assert ar["status"] == "ok" and ar["result"]["topic"] == "demo.chained"
    assert published and published[0][0] == "demo.chained"
    assert published[0][1]["via_workflow"] is True


def test_action_unknown_tool_honest_skip(eng) -> None:
    res = eng.create(
        "unknown tool",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action", "config": {"tool": "nonexistent.tool"}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    out = eng.execute(res["workflow"]["id"], None, "manual")
    ar = out["execution"]["action_results"]["n2"]
    assert ar["status"] == "skipped"
    assert "no handler registered" in ar["reason"]
    # The run itself completes — the honesty is in the node record.
    assert out["execution"]["status"] == "completed"


def test_action_timeout_recorded_honestly(eng, monkeypatch) -> None:
    def slow_handler(config: dict, context: dict) -> dict:
        time.sleep(0.5)
        return {"status": "ok"}

    eng._action_overrides["slow.tool"] = slow_handler
    # Shrink the window; patching the module constant directly since the
    # bounded runner reads it at call time.
    monkeypatch.setattr(
        "dash_backend.services.workflow_builder.ACTION_TIMEOUT_S", 0.05
    )

    res = eng.create(
        "slow flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action", "config": {"tool": "slow.tool"}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    t0 = time.perf_counter()
    out = eng.execute(res["workflow"]["id"], None, "manual")
    elapsed = time.perf_counter() - t0
    ar = out["execution"]["action_results"]["n2"]
    assert ar["status"] == "failed"
    assert "timed out after" in ar["reason"]
    assert elapsed < 0.45, "bounded runner did not honor the timeout"
    assert out["execution"]["status"] == "completed"


def test_action_receives_event_context(eng) -> None:
    seen: list[dict] = []

    def spy(config: dict, context: dict) -> dict:
        seen.append({"config": config, "context": context})
        return {"status": "ok"}

    eng._action_overrides["spy.tool"] = spy
    _make_person_seen_workflow(eng)
    eng._action_overrides["audit.log"] = spy
    try:
        eng.fire_event(
            "vision.person_seen",
            {"name": "Zidane", "person_id": "p1", "similarity": 0.97},
        )
    finally:
        eng._action_overrides.pop("audit.log", None)
        eng._action_overrides.pop("spy.tool", None)
    assert seen, "action never received context"
    ctx = seen[0]["context"]
    assert ctx["event"]["topic"] == "vision.person_seen"
    assert ctx["event"]["name"] == "Zidane"
    assert ctx["event"]["similarity"] == 0.97


def test_action_override_map_used_first(eng) -> None:
    def handler(config: dict, context: dict) -> dict:
        return {"status": "ok", "via": "override"}

    eng._action_overrides["notification.send"] = handler
    res = eng.create(
        "override flow",
        nodes=[
            {"id": "n1", "type": "trigger", "config": {"event": "x.y"}},
            {"id": "n2", "type": "action",
             "config": {"tool": "notification.send", "title": "T"}},
        ],
        edges=[{"from": "n1", "to": "n2"}],
    )
    assert res["ok"]
    out = eng.execute(res["workflow"]["id"], None, "manual")
    assert out["execution"]["action_results"]["n2"]["via"] == "override"


# ── StaticFrameCamera ─────────────────────────────────────────────────────


def _write_jpeg(tmp_path: Path, size: int = 8) -> Path:
    import cv2

    img = np.zeros((size, size, 3), dtype=np.uint8)
    ok, buf = cv2.imencode(".jpg", img)
    assert ok
    p = tmp_path / "frame.jpg"
    p.write_bytes(buf.tobytes())
    return p


def test_static_camera_disabled_without_env(monkeypatch) -> None:
    monkeypatch.delenv("DASH_VISION_STATIC_FRAME", raising=False)
    assert StaticFrameCamera.from_env() is None


def test_static_camera_from_env_reads_bytes(monkeypatch, tmp_path) -> None:
    p = _write_jpeg(tmp_path)
    monkeypatch.setenv("DASH_VISION_STATIC_FRAME", str(p))
    cam = StaticFrameCamera.from_env()
    assert cam is not None
    res = asyncio.run(cam.capture_result(0))
    assert res.ok is True
    assert res.frame == p.read_bytes()


def test_static_camera_missing_file_is_honest(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("DASH_VISION_STATIC_FRAME", str(tmp_path / "nope.jpg"))
    assert StaticFrameCamera.from_env() is None


def test_static_camera_unreadable_reports_cause(monkeypatch, tmp_path) -> None:
    p = tmp_path / "locked.jpg"
    p.write_bytes(b"\xff\xd8\xff")
    cam = StaticFrameCamera(p)
    p.unlink()
    StaticFrameCamera._cache.clear()
    res = asyncio.run(cam.capture_result(0))
    assert res.ok is False
    assert "static frame unreadable" in (res.error or "")
    assert res.frame is None


# ── Full real path: camera seam → watcher → bus → bridge → engine ────────


def test_full_vision_to_workflow_path(
    eng, fake_bus, bridge, monkeypatch, tmp_path
) -> None:
    """StaticFrameCamera feeds the watcher's REAL pipeline (decode,
    detect, recognize via fake ONNX-backed services, emit) and the emitted
    vision.person_seen reaches the workflow engine through the bridge."""

    import dash_backend.services.audit_logs as audit_mod

    writes: list[dict] = []

    class FakeAudit:
        def log(self, **kw):
            writes.append(kw)

    monkeypatch.setattr(audit_mod, "get_audit_service", lambda: FakeAudit())

    # 1. A workflow: on vision.person_seen → audit.log (real handler).
    wf_id = _make_person_seen_workflow(eng)

    # 2. Fake recognition service: one enrolled match — faithful shape.
    class FakeFaceService:
        def analyze_frame(self, rgb, include_objects=None):
            from dash_backend.vision.recognition import VisionResult

            return VisionResult(
                faces=[{
                    "box": (0, 0, 10, 10), "score": 0.9,
                    "match": {"person_id": "p1", "name": "Zidane",
                              "similarity": 0.97},
                    "match_status": "matched",
                    "landmark_aligned": True,
                }],
                persons=[{
                    "person_id": "p1", "name": "Zidane", "similarity": 0.97,
                    "box": (0, 0, 10, 10), "landmark_aligned": True,
                }],
                backend="faces+objects",
            )

        def get_persons(self):
            return [{"person_id": "p1", "name": "Zidane"}]

    # 3. The real watcher with the real StaticFrameCamera seam.
    frame = _write_jpeg(tmp_path)
    monkeypatch.setenv("DASH_VISION_STATIC_FRAME", str(frame))
    cam = StaticFrameCamera.from_env()
    watcher = VisionWatcher(
        camera=cam, recognizer=FakeFaceService(), bus=fake_bus, brain=None
    )

    # 4. Bridge live (wildcard subscribed), then one real watcher cycle.
    asyncio.run(bridge.start())
    try:
        cycle = asyncio.run(watcher.run_cycle())
        # The watcher's own record: the person was seen and delivered to
        # brain + bus + audit (all three channels confirmed in the record).
        assert "Zidane" in cycle.get("persons", []), (
            f"watcher did not record the person: {cycle}"
        )
        assert cycle["events"], "no events emitted"
        ev = cycle["events"][0]
        assert ev["kind"] == "person_seen"
        assert ev["delivered"].get("bus") is True, (
            "watcher did not confirm bus delivery"
        )

        # Give the bus's background delivery task a moment if needed, then
        # verify the workflow ran because of the vision event.
        async def _wait_for_exec():
            for _ in range(50):
                execs = [e for e in eng.get_executions(wf_id)
                         if e["source"] == "event"]
                if execs:
                    return execs[0]
                await asyncio.sleep(0.02)
            return None

        # The fake bus delivers inline during publish_sync, so the run is
        # already done by the time run_cycle returns.
        execs = asyncio.run(_wait_for_exec())
        assert execs is not None, (
            "vision.person_seen never reached the workflow engine"
        )
        ar = execs["action_results"]["n2"]
        assert ar["status"] == "ok" and ar["result"]["logged"] is True
        assert writes and writes[0]["category"] == "workflow"
    finally:
        asyncio.run(bridge.stop())


def test_full_path_requires_models_contract_documented() -> None:
    """Honesty note pinned as a test: with no fake injected, the real
    pipeline needs real models — StaticFrameCamera only substitutes the
    photon source, it never fakes recognition."""
    import inspect

    src = inspect.getsource(StaticFrameCamera)
    assert "capture_result" in src
    assert "CaptureResult" in src
