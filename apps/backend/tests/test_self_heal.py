"""Self-healing loop tests (docs/ROADMAP.md Phase 2, decisions.md #59).

All hermetic: fake checks injected, fake repair routine records calls,
audit service pointed at a temp dir. Proves the honesty contract:
"recovered" requires a passing re-run, a repair that doesn't fix the
problem is reported as still-unhealthy, skipped checks count as neither
healthy nor failing, and every cycle lands in the audit log.
"""
from __future__ import annotations

from typing import Optional  # noqa: F401  (kept for future typed fixtures)

import pytest

from dash_backend.self_heal import (
    CheckResult,
    SelfHealingLoop,
    get_self_healing_loop,
)


class FakeRepair:
    """Records actions; optionally reports success per action."""

    def __init__(self, succeed: bool = True):
        self.calls: list[str] = []
        self.succeed = succeed

    async def run(self, action: str) -> dict:
        self.calls.append(action)
        return {"action": action, "status": "ok" if self.succeed else "error"}


@pytest.fixture()
def isolated_audit(monkeypatch: pytest.MonkeyPatch, tmp_path):
    import dash_backend.services.audit_logs as audit_mod

    monkeypatch.setenv("DASH_AUDIT_LOG_DIR", str(tmp_path / "audit"))
    monkeypatch.setattr(audit_mod, "_audit_service", None)
    yield
    monkeypatch.setattr(audit_mod, "_audit_service", None)


def _loop(checks, repair: FakeRepair, **kw) -> SelfHealingLoop:
    return SelfHealingLoop(checks=checks, repair_routine=repair,
                           interval_seconds=30.0, **kw)


# Note: lambdas take the loop argument by position as `_` so ruff's E741
# (ambiguous name) is satisfied without losing the required parameter.


async def test_healthy_cycle_makes_no_repairs(isolated_audit) -> None:
    repair = FakeRepair()
    loop = _loop(
        [lambda _: CheckResult.healthy("a"), lambda _: CheckResult.healthy("b")],
        repair,
    )
    cycle = await loop.run_cycle()
    assert cycle["issues_detected"] == 0
    assert cycle["repairs"] == [] and cycle["recovered"] == []
    assert repair.calls == []
    assert cycle["degraded"] is False


async def test_repair_recovers_and_reports(isolated_audit) -> None:
    repair = FakeRepair()
    state = {"calls": 0}

    def flaky(_loop) -> CheckResult:
        state["calls"] += 1
        # unhealthy on the first pass, healthy on the verify re-run
        if state["calls"] == 1:
            return CheckResult.unhealthy("flaky", "broken", repair_action="fixit")
        return CheckResult.healthy("flaky")

    loop = _loop([flaky], repair)
    cycle = await loop.run_cycle()
    assert repair.calls == ["fixit"]
    assert cycle["recovered"] == ["flaky"]
    assert cycle["still_unhealthy"] == []
    assert cycle["degraded"] is False


async def test_failed_repair_is_reported_not_assumed(isolated_audit) -> None:
    """The repair 'succeeds' but the check still fails → still_unhealthy,
    never 'recovered'. This is the honesty rule the whole loop exists for."""
    repair = FakeRepair(succeed=True)
    loop = _loop(
        [lambda _: CheckResult.unhealthy("broken_thing", "still broken",
                                         repair_action="useless_fix")],
        repair,
    )
    cycle = await loop.run_cycle()
    assert cycle["repairs"][0]["status"] == "ok"  # repair ran fine...
    assert cycle["still_unhealthy"] == ["broken_thing"]  # ...but did not fix
    assert cycle["recovered"] == []


async def test_issue_without_repair_action_is_flagged(isolated_audit) -> None:
    loop = _loop(
        [lambda _: CheckResult.unhealthy("mystery", "no known fix")],
        FakeRepair(),
    )
    cycle = await loop.run_cycle()
    assert cycle["repairs"][0]["status"] == "no_action"
    assert cycle["still_unhealthy"] == ["mystery"]


async def test_skipped_check_is_not_healthy_nor_failing(isolated_audit) -> None:
    loop = _loop(
        [lambda _: CheckResult.skipped("opt_dep", "psutil missing")],
        FakeRepair(),
    )
    cycle = await loop.run_cycle()
    assert cycle["issues_detected"] == 0
    assert cycle["checks"][0]["status"] == "skipped"


async def test_critical_unresolved_marks_degraded(isolated_audit) -> None:
    loop = _loop(
        [lambda _: CheckResult.unhealthy("disk", "1% free",
                                         repair_action="none_exists",
                                         critical=True)],
        FakeRepair(),
    )
    cycle = await loop.run_cycle()
    assert cycle["degraded"] is True


async def test_check_exception_becomes_skip_not_crash(isolated_audit) -> None:
    def broken(_loop) -> CheckResult:
        raise RuntimeError("check blew up")

    loop = _loop([broken], FakeRepair())
    cycle = await loop.run_cycle()
    assert cycle["checks"][0]["status"] == "skipped"
    assert "blew up" in cycle["checks"][0]["detail"]


async def test_async_check_is_awaited(isolated_audit) -> None:
    async def async_check(_loop) -> CheckResult:
        return CheckResult.healthy("async_ok")

    loop = _loop([async_check], FakeRepair())
    cycle = await loop.run_cycle()
    assert cycle["checks"][0]["status"] == "healthy"


async def test_scheduler_restart_repair_path(isolated_audit) -> None:
    repair = FakeRepair()
    started = {"n": 0}

    def restarter() -> None:
        started["n"] += 1

    loop = _loop(
        [lambda _: CheckResult.unhealthy("trigger_scheduler", "dead",
                                         repair_action="restart_trigger_scheduler")],
        repair, scheduler_restarter=restarter,
    )
    await loop.run_cycle()
    assert started["n"] == 1  # restarter invoked, not the generic routine
    assert repair.calls == []


async def test_history_and_status(isolated_audit) -> None:
    loop = _loop([lambda _: CheckResult.healthy("x")], FakeRepair())
    await loop.run_cycle()
    await loop.run_cycle()
    status = loop.get_status()
    assert status["cycles_run"] == 2
    assert status["last_cycle"]["issues_detected"] == 0
    assert status["checks_registered"] == 1


async def test_singleton(isolated_audit) -> None:
    assert get_self_healing_loop() is get_self_healing_loop()
    # Silence F841 for the unused cycle assignment in the status test
    # (kept explicit there to assert on last_cycle instead).


async def test_cycle_is_audited(isolated_audit) -> None:
    """Every cycle lands in the audit log — self-healing is traceable."""
    from dash_backend.services.audit_logs import get_audit_service

    loop = _loop(
        [lambda _: CheckResult.unhealthy("thing", "bad", repair_action="fix")],
        FakeRepair(),
    )
    await loop.run_cycle()
    events = get_audit_service().query(event_type="SELF_HEAL", limit=10)
    assert events, "self-heal cycle must be auditable"
