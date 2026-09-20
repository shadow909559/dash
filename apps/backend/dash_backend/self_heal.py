"""DASH self-healing loop (docs/ROADMAP.md Phase 2, decisions.md #59).

A closed loop: DETECT (run checks) → DIAGNOSE (each issue names a repair
action) → REPAIR (best-effort action, never crash) → VERIFY (re-run the
failed checks) → REPORT (structured cycle record + audit log entry).

Design rules, stated because this component can act on its own:
- The loop can only run REGISTERED repair actions — the same best-effort
  routines the /monitor API exposes. It never invents shell commands.
- A repair that does not fix the problem is reported as such. "Recovered"
  means the check was re-run and passed, nothing less.
- Checks are injectable; the built-in set is deliberately cheap and every
  skip (e.g. psutil absent) is reported as "skipped", not silently healthy.
- One check can restart an internal DASH service (the workflow trigger
  scheduler) — the one case where the loop repairs by restart rather than
  by a repair routine.
"""
from __future__ import annotations

import asyncio
import shutil
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional, Union

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CheckFn = Callable[["SelfHealingLoop"], Union["CheckResult", Awaitable["CheckResult"]]]
MAX_HISTORY = 50


@dataclass
class CheckResult:
    """Outcome of one health check.

    status: healthy | unhealthy | skipped — a skipped check (dependency
    missing) is never counted as passing OR failing.
    """

    name: str
    status: str
    detail: str = ""
    repair_action: Optional[str] = None
    critical: bool = False

    @classmethod
    def healthy(cls, name: str, detail: str = "") -> "CheckResult":
        return cls(name=name, status="healthy", detail=detail)

    @classmethod
    def unhealthy(cls, name: str, detail: str, repair_action: Optional[str] = None,
                  critical: bool = False) -> "CheckResult":
        return cls(name=name, status="unhealthy", detail=detail,
                   repair_action=repair_action, critical=critical)

    @classmethod
    def skipped(cls, name: str, detail: str) -> "CheckResult":
        return cls(name=name, status="skipped", detail=detail)


# ── Built-in checks ───────────────────────────────────────────────────────


def _check_disk_space(_loop: "SelfHealingLoop") -> CheckResult:
    """Free disk space on the working drive; low space breaks SQLite
    writes, logs, and state files — flush_temp is the honest first move."""
    usage = shutil.disk_usage(Path.cwd())
    free_gb = usage.free / 1e9
    if free_gb < 1.0:
        return CheckResult.unhealthy(
            "disk_space", f"only {free_gb:.2f} GB free — writes may start failing",
            repair_action="flush_temp", critical=True,
        )
    if free_gb < 5.0:
        return CheckResult.unhealthy(
            "disk_space", f"low disk: {free_gb:.2f} GB free",
            repair_action="flush_temp", critical=False,
        )
    return CheckResult.healthy("disk_space", f"{free_gb:.1f} GB free")


async def _check_event_loop_lag(_loop: "SelfHealingLoop") -> CheckResult:
    """Probe event-loop responsiveness. A starved loop delays every async
    service; overshoot past the requested sleep names the problem."""
    loop = asyncio.get_running_loop()
    requested = 0.005
    start = loop.time()
    await asyncio.sleep(requested)
    overshoot = loop.time() - start - requested
    if overshoot > 0.25:
        return CheckResult.unhealthy(
            "event_loop_lag", f"loop overslept by {overshoot * 1000:.0f} ms — starved",
            repair_action="force_gc", critical=False,
        )
    return CheckResult.healthy("event_loop_lag", f"overshoot {overshoot * 1000:.1f} ms")


def _check_memory_pressure(_loop: "SelfHealingLoop") -> CheckResult:
    try:
        import psutil
    except ImportError:
        return CheckResult.skipped("memory_pressure", "psutil not installed — check unavailable")
    rss_gb = psutil.Process().memory_info().rss / 1e9
    if rss_gb > 1.5:
        return CheckResult.unhealthy(
            "memory_pressure", f"process RSS {rss_gb:.2f} GB",
            repair_action="force_gc", critical=False,
        )
    return CheckResult.healthy("memory_pressure", f"RSS {rss_gb:.2f} GB")


def _check_trigger_scheduler(_loop: "SelfHealingLoop") -> CheckResult:
    """The workflow trigger scheduler must be alive — cron triggers silently
    stop firing if it died, which is precisely the failure this loop exists
    to catch (and fix by restart)."""
    from dash_backend.services.workflow_builder import get_workflow_trigger_scheduler

    if get_workflow_trigger_scheduler().running:
        return CheckResult.healthy("trigger_scheduler", "poll loop alive")
    return CheckResult.unhealthy(
        "trigger_scheduler", "workflow trigger scheduler is not running — "
        "scheduled workflows would silently stop firing",
        repair_action="restart_trigger_scheduler", critical=True,
    )


DEFAULT_CHECKS: list[CheckFn] = [
    _check_disk_space,
    _check_event_loop_lag,
    _check_memory_pressure,
    _check_trigger_scheduler,
]


# ── The loop ──────────────────────────────────────────────────────────────


class SelfHealingLoop:
    """Periodic detect → repair → verify cycles. Injectable for tests."""

    def __init__(
        self,
        checks: Optional[list[CheckFn]] = None,
        interval_seconds: float = 600.0,
        repair_routine: Any = None,
        scheduler_restarter: Optional[Callable[[], Any]] = None,
    ) -> None:
        self._checks = checks if checks is not None else DEFAULT_CHECKS
        self._interval = max(30.0, float(interval_seconds))
        self._repair = repair_routine
        self._scheduler_restarter = scheduler_restarter
        self._task: Optional[asyncio.Task] = None
        self._history: list[dict] = []
        self._cycles_run = 0

    # ── lifecycle ──────────────────────────────────────────────────

    @property
    def running(self) -> bool:
        return self._task is not None and not self._task.done()

    async def start(self) -> None:
        if self.running:
            return
        self._task = asyncio.create_task(self._loop())
        logger.info("Self-healing loop started (interval=%ss)", self._interval)

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass
        self._task = None
        logger.info("Self-healing loop stopped")

    async def _loop(self) -> None:
        while True:
            try:
                await self.run_cycle()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("Self-healing cycle failed")
            await asyncio.sleep(self._interval)

    # ── repair plumbing ────────────────────────────────────────────

    def _get_repair(self) -> Any:
        if self._repair is None:
            from dash_backend.monitoring.repair import get_repair_routine

            self._repair = get_repair_routine()
        return self._repair

    async def _run_repair(self, action: str) -> dict:
        """One repair action. restart_trigger_scheduler is the loop's own
        move (restart a dead internal service); everything else goes to the
        registered repair routines."""
        if action == "restart_trigger_scheduler":
            try:
                if self._scheduler_restarter is None:
                    from dash_backend.services.workflow_builder import get_workflow_trigger_scheduler

                    self._scheduler_restarter = get_workflow_trigger_scheduler().start
                self._scheduler_restarter()
                return {"action": action, "status": "ok"}
            except Exception as exc:
                return {"action": action, "status": "error", "error": str(exc)}
        return await self._get_repair().run(action)

    # ── the cycle ──────────────────────────────────────────────────

    async def _run_checks(self) -> list[CheckResult]:
        results: list[CheckResult] = []
        for fn in self._checks:
            try:
                out = fn(self)
                if asyncio.iscoroutine(out) or isinstance(out, Awaitable):
                    out = await out
                results.append(out)
            except Exception as exc:
                results.append(CheckResult(
                    name=getattr(fn, "__name__", "unknown"),
                    status="skipped", detail=f"check itself failed: {exc}",
                ))
        return results

    async def run_cycle(self) -> dict:
        started = time.perf_counter()
        checks = await self._run_checks()

        unhealthy = [c for c in checks if c.status == "unhealthy"]
        repairs: list[dict] = []
        for issue in unhealthy:
            if not issue.repair_action:
                repairs.append({"action": None, "check": issue.name,
                                "status": "no_action",
                                "detail": "no repair registered for this issue"})
                continue
            result = await self._run_repair(issue.repair_action)
            repairs.append({"action": issue.repair_action, "check": issue.name,
                            "status": result.get("status", "unknown"),
                            "result": result})

        # VERIFY: re-run only the checks that fired. "Recovered" is earned
        # by a passing re-run, never assumed from a repair's return value.
        recovered: list[str] = []
        still_unhealthy: list[str] = []
        if unhealthy:
            rechecks = {c.name: c for c in await self._run_checks()}
            for issue in unhealthy:
                after = rechecks.get(issue.name)
                if after is not None and after.status == "healthy":
                    recovered.append(issue.name)
                else:
                    still_unhealthy.append(issue.name)

        cycle = {
            "started_at": datetime.now(timezone.utc).isoformat(),
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "duration_ms": round((time.perf_counter() - started) * 1000, 1),
            "checks": [vars(c) | {"status": c.status} for c in checks],
            "repairs": repairs,
            "recovered": recovered,
            "still_unhealthy": still_unhealthy,
            "degraded": any(c.critical for c in unhealthy if c.name in still_unhealthy),
            "issues_detected": len(unhealthy),
        }
        self._cycles_run += 1
        self._history.append(cycle)
        del self._history[:-MAX_HISTORY]

        self._audit(cycle)
        logger.info(
            "Self-heal cycle: %d checks, %d issues, recovered=%s, still=%s",
            len(checks), len(unhealthy), recovered or "-", still_unhealthy or "-",
        )
        return cycle

    def _audit(self, cycle: dict) -> None:
        """Traceable self-healing: every cycle lands in the audit log.
        Best-effort — the audit system must never break the loop."""
        try:
            from dash_backend.services.audit_logs import get_audit_service

            get_audit_service().log(
                event_type="SELF_HEAL",
                action="cycle",
                status="degraded" if cycle["degraded"] else "ok",
                details={
                    "issues_detected": cycle["issues_detected"],
                    "recovered": cycle["recovered"],
                    "still_unhealthy": cycle["still_unhealthy"],
                    "repairs": [r.get("action") for r in cycle["repairs"]],
                },
            )
        except Exception:
            logger.debug("Self-heal audit entry failed", exc_info=True)

    # ── observability ──────────────────────────────────────────────

    def get_status(self) -> dict:
        last = self._history[-1] if self._history else None
        return {
            "running": self.running,
            "interval_seconds": self._interval,
            "cycles_run": self._cycles_run,
            "checks_registered": len(self._checks),
            "last_cycle": {
                "started_at": last["started_at"],
                "issues_detected": last["issues_detected"],
                "recovered": last["recovered"],
                "still_unhealthy": last["still_unhealthy"],
                "degraded": last["degraded"],
            } if last else None,
        }


_self_heal_loop: Optional[SelfHealingLoop] = None


def get_self_healing_loop() -> SelfHealingLoop:
    """Singleton accessor; main.py starts it during lifespan startup."""
    global _self_heal_loop
    if _self_heal_loop is None:
        _self_heal_loop = SelfHealingLoop()
    return _self_heal_loop
