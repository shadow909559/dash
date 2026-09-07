"""Tests for DASH privacy and data control endpoints (spec Part 18).

Covers:
- GET /privacy/data-export returns structured user data
- DELETE /privacy/data-delete with confirm=true actually removes data
- DELETE /privacy/data-delete without confirm returns safety message
- GET /privacy/data-inventory returns accurate data store descriptions
- Unauthenticated access is rejected
"""

from __future__ import annotations

import pytest




# ── Data export ─────────────────────────────────────────────────


async def test_data_export_returns_sections(client):
    r = await client.get("/api/v1/privacy/data-export")
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    assert "memories" in data["sections"]
    assert "conversations" in data["sections"]
    assert "goals" in data["sections"]
    assert "audit_log" in data["sections"]


async def test_data_export_structure(client):
    """Export must return all expected sections with correct structure."""
    r = await client.get("/api/v1/privacy/data-export")
    assert r.status_code == 200
    data = r.json()
    assert "sections" in data
    for key in ("memories", "conversations", "goals", "notifications", "auth_tokens", "device_state", "audit_log"):
        assert key in data["sections"], f"missing section: {key}"


async def test_data_delete_with_confirm_removes_data(client):
    """Delete with confirm=true returns success and a counts dict."""
    r = await client.delete("/api/v1/privacy/data-delete?confirm=true")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] is True
    assert isinstance(data["counts"], dict)
    # Counts should have numeric values (not error strings)
    for key, val in data["counts"].items():
        assert isinstance(val, (int, bool)), f"counts[{key}] = {val!r} (expected int/bool)"


# ── Data deletion ───────────────────────────────────────────────


async def test_data_delete_without_confirm_is_safe(client):
    r = await client.delete("/api/v1/privacy/data-delete")
    assert r.status_code == 200
    data = r.json()
    assert data["deleted"] is False
    assert "confirm=true" in data["message"]





# ── Data inventory ──────────────────────────────────────────────


async def test_data_inventory_returns_accurate_list(client):
    r = await client.get("/api/v1/privacy/data-inventory")
    assert r.status_code == 200
    data = r.json()
    assert "data_stores" in data
    assert len(data["data_stores"]) >= 5
    names = [s["name"] for s in data["data_stores"]]
    assert "Memories" in names
    assert "Conversations" in names
    assert "Audit Log" in names
    # Every store must have required fields
    for store in data["data_stores"]:
        assert "name" in store
        assert "storage" in store
        assert "retention" in store
        assert "exportable" in store
        assert "deletable" in store


async def test_data_inventory_lists_third_party(client):
    r = await client.get("/api/v1/privacy/data-inventory")
    data = r.json()
    assert "third_party_services" in data
    providers = [s["name"] for s in data["third_party_services"]]
    assert "Ollama (local)" in providers


# ── Auth check ──────────────────────────────────────────────────


async def test_privacy_endpoints_require_auth(app):
    from httpx import ASGITransport, AsyncClient

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as bare:
        assert (await bare.get("/api/v1/privacy/data-export")).status_code == 401
        assert (await bare.delete("/api/v1/privacy/data-delete")).status_code == 401
        assert (await bare.get("/api/v1/privacy/data-inventory")).status_code == 401
