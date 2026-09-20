"""User-configurable vision watcher (decisions.md #73): hermetic tests for
the config contract, per-person notify preferences, and the API routes.

Everything here runs against fakes — no camera, no models, no real
singleton state, no real config file. Proven contracts:

- Config: validated, all-or-nothing, applied to the LIVE watcher (next
  cycle uses it), persisted, and re-applied at boot (survives restart).
- Persistence is corrupt-safe: unreadable or wrong-version files are
  reported and ignored — the watcher boots with defaults, never garbage.
- Per-person notify: opted-out persons stay enrolled and recognized but
  are never reported to brain/bus/audit; opting out does not burn
  cooldown; unknown persons notify (fail open); the pref dies with the
  person record.
- Routes: config GET/PUT and person notify PUT are auth-gated, honest on
  errors, and drive the real singleton machinery.
"""
from __future__ import annotations

import json
from typing import Any, Optional

import pytest

import dash_backend.vision.watcher as watcher_mod
from dash_backend.vision.camera_vision import CaptureResult
from dash_backend.vision.recognition import FaceStore, VisionResult
from dash_backend.vision.watcher import VisionWatcher, WatcherConfigStore


# ── Fakes (mirror tests/test_vision_watcher.py's proven seams) ───────────


class FakeCamera:
    def __init__(self, result: CaptureResult) -> None:
        self.result = result
        self.calls: list[int] = []

    async def capture_result(self, camera_id: int = 0) -> CaptureResult:
        self.calls.append(camera_id)
        return self.result


class FakeFaceService:
    def __init__(self, result: VisionResult) -> None:
        self.result = result
        self._notify: dict[str, bool] = {}

    def analyze_frame(
        self, rgb: Any, include_objects: Optional[Any] = None
    ) -> VisionResult:
        return self.result

    def set_person_notify(self, person_id: str, notify: bool) -> bool:
        self._notify[person_id] = notify
        return True

    def person_notify_flag(self, person_id: str) -> bool:
        return self._notify.get(person_id, True)


class FakeBrain:
    def __init__(self) -> None:
        self.observations: list[dict[str, Any]] = []

    def add_observation(self, entry: dict[str, Any]) -> None:
        self.observations.append(entry)


class FakeBus:
    def __init__(self) -> None:
        self.published: list[tuple[str, dict[str, Any]]] = []

    async def publish_sync(
        self, topic: str = "", data: Optional[dict[str, Any]] = None, source: str = ""
    ) -> None:
        self.published.append((topic, data or {}))


@pytest.fixture()
def _isolated_audit(monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit_logs"))
    monkeypatch.setattr(audit_mod, "_audit_service", None)
    yield


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


def _make_watcher(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Any,
    result: Optional[CaptureResult] = None,
    vision: Optional[VisionResult] = None,
    recognizer: Any = None,
) -> tuple[VisionWatcher, FakeCamera, FakeBrain, FakeBus, Any]:
    """Watcher with every seam faked, config store in a temp dir, audit
    isolated via monkeypatched get_audit_service."""
    import dash_backend.services.audit_logs as audit_mod

    class FakeAudit:
        def __init__(self) -> None:
            self.entries: list[dict[str, Any]] = []

        def log(self, **kw: Any) -> None:
            self.entries.append(kw)

    audit = FakeAudit()
    if result is None:
        # A real decodable frame — the watcher's _analyze decodes bytes for
        # real (same helper the existing vision suite uses).
        from tests.test_vision_recognition import _make_image, _png_bytes

        result = CaptureResult(frame=_png_bytes(_make_image()))
    camera = FakeCamera(result)
    brain, bus = FakeBrain(), FakeBus()
    w = VisionWatcher(
        camera=camera,
        recognizer=recognizer or FakeFaceService(vision or _seen_result()),
        brain=brain,
        bus=bus,
        store_path=tmp_path / "watcher_config.json",
    )
    monkeypatch.setattr(audit_mod, "get_audit_service", lambda: audit)
    return w, camera, brain, bus, audit


# ── Config validation ────────────────────────────────────────────────────


class TestConfigValidation:
    def test_valid_partial_update_applies_and_persists(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure(interval_seconds=7.5)
        assert res["ok"] is True
        assert w.get_config()["interval_seconds"] == 7.5
        # Persisted exactly:
        on_disk = json.loads((tmp_path / "watcher_config.json").read_text())
        assert on_disk["version"] == watcher_mod.WATCHER_CONFIG_VERSION
        assert on_disk["watcher"]["interval_seconds"] == 7.5

    def test_interval_floor_enforced(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure(interval_seconds=0.5)
        assert res["ok"] is False
        assert any("interval_seconds" in e for e in res["errors"])
        assert w.get_config()["interval_seconds"] == watcher_mod.DEFAULT_INTERVAL_S

    def test_all_or_nothing_on_multi_field_failure(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure(interval_seconds=0.5, camera_id=2)
        assert res["ok"] is False
        # camera_id was valid — but nothing applied, and the user is told.
        assert w.get_config()["camera_id"] == 0
        assert any("all-or-nothing" in e for e in res["errors"])
        assert not (tmp_path / "watcher_config.json").exists()

    def test_camera_id_type_and_range(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        for bad in (-1, 99, 2.5, True):
            res = w.configure(camera_id=bad)
            assert res["ok"] is False, f"camera_id={bad!r} must be rejected"
        assert w.get_config()["camera_id"] == 0

    def test_unknown_setting_rejected(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """configure()'s signature makes unknown kwargs a TypeError (Python's
        own guard), so the validator's unknown-key defense is pinned here
        directly — it is the last line if a future caller passes raw dicts."""
        merged, errors = VisionWatcher._validate_config_change(
            {"interval_seconds": 30.0, "repeat_cooldown_s": 600.0, "camera_id": 0},
            {"color": "red"},
        )
        assert any("unknown setting" in e for e in errors)
        assert "color" not in merged

    def test_no_settings_rejected(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure()
        assert res["ok"] is False
        assert res["errors"] == ["no settings provided"]

    def test_zero_cooldown_legal(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """0 cooldown = report every sighting; a legal, honest setting."""
        w, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure(repeat_cooldown_s=0)
        assert res["ok"] is True
        assert w.get_config()["repeat_cooldown_s"] == 0.0


# ── Live-apply: the next cycle actually uses the new values ─────────────


class TestLiveApply:
    @pytest.mark.asyncio
    async def test_new_camera_id_used_by_next_cycle(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, camera, *_ = _make_watcher(monkeypatch, tmp_path)
        res = w.configure(camera_id=3)
        assert res["ok"] is True
        await w.run_cycle()
        assert camera.calls == [3]

    @pytest.mark.asyncio
    async def test_new_cooldown_used_by_next_cycle(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, _camera, _brain, bus, _audit = _make_watcher(monkeypatch, tmp_path)
        w.configure(repeat_cooldown_s=0)
        await w.run_cycle()
        await w.run_cycle()
        person_events = [t for t, _ in bus.published if t == "vision.person_seen"]
        assert len(person_events) == 2  # zero cooldown → every sighting reports

    @pytest.mark.asyncio
    async def test_boot_applies_stored_config(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """The configured shape survives a restart (new instance, same file)."""
        cfg_file = tmp_path / "watcher_config.json"
        w1, *_ = _make_watcher(monkeypatch, tmp_path)
        w1.configure(interval_seconds=11.0, repeat_cooldown_s=45.0, camera_id=2)
        assert cfg_file.exists()

        w2 = VisionWatcher(
            camera=FakeCamera(CaptureResult(frame=b"jpeg")),
            recognizer=FakeFaceService(_seen_result()),
            brain=FakeBrain(),
            bus=FakeBus(),
            store_path=cfg_file,
        )
        assert w2.get_config() == {
            "interval_seconds": 11.0,
            "repeat_cooldown_s": 45.0,
            "camera_id": 2,
            "notify_known_persons": False,
            "notify_cooldown_s": watcher_mod.NOTIFY_COOLDOWN_S,
        }


# ── Persistence is corrupt-safe ──────────────────────────────────────────


class TestConfigStore:
    def test_corrupt_file_reported_and_ignored(self, tmp_path: Any) -> None:
        p = tmp_path / "cfg.json"
        p.write_text("{not json at all", encoding="utf-8")
        st = WatcherConfigStore(p)
        assert st.load() == {}
        assert st.last_error is not None
        # A save repairs the file and clears the error.
        st.save({"interval_seconds": 9.0, "repeat_cooldown_s": 60.0, "camera_id": 0})
        assert st.last_error is None
        assert st.load()["interval_seconds"] == 9.0

    def test_wrong_version_ignored(self, tmp_path: Any) -> None:
        p = tmp_path / "cfg.json"
        p.write_text(
            json.dumps({"version": 99, "watcher": {"camera_id": 7}}), encoding="utf-8"
        )
        st = WatcherConfigStore(p)
        assert st.load() == {}
        assert "version" in st.last_error

    def test_wrong_typed_values_dropped(self, tmp_path: Any) -> None:
        p = tmp_path / "cfg.json"
        p.write_text(
            json.dumps(
                {
                    "version": 1,
                    "watcher": {"camera_id": "front", "interval_seconds": [5]},
                }
            ),
            encoding="utf-8",
        )
        st = WatcherConfigStore(p)
        assert st.load() == {}

    def test_boolean_is_not_a_number(self, tmp_path: Any) -> None:
        p = tmp_path / "cfg.json"
        p.write_text(
            json.dumps({"version": 1, "watcher": {"camera_id": True}}),
            encoding="utf-8",
        )
        st = WatcherConfigStore(p)
        assert st.load() == {}

    def test_missing_file_means_defaults(self, tmp_path: Any) -> None:
        st = WatcherConfigStore(tmp_path / "nope.json")
        assert st.load() == {}
        assert st.last_error is None


# ── Per-person notify preferences ────────────────────────────────────────


class TestPersonNotify:
    @pytest.mark.asyncio
    async def test_opted_out_person_not_reported(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        rec = FakeFaceService(_seen_result())
        rec.set_person_notify("person_123", False)
        w, _camera, brain, bus, audit = _make_watcher(
            monkeypatch, tmp_path, recognizer=rec
        )
        cycle = await w.run_cycle()
        # Still seen — honest cycle record:
        assert cycle["persons"] == ["Alice"]
        # But never reported onward:
        assert brain.observations == []
        assert bus.published == []
        assert audit.entries == []

    @pytest.mark.asyncio
    async def test_opt_out_does_not_burn_cooldown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Opt back in → the next sighting reports immediately (a fresh
        bounded report), because a suppressed sighting never set the key."""
        rec = FakeFaceService(_seen_result())
        rec.set_person_notify("person_123", False)
        w, _c, _b, _bus, _a = _make_watcher(monkeypatch, tmp_path, recognizer=rec)
        await w.run_cycle()
        rec.set_person_notify("person_123", True)
        cycle = await w.run_cycle()
        assert any(
            e["kind"] == "person_seen" for e in cycle["events"]
        )

    @pytest.mark.asyncio
    async def test_unknown_person_fails_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """A person with no stored pref is reported — never silently muted."""
        w, _c, brain, _bus, _a = _make_watcher(monkeypatch, tmp_path)
        await w.run_cycle()
        assert len(brain.observations) == 1
        assert brain.observations[0]["kind"] == "person_seen"

    @pytest.mark.asyncio
    async def test_notify_lookup_failure_fails_open(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """A broken store must not mute people — it notifies."""

        class ExplodingStore(FakeFaceService):
            def person_notify_flag(self, person_id: str) -> bool:
                raise RuntimeError("store wedged")

        w, _c, brain, _bus, _a = _make_watcher(
            monkeypatch, tmp_path, recognizer=ExplodingStore(_seen_result())
        )
        await w.run_cycle()
        assert len(brain.observations) == 1

    @pytest.mark.asyncio
    async def test_emit_double_check_blocks_bypass(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """_emit re-checks the flag for person_seen — a future caller path
        that skips _emit_person cannot outsmart the preference."""

        class HiddenPerson(FakeFaceService):
            """Reports person_seen for someone the store says is opted out,
            via a direct _emit call (the bypass the double-check targets)."""

        rec = FakeFaceService(_seen_result())
        rec.set_person_notify("person_123", False)
        w, _c, brain, _bus, _a = _make_watcher(monkeypatch, tmp_path, recognizer=rec)
        entry = await w._emit(
            "person_seen",
            "Recognized Alice on camera",
            {"person_id": "person_123", "name": "Alice"},
            key="person:person_123",
        )
        assert entry is None
        assert brain.observations == []

    def test_face_store_notify_roundtrip_and_delete_semantics(
        self, tmp_path: Any
    ) -> None:
        store = FaceStore(tmp_path / "faces.json")
        store.add_sample("p1", "Zed", [0.1] * 8)
        assert store.notify_flag("p1") is True  # default: notify
        assert store.set_notify("p1", False) is True
        assert store.notify_flag("p1") is False
        # Persisted:
        on_disk = json.loads((tmp_path / "faces.json").read_text())
        assert on_disk["persons"]["p1"]["notify"] is False
        # Unknown person → False:
        assert store.set_notify("ghost", True) is False
        # The pref dies with the person:
        assert store.remove_person("p1") is True
        assert store.notify_flag("p1") is True  # gone → fail-open default

    def test_list_persons_carries_notify_flag(self, tmp_path: Any) -> None:
        store = FaceStore(tmp_path / "faces.json")
        store.add_sample("p1", "Zed", [0.1] * 8)
        store.set_notify("p1", False)
        listed = store.list_persons()
        assert listed == [
            {"person_id": "p1", "name": "Zed", "samples": 1, "notify": False}
        ]


# ── API routes ───────────────────────────────────────────────────────────


class TestRoutes:
    @pytest.fixture()
    def _route_env(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any):
        """Isolated singletons for route tests: face store, watcher config,
        audit dir — and fresh singletons so nothing leaks between tests."""
        monkeypatch.setenv("DASH_VISION_MODELS", str(tmp_path / "models"))
        monkeypatch.setenv("DASH_WATCHER_CONFIG", str(tmp_path / "watcher_config.json"))
        monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit"))
        import dash_backend.services.audit_logs as audit_mod
        import dash_backend.vision.recognition as rec_mod
        import dash_backend.vision.watcher as watcher_mod

        monkeypatch.setattr(audit_mod, "_audit_service", None)
        monkeypatch.setattr(rec_mod, "_face_service", None)
        # The watcher singleton binds its config store at construction —
        # a stale one would write the previous test's file.
        monkeypatch.setattr(watcher_mod, "_watcher", None)
        yield tmp_path

    def _client(self):
        from fastapi.testclient import TestClient

        from dash_backend.auth.dependencies import get_current_user
        from dash_backend.main import create_app

        app = create_app()
        app.dependency_overrides[get_current_user] = lambda: {"sub": "test"}
        return TestClient(app)

    def test_config_routes_roundtrip(self, _route_env: Any) -> None:
        client = self._client()
        r = client.get("/api/v1/vision/watch/config")
        assert r.status_code == 200
        body = r.json()
        assert body["interval_seconds"] == watcher_mod.DEFAULT_INTERVAL_S
        assert body["limits"]["interval_seconds_min"] == watcher_mod.MIN_INTERVAL_S
        assert "config_file" in body

        r = client.put(
            "/api/v1/vision/watch/config",
            json={"interval_seconds": 12.5, "camera_id": 1},
        )
        assert r.status_code == 200
        assert r.json()["interval_seconds"] == 12.5
        assert r.json()["camera_id"] == 1
        # Persisted:
        on_disk = json.loads(
            (_route_env / "watcher_config.json").read_text(encoding="utf-8")
        )
        assert on_disk["watcher"]["interval_seconds"] == 12.5

        # GET reflects the change live:
        r = client.get("/api/v1/vision/watch/config")
        assert r.json()["interval_seconds"] == 12.5

    def test_config_route_rejects_invalid(self, _route_env: Any) -> None:
        client = self._client()
        r = client.put("/api/v1/vision/watch/config", json={"interval_seconds": 0.1})
        assert r.status_code == 422
        r = client.put("/api/v1/vision/watch/config", json={"camera_id": 999})
        assert r.status_code == 422
        # All-or-nothing at the route too: nothing changed on disk.
        assert not (_route_env / "watcher_config.json").exists()

    def test_config_route_rejects_explicit_null(self, _route_env: Any) -> None:
        client = self._client()
        r = client.put("/api/v1/vision/watch/config", json={"camera_id": None})
        assert r.status_code == 422
        assert "null" in r.json()["detail"].lower()

    def test_person_notify_route(self, _route_env: Any) -> None:
        """Real store, real route: enroll a face vector directly in the
        isolated FaceStore, then flip the pref over HTTP."""
        store_path = _route_env / "models" / "known_faces.json"
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store = FaceStore(store_path)
        store.add_sample("person_x", "Test Person", [0.2] * 8)

        client = self._client()
        r = client.put(
            "/api/v1/vision/persons/person_x/notify", json={"notify": False}
        )
        assert r.status_code == 200
        assert r.json() == {"ok": True, "person_id": "person_x", "notify": False}
        assert json.loads(store_path.read_text(encoding="utf-8"))["persons"][
            "person_x"
        ]["notify"] is False
        assert FaceStore(store_path).notify_flag("person_x") is False

        # GET /persons/{id} carries the flag:
        r = client.get("/api/v1/vision/persons/person_x")
        assert r.status_code == 200
        assert r.json()["notify"] is False

        # Unknown person → 404:
        r = client.put("/api/v1/vision/persons/ghost/notify", json={"notify": True})
        assert r.status_code == 404

    def test_person_list_carries_notify(self, _route_env: Any) -> None:
        store_path = _route_env / "models" / "known_faces.json"
        store_path.parent.mkdir(parents=True, exist_ok=True)
        store = FaceStore(store_path)
        store.add_sample("person_x", "Test Person", [0.2] * 8)
        store.set_notify("person_x", False)

        client = self._client()
        r = client.get("/api/v1/vision/persons")
        assert r.status_code == 200
        persons = r.json()["persons"]
        assert persons[0]["notify"] is False

    def test_routes_require_auth(self, _route_env: Any) -> None:
        from fastapi.testclient import TestClient

        from dash_backend.main import create_app

        client = TestClient(create_app())
        assert client.get("/api/v1/vision/watch/config").status_code in (401, 403)
        assert client.put(
            "/api/v1/vision/watch/config", json={"interval_seconds": 8}
        ).status_code in (401, 403)
        assert client.put(
            "/api/v1/vision/persons/p/notify", json={"notify": True}
        ).status_code in (401, 403)

    def test_route_accepts_and_persists_notify_settings(
        self, _route_env: Any
    ) -> None:
        client = self._client()
        r = client.put(
            "/api/v1/vision/watch/config",
            json={"notify_known_persons": True, "notify_cooldown_s": 60},
        )
        assert r.status_code == 200
        assert r.json()["notify_known_persons"] is True
        assert r.json()["notify_cooldown_s"] == 60.0
        on_disk = json.loads(
            (_route_env / "watcher_config.json").read_text(encoding="utf-8")
        )
        assert on_disk["watcher"]["notify_known_persons"] is True
        # A truthy string is not a bool — 422, nothing changed:
        r = client.put(
            "/api/v1/vision/watch/config", json={"notify_known_persons": "yes"}
        )
        assert r.status_code == 422
        # Config report carries the new limits/defaults:
        body = client.get("/api/v1/vision/watch/config").json()
        assert body["defaults"]["notify_known_persons"] is False
        assert "notify_cooldown_s_min" in body["limits"]


# ── Desktop notifications for recognized persons (guardian's pattern) ────


class StubNotifier:
    """NotificationService stand-in: records calls, never touches the OS."""

    def __init__(self, fail: bool = False) -> None:
        self.calls: list[dict[str, Any]] = []
        self.fail = fail

    async def show(
        self, title: str = "DASH", message: str = "", duration: int = 5
    ) -> dict[str, Any]:
        self.calls.append({"title": title, "message": message, "duration": duration})
        if self.fail:
            raise RuntimeError("toast transport exploded")
        return {"summary": "sent", "mechanism": "windows-toast", "blocking": False}


class TestDesktopNotify:
    def _w(self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any, **kw: Any):
        w, camera, brain, bus, audit = _make_watcher(monkeypatch, tmp_path, **kw)
        return w, camera, brain, bus, audit

    @pytest.mark.asyncio
    async def test_off_by_default_no_toast_key_no_notifier(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        assert w.get_config()["notify_known_persons"] is False
        cycle = await w.run_cycle()
        ev = next(e for e in cycle["events"] if e["kind"] == "person_seen")
        assert "toast" not in ev["delivered"]  # never attempted ≠ failed
        assert w._notifier is None  # nothing lazily built either

    @pytest.mark.asyncio
    async def test_enabled_toast_fires_with_honest_record(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        stub = StubNotifier()
        w._notifier = stub
        assert w.configure(notify_known_persons=True)["ok"] is True
        cycle = await w.run_cycle()
        ev = next(e for e in cycle["events"] if e["kind"] == "person_seen")
        assert ev["delivered"]["toast"] is True
        assert len(stub.calls) == 1
        assert stub.calls[0]["title"] == "DASH Vision"
        assert "Alice" in stub.calls[0]["message"]
        assert w._last_toast is not None and w._last_toast["status"] == "ok"

    @pytest.mark.asyncio
    async def test_disable_removes_the_key_again(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        w._notifier = StubNotifier()
        w.configure(notify_known_persons=True, repeat_cooldown_s=0)
        await w.run_cycle()
        w.configure(notify_known_persons=False)
        cycle = await w.run_cycle()
        ev = next(e for e in cycle["events"] if e["kind"] == "person_seen")
        assert "toast" not in ev["delivered"]

    @pytest.mark.asyncio
    async def test_opted_out_person_never_gets_a_toast(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """#73's per-person pref outranks the global desktop switch."""
        rec = FakeFaceService(_seen_result())
        rec.set_person_notify("person_123", False)
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path, recognizer=rec)
        stub = StubNotifier()
        w._notifier = stub
        w.configure(notify_known_persons=True)
        await w.run_cycle()
        assert stub.calls == []  # person event suppressed → no toast

    @pytest.mark.asyncio
    async def test_own_rate_limit_independent_of_event_cooldown(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Event cooldown 0 → every cycle reports an event; the toast still
        fires at most once per notify_cooldown_s (its own clock)."""
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        stub = StubNotifier()
        w._notifier = stub
        w.configure(
            notify_known_persons=True,
            repeat_cooldown_s=0,
            notify_cooldown_s=300.0,
        )
        await w.run_cycle()
        await w.run_cycle()
        await w.run_cycle()
        assert len(stub.calls) == 1  # rate-limited on the notify clock
        last = w._last_toast
        assert last is not None and last.get("reason") == "notify cooldown active"

    @pytest.mark.asyncio
    async def test_notify_limit_independent_of_event_limit(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """A toast skipped by the notify limit must not suppress the event
        record — the brain still learns about the sighting."""
        w, _c, brain, _bus, _a = self._w(monkeypatch, tmp_path)
        w._notifier = StubNotifier()
        w.configure(
            notify_known_persons=True,
            repeat_cooldown_s=0,
            notify_cooldown_s=300.0,
        )
        await w.run_cycle()
        brain_count_after_first = len(brain.observations)
        await w.run_cycle()  # toast skipped by rate limit
        assert len(brain.observations) > brain_count_after_first

    @pytest.mark.asyncio
    async def test_failing_notifier_honest_skipped(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        w._notifier = StubNotifier(fail=True)
        w.configure(notify_known_persons=True)
        cycle = await w.run_cycle()
        ev = next(e for e in cycle["events"] if e["kind"] == "person_seen")
        assert ev["delivered"]["toast"] is False
        assert w._last_toast is not None
        assert w._last_toast["status"] == "skipped"
        assert "toast transport exploded" in w._last_toast["reason"]
        # brain/bus/audit are unaffected by a dead toast channel:
        assert ev["delivered"]["brain"] is True

    @pytest.mark.asyncio
    async def test_failing_notifier_not_hammered(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """A broken notifier is retried at most once per notify window —
        stamping happens before dispatch (guardian's anti-spam order)."""
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path)
        stub = StubNotifier(fail=True)
        w._notifier = stub
        w.configure(notify_known_persons=True, repeat_cooldown_s=0)
        await w.run_cycle()
        await w.run_cycle()
        await w.run_cycle()
        assert len(stub.calls) == 1

    @pytest.mark.asyncio
    async def test_non_person_kinds_never_toast(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        """Only toast-worthy kinds reach the desktop — unknown_person stays
        a bus/brain/audit event, never a toast."""
        from dash_backend.vision.recognition import VisionResult

        rec = FakeFaceService(
            VisionResult(
                backend="onnx",
                faces=[
                    {
                        "box": [0, 0, 10, 10],
                        "confidence": 0.9,
                        "match": None,
                        "match_status": "unknown person",
                    }
                ],
                persons=[],
            )
        )
        w, _c, _b, _bus, _a = self._w(monkeypatch, tmp_path, recognizer=rec)
        stub = StubNotifier()
        w._notifier = stub
        w.configure(notify_known_persons=True, repeat_cooldown_s=0)
        cycle = await w.run_cycle()
        kinds = [e["kind"] for e in cycle["events"]]
        assert "unknown_person" in kinds
        assert all("toast" not in e["delivered"] for e in cycle["events"])
        assert stub.calls == []

    def test_config_type_contract_and_persistence(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Any
    ) -> None:
        w, *_ = self._w(monkeypatch, tmp_path)
        # Truthy non-bools rejected at the validation layer:
        res = w.configure(notify_known_persons="yes")  # type: ignore[arg-type]
        assert res["ok"] is False
        assert w.get_config()["notify_known_persons"] is False
        # Negative cooldown rejected:
        res = w.configure(notify_cooldown_s=-1)
        assert res["ok"] is False
        # Valid update persists + survives a new instance (restart):
        assert w.configure(notify_known_persons=True, notify_cooldown_s=45.0)["ok"]
        on_disk = json.loads((tmp_path / "watcher_config.json").read_text())
        assert on_disk["watcher"]["notify_known_persons"] is True
        assert on_disk["watcher"]["notify_cooldown_s"] == 45.0
        w2 = VisionWatcher(
            camera=FakeCamera(CaptureResult(frame=b"x")),
            recognizer=FakeFaceService(_seen_result()),
            brain=FakeBrain(),
            bus=FakeBus(),
            store_path=tmp_path / "watcher_config.json",
        )
        assert w2.get_config()["notify_known_persons"] is True
        assert w2.get_config()["notify_cooldown_s"] == 45.0

    def test_store_rejects_string_bool_in_file(self, tmp_path: Any) -> None:
        """A config file with notify_known_persons="true" must not become
        a truthy flag — the store's type contract catches it."""
        p = tmp_path / "cfg.json"
        p.write_text(
            json.dumps({"version": 1, "watcher": {"notify_known_persons": "true"}}),
            encoding="utf-8",
        )
        assert WatcherConfigStore(p).load() == {}

