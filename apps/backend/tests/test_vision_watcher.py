"""VisionWatcher tests (Phase 1 extension, decisions.md #62): DASH's
autonomous eyes, fully hermetic — fake camera, fake recognizer, fake
brain, fake bus, isolated audit dir, fake clock for cooldowns.

Proves the honesty contract: a recognized person is only ever named when
the recognizer matched them; every degraded state (no camera, missing
models, undecodable frame) keeps its named cause verbatim; cooldowns
bound repetition without hiding the scene from the cycle record; failed
delivery to the brain is visible, not lost; and a dead camera backs the
poll off instead of being hammered.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

import pytest

import dash_backend.vision.watcher as watcher_mod
from dash_backend.vision.recognition import Detection, VisionResult
from dash_backend.vision.watcher import VisionWatcher
from dash_backend.vision.camera_vision import CaptureResult

try:
    from PIL import Image  # noqa: F401

    _PIL = True
except ImportError:  # pragma: no cover
    _PIL = False

pytestmark = pytest.mark.skipif(
    not _PIL, reason="Pillow not installed — the watch pipeline decodes real images"
)


@pytest.fixture(autouse=True)
def _isolated_watcher_config(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    """No test may read or write the user's real watcher config file."""
    monkeypatch.setenv("DASH_WATCHER_CONFIG", str(tmp_path / "watcher_config.json"))
    yield


# ── Fakes ────────────────────────────────────────────────────────────────


class FakeCamera:
    def __init__(self, result: CaptureResult) -> None:
        self.result = result
        self.calls = 0

    async def capture_result(self, camera_id: int = 0) -> CaptureResult:
        self.calls += 1
        return self.result


class FakeFaceService:
    """Stands in for FaceRecognitionService at analyze_frame's contract."""

    def __init__(self, result: VisionResult) -> None:
        self.result = result
        self.calls = 0

    def analyze_frame(
        self, rgb: Any, include_objects: Optional[Any] = None
    ) -> VisionResult:
        self.calls += 1
        return self.result


class FakeBrain:
    def __init__(self) -> None:
        self.observations: list[dict[str, Any]] = []

    def add_observation(self, entry: dict[str, Any]) -> None:
        self.observations.append(entry)


class BrokenBrain:
    def add_observation(self, entry: dict[str, Any]) -> None:
        raise RuntimeError("brain offline")


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish_sync(
        self, topic: str = "", data: Optional[dict[str, Any]] = None, source: str = ""
    ) -> None:
        self.published.append((topic, data or {}))


class FakeAudit:
    def __init__(self) -> None:
        self.entries: list[dict[str, Any]] = []

    def log(self, **kw: Any) -> None:
        self.entries.append(kw)


@pytest.fixture()
def _isolated_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    """VisionWatcher must never write the repo's real audit directory."""
    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit_logs"))
    monkeypatch.setattr(audit_mod, "_audit_service", None)
    yield


def _make_watcher(
    monkeypatch: pytest.MonkeyPatch,
    result: CaptureResult,
    vision: VisionResult,
    **kw: Any,
) -> tuple[VisionWatcher, FakeCamera, FakeBrain, FakeBus, FakeAudit]:
    """Watcher with every seam faked; audit isolated to a temp dir."""
    import dash_backend.services.audit_logs as audit_mod

    camera = FakeCamera(result)
    brain, bus, audit = FakeBrain(), FakeBus(), FakeAudit()
    w = VisionWatcher(
        camera=camera,
        recognizer=FakeFaceService(vision),
        brain=brain,
        bus=bus,
        **kw,
    )
    monkeypatch.setattr(audit_mod, "get_audit_service", lambda: audit)
    return w, camera, brain, bus, audit


def _seen_result(name: str = "Alice", sim: float = 0.91) -> VisionResult:
    return VisionResult(
        backend="onnx",
        faces=[
            {
                "box": [10, 10, 100, 100],
                "confidence": 0.95,
                "match": {
                    "person_id": "person_123",
                    "name": name,
                    "similarity": sim,
                },
            }
        ],
        persons=[
            {
                "person_id": "person_123",
                "name": name,
                "similarity": sim,
                "box": [10, 10, 100, 100],
            }
        ],
    )


def _ok_frame() -> CaptureResult:
    """A real, decodable PNG — _analyze runs the genuine decode path."""
    from tests.test_vision_recognition import _make_image, _png_bytes

    return CaptureResult(frame=_png_bytes(_make_image()))


# ── Recognition events ───────────────────────────────────────────────────


async def test_recognized_person_is_reported_through_brain_bus_and_audit(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())

    cycle = await w.run_cycle()

    assert cycle["ok"] is True
    assert cycle["persons"] == ["Alice"]
    kinds = [e["kind"] for e in cycle["events"]]
    assert kinds == ["person_seen"]
    event = cycle["events"][0]
    assert "Recognized Alice on camera (similarity 0.91)" in event["message"]
    # the report reaches all three channels, and says so honestly
    assert event["delivered"] == {"brain": True, "bus": True, "audit": True}
    assert brain.observations and brain.observations[0]["kind"] == "person_seen"
    assert brain.observations[0]["source"] == "vision_watcher"
    assert bus.published and bus.published[0][0] == "vision.person_seen"
    assert bus.published[0][1]["name"] == "Alice"
    assert any(e["event_type"] == "VISION_WATCH" for e in audit.entries)
    # the watcher remembers who was seen
    assert w.get_status()["persons_seen"][0]["name"] == "Alice"
    assert w.get_status()["persons_seen"][0]["count"] == 1


async def test_repeats_are_cooled_down_but_cycle_record_stays_honest(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())

    first = await w.run_cycle()
    second = await w.run_cycle()

    assert len(first["events"]) == 1
    # second cycle: same person, within cooldown → suppressed for the
    # brain/bus/audit (no flood), but the cycle still recorded the scene
    assert second["events"] == []
    assert second["persons"] == ["Alice"]
    assert second["ok"] is True
    assert len(brain.observations) == 1  # no duplicate delivery
    assert len(bus.published) == 1
    assert w.get_status()["persons_seen"][0]["count"] == 2  # still counted


async def test_cooldown_expiry_re_reports(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(
        monkeypatch, _ok_frame(), _seen_result(), repeat_cooldown_s=0.0
    )
    await w.run_cycle()
    before = len(brain.observations)
    await w.run_cycle()
    assert len(brain.observations) == before + 1


async def test_unknown_face_is_never_given_a_name(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    vision = VisionResult(
        backend="onnx",
        faces=[
            {
                "box": [0, 0, 50, 50],
                "confidence": 0.9,
                "match": None,
                "match_status": "unknown person",
            }
        ],
        persons=[],
    )
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), vision)

    cycle = await w.run_cycle()

    assert cycle["persons"] == []
    event = cycle["events"][0]
    assert event["kind"] == "unknown_person"
    assert "did not match anyone enrolled" in event["message"]
    assert "no identity is being guessed" in event["message"]


async def test_face_with_no_enrollments_says_so(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    vision = VisionResult(
        backend="onnx",
        faces=[
            {
                "box": [0, 0, 50, 50],
                "confidence": 0.9,
                "match": None,
                "match_status": "no persons enrolled",
            }
        ],
    )
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), vision)

    cycle = await w.run_cycle()

    assert cycle["events"][0]["kind"] == "unknown_person"
    assert "no one is enrolled yet" in cycle["events"][0]["message"]
    assert "camera/enroll" in cycle["events"][0]["message"]


async def test_object_only_scene_reports_objects(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    vision = VisionResult(
        backend="onnx",
        objects=[
            Detection(name="laptop", confidence=0.87, box=[0, 0, 10, 10]),
            Detection(name="chair", confidence=0.72, box=[5, 5, 15, 15]),
        ],
    )
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), vision)

    cycle = await w.run_cycle()

    event = cycle["events"][0]
    assert event["kind"] == "scene"
    assert "laptop (0.87)" in event["message"]
    assert "chair (0.72)" in event["message"]


# ── Degraded states keep their named cause ───────────────────────────────


async def test_camera_failure_is_reported_verbatim(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    cap = CaptureResult(
        frame=None,
        error="no camera available (device absent or busy)",
        hint="connect a camera or free it from other apps",
    )
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, cap, VisionResult())

    cycle = await w.run_cycle()

    assert cycle["ok"] is False
    assert cycle["consecutive_failures"] == 1
    event = cycle["events"][0]
    assert event["kind"] == "camera_unavailable"
    assert "no camera available (device absent or busy)" in event["message"]
    assert event["detail"]["hint"] == "connect a camera or free it from other apps"
    assert w._recognizer.calls == 0  # never pretends to analyze a failed capture


async def test_missing_models_are_reported_as_watch_degraded(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    vision = VisionResult(backend="none", reason="detector: model missing: /x/y.onnx")
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), vision)

    cycle = await w.run_cycle()

    event = cycle["events"][0]
    assert event["kind"] == "watch_degraded"
    assert "model missing" in event["message"]


async def test_recovery_after_failures_is_announced_once(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    class FlakyCamera(FakeCamera):
        def __init__(self) -> None:
            super().__init__(CaptureResult(frame=None, error="camera busy"))
            self.n = 0

        async def capture_result(self, camera_id: int = 0) -> CaptureResult:
            self.n += 1
            if self.n <= 2:
                return CaptureResult(frame=None, error="camera busy")
            return _ok_frame()

    camera = FlakyCamera()
    w = VisionWatcher(camera=camera, recognizer=FakeFaceService(_seen_result()))

    await w.run_cycle()
    await w.run_cycle()
    cycle = await w.run_cycle()

    assert cycle["ok"] is True
    kinds = [e["kind"] for e in cycle["events"]]
    assert kinds == ["watch_recovered", "person_seen"]
    assert cycle["consecutive_failures"] == 0


# ── Loop behavior: backoff, resilience, status ───────────────────────────


async def test_failure_backoff_doubles_and_caps(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, *_ = _make_watcher(
        monkeypatch,
        CaptureResult(frame=None, error="camera busy"),
        VisionResult(),
        interval_seconds=30.0,
    )
    assert w._current_interval() == 30.0
    for _ in range(3):
        await w.run_cycle()
    assert w._current_interval() == pytest.approx(30.0 * 8)
    for _ in range(10):
        await w.run_cycle()
    assert w._current_interval() == pytest.approx(30.0 * 32)  # capped
    # recovery resets it
    camera2 = FakeCamera(_ok_frame())
    w2 = VisionWatcher(
        camera=camera2, recognizer=FakeFaceService(_seen_result()), interval_seconds=30.0
    )
    await w2.run_cycle()
    assert w2._current_interval() == 30.0


def test_interval_has_a_floor() -> None:
    assert VisionWatcher(interval_seconds=0.5)._interval == 5.0


async def test_loop_survives_cycle_exceptions_and_stops_cleanly(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())
    calls = {"n": 0}
    real_cycle = w.run_cycle

    async def flaky() -> dict[str, Any]:
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return await real_cycle()

    w.run_cycle = flaky  # type: ignore[method-assign]
    w._interval = 0.05  # run the real loop fast; production default is 30s
    await w.start()
    # Poll to a deadline instead of a fixed sleep: after the first cycle
    # raises, the loop applies failure backoff (2× the interval), so a
    # fixed sleep can miss the second cycle under load.
    deadline = time.monotonic() + 5.0
    while calls["n"] < 2 and time.monotonic() < deadline:
        await asyncio.sleep(0.02)
    assert w.running
    await w.stop()
    assert not w.running
    assert calls["n"] >= 2  # the exception did not kill the loop


async def test_broken_brain_does_not_lose_the_event(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())
    w._brain = BrokenBrain()

    cycle = await w.run_cycle()

    event = cycle["events"][0]
    assert event["delivered"]["brain"] is False
    assert event["delivered"]["bus"] is True  # other channels still got it
    assert event["delivered"]["audit"] is True


async def test_scan_now_and_status(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())
    status = w.get_status()
    assert status["running"] is False
    assert status["cycles"] == 0
    await w.scan_now()
    status = w.get_status()
    assert status["cycles"] == 1
    assert status["events_total"] == 1
    assert status["last_cycle"]["ok"] is True
    assert status["recent_events"][-1]["kind"] == "person_seen"


# ── The real brain seam ──────────────────────────────────────────────────


async def test_real_agent_core_receives_observations_into_working_memory(
    monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    """The contract end-to-end: the watcher's report lands in the same
    memory context DASH reasons from — not a side channel."""
    from dash_backend.autonomous.agent_core import AgentCore

    core = AgentCore()
    w = VisionWatcher(
        camera=FakeCamera(_ok_frame()),
        recognizer=FakeFaceService(_seen_result()),
        brain=core,
    )

    await w.run_cycle()

    memory = core.get_working_memory()
    assert len(memory) == 1
    entry = memory[0]
    assert entry["goal"] == "observation"
    assert entry["source"] == "vision_watcher"
    assert entry["kind"] == "person_seen"
    assert "Alice" in entry["message"]


# ── Routes ───────────────────────────────────────────────────────────────


async def test_watch_status_route(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w, camera, brain, bus, audit = _make_watcher(monkeypatch, _ok_frame(), _seen_result())
    monkeypatch.setattr(watcher_mod, "_watcher", w)

    r = await client.get("/api/v1/vision/watch/status")
    assert r.status_code == 200
    body = r.json()
    assert body["available"] is True
    assert body["running"] is False
    assert body["cooldown_seconds"] == 600.0


async def test_watch_scan_now_route_reports_degradation_honestly(
    client, monkeypatch: pytest.MonkeyPatch, _isolated_audit: None
) -> None:
    w = VisionWatcher(
        camera=FakeCamera(
            CaptureResult(frame=None, error="no camera available (device absent or busy)")
        )
    )
    monkeypatch.setattr(watcher_mod, "_watcher", w)

    r = await client.post("/api/v1/vision/watch/scan-now")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is False
    assert "no camera available" in body["events"][0]["message"]


async def test_watch_routes_reject_anonymous(
    app, monkeypatch: pytest.MonkeyPatch
) -> None:
    from httpx import AsyncClient, ASGITransport

    monkeypatch.setattr(watcher_mod, "_watcher", VisionWatcher())
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as anon:
        r1 = await anon.get("/api/v1/vision/watch/status")
        r2 = await anon.post("/api/v1/vision/watch/scan-now")
    assert r1.status_code == 401
    assert r2.status_code == 401
