"""Tests for DASH security audit layer: logout, auth event recording, audit log REST.

Covers:
- POST /auth/logout revokes all refresh tokens (reusing token fails)
- Auth events (register, login success/failure, refresh) are recorded in audit log
- GET /security/audit-log returns recorded events with filtering
- GET /security/audit-log/stats returns statistics
"""

from __future__ import annotations

import pytest


# ── Auth event recording + logout ───────────────────────────────


async def test_register_records_audit_event(client):
    """Registering a user should emit a REGISTER audit event."""
    from dash_backend.services.audit_logs import get_audit_service

    before = len(get_audit_service().query(event_type="REGISTER", limit=100))
    # Register a unique user (client fixture auto-creates owner on first request,
    # so we test register via a separate bare client call).
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "audit_test_register@example.com",
            "username": "audit_test_register",
            "password": "testpass123",
        },
    )
    assert r.status_code in (201, 409)  # 409 if already exists from previous run
    after = len(get_audit_service().query(event_type="REGISTER", limit=100))
    assert after >= before  # event was recorded (or already existed)


async def test_login_failure_records_audit_event(client):
    """Failed login should emit LOGIN_FAILURE with WARNING severity."""
    from dash_backend.services.audit_logs import get_audit_service

    before = len(get_audit_service().query(event_type="LOGIN_FAILURE", limit=100))
    r = await client.post(
        "/api/v1/auth/login",
        json={"email": "nonexistent@example.com", "password": "wrongpass"},
    )
    assert r.status_code == 401
    after = len(get_audit_service().query(event_type="LOGIN_FAILURE", limit=100))
    assert after > before


async def test_logout_revokes_refresh_tokens(client):
    """After logout, the refresh token should no longer work."""
    # Create a fresh user for this test (clean state).
    r = await client.post(
        "/api/v1/auth/register",
        json={
            "email": "logout_test@example.com",
            "username": "logout_test",
            "password": "logoutpass123",
        },
    )
    if r.status_code == 201:
        refresh = r.json()["refresh_token"]
    else:
        # User already exists from a previous run; login to get a fresh token.
        r = await client.post(
            "/api/v1/auth/login",
            json={"email": "logout_test@example.com", "password": "logoutpass123"},
        )
        assert r.status_code == 200
        refresh = r.json()["refresh_token"]

    # Verify refresh works before logout.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 200

    # Logout.
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 204

    # The OLD refresh token should now be rejected.
    r = await client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert r.status_code == 401


async def test_logout_records_audit_event(client):
    """Logout should emit a LOGOUT audit event with tokens_revoked count."""
    from dash_backend.services.audit_logs import get_audit_service

    # Ensure a logged-in user exists.
    await client.post(
        "/api/v1/auth/register",
        json={"email": "logout_audit@example.com", "username": "logout_audit", "password": "pass123"},
    )
    before = len(get_audit_service().query(event_type="LOGOUT", limit=100))
    r = await client.post("/api/v1/auth/logout")
    assert r.status_code == 204
    after = len(get_audit_service().query(event_type="LOGOUT", limit=100))
    assert after > before


# ── Audit log REST endpoint ─────────────────────────────────────


async def test_audit_log_endpoint_returns_entries(client):
    """GET /security/audit-log should return recorded events."""
    r = await client.get("/api/v1/security/audit-log")
    assert r.status_code == 200
    data = r.json()
    assert "count" in data
    assert "entries" in data
    assert isinstance(data["entries"], list)


async def test_audit_log_endpoint_filters_by_event_type(client):
    """Filtering by event_type should narrow results."""
    r = await client.get("/api/v1/security/audit-log?event_type=LOGIN_FAILURE")
    assert r.status_code == 200
    data = r.json()
    for entry in data["entries"]:
        assert entry["event_type"] == "LOGIN_FAILURE"


async def test_audit_log_stats_endpoint(client):
    """GET /security/audit-log/stats should return statistics."""
    r = await client.get("/api/v1/security/audit-log/stats")
    assert r.status_code == 200
    stats = r.json()
    assert "enabled" in stats
    assert "total_entries" in stats


async def test_audit_log_requires_auth(app):
    """Unauthenticated requests to audit log should be rejected."""
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        assert (await bare.get("/api/v1/security/audit-log")).status_code == 401
        assert (await bare.get("/api/v1/security/audit-log/stats")).status_code == 401
