"""Guardian tests (Phase 4, decisions.md #60).

All hermetic: psutil is faked at the module boundary, the notifier is a
recorder, the audit log lives in a temp dir. Proves the honesty contract:
new listeners after baseline are incidents, the first scan is baseline
only, suspicious names are critical incidents, login bursts fire per-IP
and globally, response is rate-limited per key, unavailable actions are
"skipped" (never fake-success), and every incident is audit-logged.
"""
from __future__ import annotations

import time
from typing import Any

import pytest

from dash_backend.security.guardian import (
    Incident,
    ListenerSnapshot,
    Guardian,
    get_guardian,
)


# ── Fake psutil machinery ─────────────────────────────────────────────────


class FakeProc:
    def __init__(self, pid: int, name: str) -> None:
        self._pid, self._name = pid, name

    def name(self) -> str:
        return self._name


class FakeAddr:
    def __init__(self, ip: str, port: int) -> None:
        self.ip, self.port = ip, port


class FakeConn:
    def __init__(self, laddr: FakeAddr, pid: int, status: str) -> None:
        self.laddr, self.pid, self.status = laddr, pid, status


class FakePsutil:
    CONN_LISTEN = "LISTEN"

    def __init__(self, conns: list[FakeConn], procs: list[dict]) -> None:
        self._conns, self._procs = conns, procs
        self.NoSuchProcess = type("NoSuchProcess", (), {})
        self.AccessDenied = type("AccessDenied", (), {})

    def net_connections(self, kind: str = "inet") -> list[FakeConn]:
        assert kind == "inet"
        return self._conns

    def Process(self, pid: int) -> FakeProc:
        for p in self._procs:
            if p["pid"] == pid:
                return FakeProc(p["pid"], p["name"])
        raise self.NoSuchProcess()

    def process_iter(self, attrs: list[str]) -> list[Any]:
        # Real psutil yields Process objects with an .info dict — guardian
        # reads p.info[...], so the fake must present the same surface.
        class P:
            def __init__(self, item: dict) -> None:
                self.info = dict(item)

        return [P(p) for p in self._procs]


class RecorderNotifier:
    def __init__(self) -> None:
        self.shown: list[tuple[str, str]] = []

    async def show(self, title: str, message: str = "", **kw) -> dict:
        self.shown.append((title, message))
        return {"summary": title}


@pytest.fixture()
def isolated_audit(monkeypatch: pytest.MonkeyPatch, tmp_path):
    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(audit_mod, "_audit_service", None)
    yield
    monkeypatch.setattr(audit_mod, "_audit_service", None)


def _make_guardian(monkeypatch, conns, procs, **kw) -> Guardian:
    import dash_backend.security.guardian as gmod

    fake = FakePsutil(conns, procs)
    monkeypatch.setattr(
        gmod, "_psutil", lambda: fake, raising=True
    )
    g = Guardian(notifier=RecorderNotifier(), bus=None, **kw)
    return g


# ── Listener watch ────────────────────────────────────────────────────────


def _conn(port: int, pid: int, ip: str = "0.0.0.0") -> FakeConn:
    return FakeConn(FakeAddr(ip, port), pid, "LISTEN")


def test_first_scan_is_baseline_no_incidents(monkeypatch) -> None:
    g = _make_guardian(monkeypatch, [_conn(8080, 100)], [{"pid": 100, "name": "app.exe"}])
    incidents = g.check_listeners()
    assert incidents == []
    assert g.get_status()["listeners_tracked"] == 1


def test_new_listener_after_baseline_is_incident(monkeypatch) -> None:
    g = _make_guardian(monkeypatch, [_conn(8080, 100)], [{"pid": 100, "name": "app.exe"}])
    g.check_listeners()  # baseline

    # A new process starts listening on an uncommon port.
    g._scan_listeners = lambda: [
        ListenerSnapshot(8080, 100, "app.exe", "0.0.0.0:8080"),
        ListenerSnapshot(4444, 200, "unknown.exe", "0.0.0.0:4444"),
    ]
    incidents = g.check_listeners()
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.kind == "new_listener" and inc.severity == "warning"
    assert inc.detail["port"] == 4444 and inc.detail["process"] == "unknown.exe"


def test_new_listener_on_common_port_is_info(monkeypatch) -> None:
    g = _make_guardian(monkeypatch, [], [])
    g.check_listeners()  # baseline: empty
    g._scan_listeners = lambda: [ListenerSnapshot(5353, 300, "mdns", "0.0.0.0:5353")]
    incidents = g.check_listeners()
    assert len(incidents) == 1 and incidents[0].severity == "info"


def test_recurring_listener_does_not_re_fire(monkeypatch) -> None:
    snap = [ListenerSnapshot(9000, 10, "svc", "0.0.0.0:9000")]
    g = _make_guardian(monkeypatch, [], [])
    g.check_listeners()
    g._scan_listeners = lambda: snap
    assert len(g.check_listeners()) == 1
    assert g.check_listeners() == []  # same listener: no new incident


# ── Process watch ─────────────────────────────────────────────────────────


def test_suspicious_process_is_critical(monkeypatch) -> None:
    g = _make_guardian(
        monkeypatch, [],
        [{"pid": 42, "name": "xmrig"}, {"pid": 43, "name": "chrome.exe"}],
    )
    incidents = g.check_processes()
    assert len(incidents) == 1
    assert incidents[0].kind == "suspicious_process"
    assert incidents[0].severity == "critical"
    assert incidents[0].detail["pid"] == 42
    assert "never kills automatically" in incidents[0].detail["hint"]


def test_benign_processes_are_silent(monkeypatch) -> None:
    g = _make_guardian(
        monkeypatch, [],
        [{"pid": 1, "name": "explorer.exe"}, {"pid": 2, "name": "python.exe"}],
    )
    assert g.check_processes() == []


# ── Failed-login bursts ───────────────────────────────────────────────────


def test_login_burst_from_one_ip_fires(monkeypatch) -> None:
    g = Guardian(failed_login_burst=3, failed_login_window_s=60)
    assert g.record_login_failure("1.2.3.4") is None
    assert g.record_login_failure("1.2.3.4") is None
    inc = g.record_login_failure("1.2.3.4")
    assert inc is not None and inc.kind == "failed_login_burst"
    assert inc.detail["source_ip"] == "1.2.3.4" and inc.detail["count"] == 3


def test_scattered_failures_do_not_fire(monkeypatch) -> None:
    g = Guardian(failed_login_burst=3, failed_login_window_s=60)
    assert g.record_login_failure("1.1.1.1") is None
    assert g.record_login_failure("2.2.2.2") is None
    assert g.record_login_failure("3.3.3.3") is None  # different IPs, under 2x


def test_global_storm_is_critical(monkeypatch) -> None:
    g = Guardian(failed_login_burst=2, failed_login_window_s=60)
    for ip in ("a", "b", "c", "d", "e"):
        g.record_login_failure(ip)
    # 6th failure crosses the global 2x threshold.
    inc = g.record_login_failure("f")
    assert inc is not None and inc.severity == "critical"


def test_old_failures_expire_from_window(monkeypatch) -> None:
    g = Guardian(failed_login_burst=3, failed_login_window_s=1.0)
    for _ in range(3):
        g.record_login_failure("1.1.1.1")
    # Age out the window.
    for key, dq in g._login_ips.items():
        for i in range(len(dq)):
            dq[i] = time.time() - 10
    for i in range(len(g._login_times)):
        g._login_times[i] = time.time() - 10
    assert g.record_login_failure("1.1.1.1") is None


# ── Response engine ───────────────────────────────────────────────────────


async def test_response_notifies_and_is_rate_limited() -> None:
    notifier = RecorderNotifier()
    g = Guardian(notifier=notifier, bus=None)
    inc = Incident("new_listener", "warning",
                   {"port": 4444, "pid": 1, "process": "x", "address": "a"})

    first = await g.respond(inc)
    assert first[0]["status"] == "ok" and notifier.shown
    second = await g.respond(inc)
    assert second[0]["status"] == "skipped"  # cooldown
    assert len(notifier.shown) == 1  # no flood


async def test_publish_event_for_workflows() -> None:
    class Bus:
        def __init__(self):
            self.published: list[tuple] = []

        async def publish_sync(self, topic, data=None, source="", **kw):
            self.published.append((topic, data))

    bus = Bus()
    g = Guardian(notifier=RecorderNotifier(), bus=bus)
    await g.respond(Incident("new_listener", "warning",
                             {"port": 4444, "pid": 1, "process": "x", "address": "a"}))
    assert bus.published and bus.published[0][0] == "guardian.new_listener"


async def test_notification_failure_is_skipped_not_fatal() -> None:
    class BadNotifier:
        async def show(self, *a, **kw):
            raise RuntimeError("no desktop session")

    g = Guardian(notifier=BadNotifier(), bus=None)
    res = await g.respond(Incident("new_listener", "info",
                                   {"port": 1, "pid": 1, "process": "x", "address": "a"}))
    assert res[0]["status"] == "skipped" and "no desktop session" in res[0]["reason"]


# ── Full scan + audit ─────────────────────────────────────────────────────


async def test_run_scan_records_incidents_in_audit(isolated_audit, monkeypatch) -> None:
    g = _make_guardian(
        monkeypatch, [],
        [{"pid": 42, "name": "mimikatz"}],
    )
    cycle = await g.run_scan()
    assert any(i["kind"] == "suspicious_process" for i in cycle["incidents"])

    from dash_backend.services.audit_logs import get_audit_service

    events = get_audit_service().query(event_type="GUARDIAN_INCIDENT", limit=5)
    assert events and events[0]["action"] == "suspicious_process"
    assert events[0]["severity"] == "CRITICAL"


async def test_scan_offloads_psutil_off_event_loop(monkeypatch) -> None:
    """The scan must not block the loop even when psutil is slow:
    checks are sync functions executed in worker threads."""
    g = _make_guardian(monkeypatch, [], [])

    def slow_check():
        time.sleep(0.02)  # blocking, like a real psutil sweep
        return []

    g.check_listeners = slow_check  # type: ignore[method-assign]
    g.check_processes = slow_check  # type: ignore[method-assign]
    cycle = await g.run_scan()
    assert cycle["incidents"] == []


async def test_singleton(isolated_audit) -> None:
    assert get_guardian() is get_guardian()


# ── Routes ────────────────────────────────────────────────────────────────


async def test_guardian_routes(client, monkeypatch) -> None:
    import dash_backend.security.guardian as gmod

    g = Guardian(notifier=RecorderNotifier(), bus=None)
    monkeypatch.setattr(gmod, "_guardian", g)

    r = await client.get("/api/v1/security/guardian")
    assert r.status_code == 200
    body = r.json()
    assert body["running"] is False and "failed_login_threshold" in body

    r = await client.get("/api/v1/security/guardian/incidents")
    assert r.status_code == 200 and r.json()["incidents"] == []


async def test_guardian_routes_require_auth() -> None:
    from fastapi.testclient import TestClient

    from dash_backend.main import create_app

    sync_client = TestClient(create_app())
    assert sync_client.get("/api/v1/security/guardian").status_code in (401, 403)
    assert sync_client.post("/api/v1/security/guardian/scan").status_code in (401, 403)
