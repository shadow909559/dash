"""Approval-system regression tests (two-phase gate for CRITICAL actions).

Verifies Phase 14 requirements:
- Sensitive action without approval does NOT execute and returns pending approval
- Invalid/forged approval id is rejected
- Denial makes execution impossible
- Approval enables exactly one execution
- Expired/stale approvals are rejected
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def fresh_permission_manager(monkeypatch):
    """Isolate the global PermissionManager + approved-id set per test."""
    from dash_backend.services import permission_manager as pm_mod
    from dash_backend.api.routes import desktop_control as dc

    pm = pm_mod.PermissionManager()
    monkeypatch.setattr(pm_mod, "_permission_manager", pm)
    monkeypatch.setattr(dc, "_approved_power_ids", set())
    return pm


async def test_power_action_requires_approval(client, monkeypatch):
    """First call must NOT execute; it must return a pending approval."""
    executed = {"count": 0}

    class FakePowerService:
        async def sleep(self):
            executed["count"] += 1
            return {"summary": "SLEEP EXECUTED"}

    import dash_backend.api.routes.desktop_control as dc

    monkeypatch.setattr(
        "dash_backend.services.power.PowerService", FakePowerService, raising=False
    )

    resp = await client.post("/api/v1/desktop/power/sleep")
    assert resp.status_code == 202, resp.text
    detail = resp.json()["detail"]
    assert detail["approval_required"] is True
    assert detail["operation"] == "sleep"
    assert detail["approval_id"]
    # The dangerous action must not have run.
    assert executed["count"] == 0


async def test_forged_approval_id_rejected(client, monkeypatch):
    class FakePowerService:
        async def sleep(self):
            raise AssertionError("must never execute")

    monkeypatch.setattr(
        "dash_backend.services.power.PowerService", FakePowerService, raising=False
    )
    resp = await client.post("/api/v1/desktop/power/sleep", params={"approval_id": "forged"})
    assert resp.status_code == 400


async def test_approve_then_execute_once(client, monkeypatch, fresh_permission_manager):
    executed = {"count": 0}

    class FakePowerService:
        async def sleep(self):
            executed["count"] += 1
            return {"summary": "SLEEP EXECUTED"}

    monkeypatch.setattr(
        "dash_backend.services.power.PowerService", FakePowerService, raising=False
    )

    first = await client.post("/api/v1/desktop/power/sleep")
    assert first.status_code == 202
    approval_id = first.json()["detail"]["approval_id"]

    ok = await client.post(f"/api/v1/desktop/approvals/{approval_id}/approve")
    assert ok.status_code == 200

    second = await client.post(
        "/api/v1/desktop/power/sleep", params={"approval_id": approval_id}
    )
    assert second.status_code == 200, second.text
    assert executed["count"] == 1

    # Replay of the same approval id must fail (single-use).
    replay = await client.post(
        "/api/v1/desktop/power/sleep", params={"approval_id": approval_id}
    )
    assert replay.status_code == 400
    assert executed["count"] == 1


async def test_denied_action_cannot_execute(client, monkeypatch, fresh_permission_manager):
    executed = {"count": 0}

    class FakePowerService:
        async def shutdown(self, force=False, timeout=30):
            executed["count"] += 1
            return {"summary": "SHUTDOWN EXECUTED"}

    monkeypatch.setattr(
        "dash_backend.services.power.PowerService", FakePowerService, raising=False
    )

    first = await client.post("/api/v1/desktop/power/shutdown", json={})
    assert first.status_code == 202
    approval_id = first.json()["detail"]["approval_id"]

    denied = await client.post(f"/api/v1/desktop/approvals/{approval_id}/deny")
    assert denied.status_code == 200

    attempt = await client.post(
        "/api/v1/desktop/power/shutdown", json={"approval_id": approval_id}
    )
    assert attempt.status_code == 400
    assert executed["count"] == 0


async def test_stale_approval_expiry(client, monkeypatch, fresh_permission_manager):
    class FakePowerService:
        async def sleep(self):
            return {"summary": "nope"}

    monkeypatch.setattr(
        "dash_backend.services.power.PowerService", FakePowerService, raising=False
    )
    first = await client.post("/api/v1/desktop/power/sleep")
    assert first.status_code == 202
    approval_id = first.json()["detail"]["approval_id"]

    # Force-age the pending request beyond the TTL.
    fresh_permission_manager._pending_requests[approval_id].timestamp = 0.0

    stale = await client.post(f"/api/v1/desktop/approvals/{approval_id}/approve")
    assert stale.status_code == 404
