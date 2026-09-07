import asyncio
import pytest

from dash_backend.automation.scheduler import AutomationScheduler
from dash_backend.automation import service as automation_service


@pytest.mark.asyncio
async def test_scheduler_runs_interval(monkeypatch):
    called = []

    async def fake_fetch(session):
        # return a single fake automation-like object
        class A:
            id = "fake"
            trigger_type = "interval"
            schedule = "1"
            enabled = True
        return [A()]

    async def fake_execute(session, a):
        called.append(a.id)
        return {"status": "SUCCESS"}

    monkeypatch.setattr(automation_service, "fetch_enabled_automations", fake_fetch)
    monkeypatch.setattr(automation_service, "execute_automation", fake_execute)

    sched = AutomationScheduler(poll_interval=1)
    try:
        sched.start()
        await asyncio.sleep(2.5)
    finally:
        await sched.stop()

    assert "fake" in called
