"""Guardian — DASH's defensive security brain (Phase 4, decisions.md #60).

Defends the machine autonomously. NOT offense: this module contains no
port scans of other hosts, no exploit code, no payload generation — the
roadmap refuses those on real grounds (they endanger the user, not
protect them). What it does, on a poll loop:

1. LISTENING-PORT WATCH — every listening TCP socket is inventoried
   (pid, process name, address). NEW listeners that are not on the
   allowlist (first-seen baseline is trusted; anything after startup is
   an event) raise a GUARDIAN_NEW_LISTENER incident. This is how backdoor
   listeners and worm-payload servers actually show up on a home machine.
2. PROCESS WATCH — processes whose name matches a known miner/RAT-ish
   pattern raise a GUARDIAN_SUSPICIOUS_PROCESS incident (pattern list is
   deliberately small and explained; guessing breeds false alarms).
3. FAILED-LOGIN DETECTION — reads the audit log for LOGIN_FAILURE
   entries. Source IP is recorded on login failures now (see auth.py),
   so bursts from one IP escalate severity; sourceless bursts still
   count (they existed before this module).

Automatic response, deliberately boring by design:
- Every incident is audit-logged (GUARDIAN_INCIDENT) — the honest
  incident log comes first; response is secondary.
- Desktop notification for high-severity incidents.
- Publishes guardian.* events on the event bus so workflows can react
  (the user can wire "on new listener → log and notify" flows).
- Rate-limited actions: each (action, key) pair fires at most once per
  cooldown so an attack storm cannot loop DASH into a notification flood
  or a process-kill storm. Actions FAIL SAFE: anything the engine cannot
  do (psutil absent, process already gone, kill denied) is reported as
  "skipped" with the reason — never counted as success.

The one destructive action — terminating a suspicious process — is
manual-only: the incident names the pid; a human decides. An automated
kill loop acting on heuristics is how a defender becomes the attacker.
"""
from __future__ import annotations

import asyncio
import fnmatch
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# 0-RTT patterns: tiny, explainable, and worth a look. A name matching
# these is an INCIDENT TO REVIEW, not proof of compromise.
SUSPICIOUS_PROCESS_PATTERNS: tuple[str, ...] = (
    "xmrig*", "cpuminer*", "minerd*", "cryptominer*",  # coin miners
    "nc.exe", "ncat*", "netcat*",                       # raw shells
    "mimikatz*", "pwdump*", "lazagne*",                 # credential theft
    "keylogger*",                                       # keyloggers
)

# Listening on 0.0.0.0/:: for these ports is normal home-software noise.
COMMON_LISTEN_PORTS = {139, 445, 5353, 5355, 5040, 5432, 6463, 7000, 27036, 49664, 49665, 49666, 49667, 49668}

DEFAULT_INTERVAL_S = 60.0
ACTION_COOLDOWN_S = 300.0          # per (action, key)
FAILED_LOGIN_WINDOW_S = 300.0      # burst window
FAILED_LOGIN_BURST = 8             # failures within the window → incident
MAX_PORTS_PER_SCAN = 256           # report cap per scan (never spam)


@dataclass
class Incident:
    kind: str                 # new_listener | suspicious_process | failed_login_burst
    severity: str             # info | warning | critical
    detail: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"kind": self.kind, "severity": self.severity, **self.detail}


@dataclass
class ListenerSnapshot:
    port: int
    pid: Optional[int]
    process: str
    address: str


def _psutil():
    import psutil

    return psutil


class Guardian:
    """Polling defensive-security monitor with an automatic response engine."""

    def __init__(
        self,
        interval_seconds: float = DEFAULT_INTERVAL_S,
        failed_login_burst: int = FAILED_LOGIN_BURST,
        failed_login_window_s: float = FAILED_LOGIN_WINDOW_S,
        action_cooldown_s: float = ACTION_COOLDOWN_S,
        allow_ports: Optional[set[int]] = None,
        notifier: Any = None,
        bus: Any = None,
    ) -> None:
        self._interval = max(15.0, float(interval_seconds))
        self._burst_threshold = int(failed_login_burst)
        self._burst_window_s = float(failed_login_window_s)
        self._cooldown_s = float(action_cooldown_s)
        self._allow_ports = set(allow_ports) if allow_ports is not None else set(COMMON_LISTEN_PORTS)
        self._notifier = notifier
        self._bus = bus

        self._known_listeners: set[tuple[int, str]] = set()
        self._baseline_taken = False
        self._login_times: deque[float] = deque(maxlen=200)
        self._login_ips: dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self._last_action: dict[str, float] = {}
        self._task: Optional[asyncio.Task] = None
        self._history: deque = deque(maxlen=100)
        self._incidents_total = 0

    # ── lifecycle ──────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Guardian started (interval=%ss, burst=%d/%ss)",
                    self._interval, self._burst_threshold, self._burst_window_s)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Guardian stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_scan()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Guardian scan failed")
            await asyncio.sleep(self._interval)

    # ── detection: listening ports ─────────────────────────────────

    def _scan_listeners(self) -> list[ListenerSnapshot]:
        psutil = _psutil()
        out: list[ListenerSnapshot] = []
        for conn in psutil.net_connections(kind="inet"):
            if conn.status != psutil.CONN_LISTEN or conn.laddr is None:
                continue
            name = ""
            if conn.pid:
                try:
                    name = psutil.Process(conn.pid).name()
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    name = "<access denied>"
            out.append(ListenerSnapshot(
                port=int(conn.laddr.port), pid=conn.pid, process=name,
                address=f"{conn.laddr.ip}:{conn.laddr.port}",
            ))
            if len(out) >= MAX_PORTS_PER_SCAN:
                break
        return out

    def check_listeners(self) -> list[Incident]:
        """Diff current listeners against the trusted baseline."""
        incidents: list[Incident] = []
        try:
            current = self._scan_listeners()
        except Exception as exc:
            logger.warning("Guardian listener scan unavailable: %s", exc)
            return incidents

        seen_now: set[tuple[int, str]] = set()
        for snap in current:
            key = (snap.port, snap.process)
            seen_now.add(key)
            if not self._baseline_taken:
                continue
            if key in self._known_listeners:
                continue
            # A brand-new listener on an uncommon port is worth more
            # attention than one on a port known-noisy anyway.
            severity = "info" if snap.port in self._allow_ports else "warning"
            incidents.append(Incident(
                kind="new_listener",
                severity=severity,
                detail={"port": snap.port, "pid": snap.pid,
                        "process": snap.process, "address": snap.address,
                        "hint": "verify this is software you installed"},
            ))
        self._known_listeners = seen_now
        self._baseline_taken = True
        return incidents

    # ── detection: suspicious processes ────────────────────────────

    def check_processes(self) -> list[Incident]:
        incidents: list[Incident] = []
        try:
            psutil = _psutil()
            names = [(p.info["pid"], p.info["name"] or "")
                     for p in psutil.process_iter(attrs=["pid", "name"])]
        except Exception as exc:
            logger.warning("Guardian process scan unavailable: %s", exc)
            return incidents
        seen: set[str] = set()
        for pid, name in names:
            lowered = name.lower()
            for pattern in SUSPICIOUS_PROCESS_PATTERNS:
                if fnmatch.fnmatch(lowered, pattern) and pattern not in seen:
                    seen.add(pattern)
                    incidents.append(Incident(
                        kind="suspicious_process",
                        severity="critical",
                        detail={"pid": pid, "process": name,
                                "pattern": pattern,
                                "hint": "review manually before acting; "
                                        "guardian never kills automatically"},
                    ))
                    break
        return incidents

    # ── detection: failed-login bursts ─────────────────────────────

    def record_login_failure(self, source_ip: Optional[str] = None) -> Optional[Incident]:
        """Feed one failed login; returns an incident when the burst
        threshold is crossed. Called from the login path and by the
        audit-scan sweep (which covers failures Guardian never saw live)."""
        now = time.time()
        cutoff = now - self._burst_window_s
        self._login_times.append(now)
        while self._login_times and self._login_times[0] < cutoff:
            self._login_times.popleft()
        recent = list(self._login_times)

        ip_key = source_ip or "unknown"
        if source_ip:
            ips = self._login_ips[ip_key]
            ips.append(now)
            ip_recent = [t for t in ips if now - t <= self._burst_window_s]
            if len(ip_recent) >= self._burst_threshold:
                return Incident(
                    kind="failed_login_burst", severity="warning",
                    detail={"source_ip": ip_key, "count": len(ip_recent),
                            "window_s": self._burst_window_s,
                            "hint": "repeated failures from one address — "
                                    "credential stuffing pattern"},
                )
        if len(recent) >= self._burst_threshold * 2:
            return Incident(
                kind="failed_login_burst", severity="critical",
                detail={"source_ip": ip_key, "count": len(recent),
                        "window_s": self._burst_window_s,
                        "hint": "failure storm across sources — possible "
                                "distributed attempt"},
            )
        return None

    def scan_audit_log(self) -> list[Incident]:
        """Sweep recent LOGIN_FAILURE entries from the audit log (covers
        failures that happened while guardian was not watching)."""
        incidents: list[Incident] = []
        try:
            from dash_backend.services.audit_logs import get_audit_service

            entries = get_audit_service().query(event_type="LOGIN_FAILURE", limit=50)
        except Exception:
            return incidents
        now = time.time()
        for entry in entries:
            try:
                ts = float(entry.get("timestamp", 0))
            except (TypeError, ValueError):
                continue
            if now - ts <= self._burst_window_s:
                self._login_times.append(ts)
        if len(self._login_times) >= self._burst_threshold:
            incidents.append(Incident(
                kind="failed_login_burst", severity="warning",
                detail={"source_ip": "audit_log_sweep",
                        "count": len(self._login_times),
                        "window_s": self._burst_window_s,
                        "hint": "failures observed in the audit log"},
            ))
        return incidents

    # ── response engine ────────────────────────────────────────────

    def _cooldown_ok(self, action: str, key: str) -> bool:
        stamp = f"{action}:{key}"
        now = time.time()
        last = self._last_action.get(stamp, 0.0)
        if now - last < self._cooldown_s:
            return False
        self._last_action[stamp] = now
        return True

    async def _notify(self, incident: Incident) -> dict:
        """Desktop notification; skipped honestly when unavailable."""
        if self._notifier is None:
            try:
                from dash_backend.services.notifications import NotificationService

                self._notifier = NotificationService()
            except Exception as exc:
                return {"action": "notify", "status": "skipped", "reason": str(exc)}
        try:
            await self._notifier.show(
                title=f"DASH Guardian: {incident.kind}",
                message=str(incident.detail.get("hint", ""))[:200],
            )
            return {"action": "notify", "status": "ok"}
        except Exception as exc:
            return {"action": "notify", "status": "skipped", "reason": str(exc)}

    async def _publish(self, incident: Incident) -> dict:
        """Publish on the event bus so workflows can react; skipped when
        no loop/bus is available (producers must never crash the scanner)."""
        if self._bus is None:
            try:
                from dash_backend.events.event_bus import get_event_bus

                self._bus = get_event_bus()
            except Exception as exc:
                return {"action": "publish", "status": "skipped", "reason": str(exc)}
        try:
            await self._bus.publish_sync(
                topic=f"guardian.{incident.kind}",
                data=incident.to_dict(),
                source="guardian",
            )
            return {"action": "publish", "status": "ok"}
        except Exception as exc:
            return {"action": "publish", "status": "skipped", "reason": str(exc)}

    async def respond(self, incident: Incident) -> list[dict]:
        """Rate-limited automatic response. Notification + workflow event;
        heavy actions stay manual (see module docstring)."""
        results: list[dict] = []
        key = f"{incident.kind}:{incident.detail.get('port') or incident.detail.get('source_ip') or incident.detail.get('process')}"
        if self._cooldown_ok("respond", key):
            results.append(await self._notify(incident))
            results.append(await self._publish(incident))
        else:
            results.append({"action": "respond", "status": "skipped",
                            "reason": "cooldown active for this incident key"})
        return results

    # ── the scan ───────────────────────────────────────────────────

    async def run_scan(self) -> dict:
        """One full scan; blocks of work run in threads where psutil is
        expensive. Returns a cycle record and (rate-limited) responds."""
        started = time.perf_counter()
        incidents: list[Incident] = []
        # psutil calls are blocking → off the event loop.
        listener_incidents = await asyncio.to_thread(self.check_listeners)
        process_incidents = await asyncio.to_thread(self.check_processes)
        incidents.extend(listener_incidents)
        incidents.extend(process_incidents)
        incidents.extend(self.scan_audit_log())

        responses: list[dict] = []
        for incident in incidents:
            self._record(incident)
            responses.extend(await self.respond(incident))

        cycle = {
            "at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "incidents": [i.to_dict() for i in incidents],
            "responses": responses,
            "listeners_tracked": len(self._known_listeners),
        }
        self._history.append(cycle)
        return cycle

    def _record(self, incident: Incident) -> None:
        """The honest incident log: every incident lands in the audit
        trail, severity-labeled, whether or not any response succeeded."""
        self._incidents_total += 1
        try:
            from dash_backend.services.audit_logs import get_audit_service

            get_audit_service().log(
                event_type="GUARDIAN_INCIDENT",
                action=incident.kind,
                status=incident.severity,
                details=incident.to_dict(),
                severity="WARNING" if incident.severity != "critical" else "CRITICAL",
            )
        except Exception:
            logger.debug("Guardian audit entry failed", exc_info=True)

    # ── observability ──────────────────────────────────────────────

    def get_status(self) -> dict:
        last = self._history[-1] if self._history else None
        return {
            "running": self.running,
            "interval_seconds": self._interval,
            "incidents_total": self._incidents_total,
            "listeners_tracked": len(self._known_listeners),
            "failed_login_threshold": self._burst_threshold,
            "last_scan": {
                "at": last["at"],
                "incidents": len(last["incidents"]),
            } if last else None,
        }

    def recent_incidents(self, limit: int = 20) -> list[dict]:
        out: list[dict] = []
        for cycle in reversed(self._history):
            for incident in cycle["incidents"]:
                out.append(incident)
                if len(out) >= limit:
                    return out
        return out


_guardian: Optional[Guardian] = None


def get_guardian() -> Guardian:
    """Singleton accessor; main.py starts it during lifespan startup."""
    global _guardian
    if _guardian is None:
        _guardian = Guardian()
    return _guardian
