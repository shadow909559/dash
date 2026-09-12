"""Autostart-path regression tests.

The auto-start chain has three links, and each has failed silently before:
1. Windows Run key launches DASH.exe --hidden      (main.ts launchHidden)
2. Electron spawns/attaches the FastAPI backend    (BackendManager)
3. The backend's lifespan starts all services      (main.py lifespan)

Electron main-process code can't run under pytest, so layers 1-2 are tested
against the TypeScript sources (the source of truth) for behavior contracts,
plus minified-safe string markers on the built artifact to catch a stale
build. Layer 3 boots the real app and asserts every service logged
engagement with zero startup exceptions.
"""

from __future__ import annotations

import io
import pathlib
import re
import sys

import pytest

# tests/ -> backend -> apps -> repo root
REPO = pathlib.Path(__file__).resolve().parents[3]
DESKTOP = REPO / "apps" / "desktop"
# vite bundles main.ts AND its imports (incl. backend_manager.ts) into the
# single dist-electron/main.js that Electron actually loads.
DIST_MAIN = DESKTOP / "dist-electron" / "main.js"
SRC_MAIN = DESKTOP / "electron" / "main.ts"
SRC_BM = DESKTOP / "electron" / "backend_manager.ts"


# ── Layer 1: launch flags / login-item contract ───────────────────────────


def test_launch_hidden_recognizes_run_key_args():
    """The Run key carries --hidden; main must treat that as launch-hidden."""
    for src in (SRC_MAIN, DIST_MAIN):
        text = src.read_text(encoding="utf-8")
        assert '--hidden"' in text or '"--hidden"' in text, f"{src.name}: no --hidden check"
        assert "--start-minimized" in text, f"{src.name}: no --start-minimized check"
        assert "getLoginItemSettings" in text, f"{src.name}: login-item state ignored"


def test_run_key_args_passed_when_start_minimized():
    """Windows ignores openAsHidden — the Run key itself must carry --hidden."""
    text = SRC_MAIN.read_text(encoding="utf-8")
    assert 'args: settings.startMinimized ? ["--hidden"] : []' in text


def test_startup_prefs_persisted_to_disk():
    """startAsOrb/startMinimized live in userData (login item can't hold them)."""
    for src in (SRC_MAIN, DIST_MAIN):
        text = src.read_text(encoding="utf-8")
        assert "startup-prefs.json" in text, f"{src.name}: startup prefs not persisted"


def test_start_as_orb_honored_on_hidden_launch():
    """When launchHidden and startAsOrb, the app must open the orb window."""
    text = SRC_MAIN.read_text(encoding="utf-8")
    m = re.search(r"if \(launchHidden && mainWindow", text)
    assert m, "no launchHidden block found"
    block = text[m.start() : m.start() + 900]
    assert "startAsOrb" in block, "startAsOrb not handled inside launchHidden block"
    assert "createOrbWindow" in block
    assert "systemTray.enableBackgroundMode" in block, "non-orb path lost tray background mode"


def test_built_artifact_is_current():
    """The bundle Electron loads must contain this session's fixes (stale
    build detector: these markers only exist in new source)."""
    text = DIST_MAIN.read_text(encoding="utf-8")
    assert "startup-prefs.json" in text, "dist-electron/main.js is stale — run npm run build"
    assert '["--hidden"]' in text, "dist-electron/main.js missing --hidden args (stale build)"


# ── Layer 2: BackendManager spawn correctness ─────────────────────────────


def test_packaged_backend_dir_uses_resources_path():
    """Packaged backend lives in resources/backend, NOT inside app.asar.

    Regression: app.getAppPath() returned <install>/resources/app.asar — a
    path that can never contain the backend — so packaged autostart could
    only fail.
    """
    text = SRC_BM.read_text(encoding="utf-8")
    assert "process.resourcesPath" in text


def test_packaged_spawn_has_pyinstaller_and_venv_fallbacks():
    """No DashBackend.exe is shipped today; the manager must fall back to a
    bundled venv interpreter and then a system python instead of throwing."""
    text = SRC_BM.read_text(encoding="utf-8")
    assert "DashBackend.exe" in text
    assert ".venv" in text and "python.exe" in text
    assert text.count("this.usePythonDirect = true") >= 2, (
        "packaged fallbacks must set usePythonDirect so uvicorn args are used"
    )


def test_health_wait_window_covers_cold_login():
    """60s health wait (120 x 500ms): the lifespan starts 15+ services and
    cold login can exceed the old 20s, burning a scarce restart attempt."""
    text = SRC_BM.read_text(encoding="utf-8")
    m = re.search(r"waitForBackend\(maxAttempts\s*=\s*(\d+),\s*interval\s*=\s*(\d+)\)", text)
    assert m, "waitForBackend defaults not found"
    attempts, interval = int(m.group(1)), int(m.group(2))
    assert attempts * interval >= 60_000, (
        f"health wait is only {attempts * interval}ms — cold login will exhaust restart attempts"
    )


def test_spawn_uses_uvicorn_module_args():
    text = SRC_BM.read_text(encoding="utf-8")
    assert '"-m", "uvicorn"' in text
    assert '"dash_backend.main:app"' in text
    assert '"--host"' in text and '"--port"' in text


def test_stale_backend_replaced_not_duplicated():
    """Port occupied by a stale DASH process must be cleaned up, and a
    healthy one reused — never a second backend on one port."""
    text = SRC_BM.read_text(encoding="utf-8")
    assert "looksLikeDash" in text and "stopPid" in text
    assert "reusing healthy DASH backend" in text


# ── Layer 3: backend lifespan engages every service ───────────────────────


class _Tee(io.StringIO):
    """Capture stdout while still forwarding to the real stream.

    Needed because setup_logging() uses basicConfig(force=True), which
    removes any handler the test attached — but its own handler binds
    sys.stdout at creation, so swapping stdout before app boot captures
    every lifespan log line.
    """

    def __init__(self, original):
        super().__init__()
        self._original = original

    def write(self, s):
        try:
            self._original.write(s)
        except Exception:
            pass
        return super().write(s)

    def flush(self):
        try:
            self._original.flush()
        except Exception:
            pass
        return super().flush()



def test_lifespan_starts_all_services_without_exception(monkeypatch, tmp_path):
    """Boot the real app and require every autostart service to log engagement
    with zero 'Failed to start' exceptions.

    Kept synchronous on purpose: TestClient manages its own event loop and
    deadlocks when instantiated inside a pytest-asyncio test.
    """
    monkeypatch.setenv("DASH_LOCAL_STORE", str(tmp_path / "dash_lifespan_test.db"))
    from fastapi.testclient import TestClient
    from dash_backend.main import create_app

    real_stdout = sys.stdout
    tee = _Tee(real_stdout)
    sys.stdout = tee
    expected = [
        "Database migrations applied",          # alembic auto-migration
        "device identity ready",                # local device identity
        "Executive worker started",             # durable task queue
        "Automation scheduler started",         # automation engine
        "Event Bus started",                    # internal pub/sub
        "System services started",              # health/metrics/cache/resource
        "Enhanced Sync Service started",
        "Plugin Manager and Hot Reloader started",
        "Autonomous agent services started",    # incl. brain
        "Performance optimizers started",
        "Predictive device sampler started",
    ]

    try:
        with TestClient(create_app()) as client:
            r = client.get("/health")
            assert r.status_code == 200
            assert r.json()["status"] == "ok"
    finally:
        sys.stdout = real_stdout

    log = tee.getvalue()
    missing = [needle for needle in expected if needle not in log]
    assert not missing, f"autostart services did not engage: {missing}"

    exceptions = [
        line for line in log.splitlines()
        if "Failed to start" in line or "Alembic migration failed" in line
    ]
    assert not exceptions, f"startup exceptions: {exceptions[:5]}"

    # Shutdown must also complete cleanly — verified in the SAME boot, since
    # booting a second app instance in one pytest process deadlocks on
    # process-wide singletons (background tasks/threads are not all
    # re-startable).
    assert "backend stopped" in log, "lifespan shutdown did not complete"
    assert "EventBus stopped" in log, "event bus did not stop cleanly"
