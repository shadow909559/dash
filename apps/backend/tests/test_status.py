"""Regression tests for /status/overview aggregation.

Status must reflect REAL subsystem state and never fabricate data; sections
that are unavailable degrade gracefully with available=false.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from dash_backend.main import create_app
from tests.conftest import AUTH_HEADERS


@pytest.fixture
async def status_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
        yield ac


@pytest.mark.asyncio
async def test_status_overview_shape(status_client: AsyncClient) -> None:
    resp = await status_client.get("/api/v1/status/overview")
    assert resp.status_code == 200
    body = resp.json()

    # Core sections always present
    assert body["backend"]["status"] == "ok"
    for section in ("conversations", "tasks", "planner", "notifications", "ai_provider", "system", "services"):
        assert section in body, f"missing status section: {section}"


@pytest.mark.asyncio
async def test_status_conversations_reflect_db(status_client: AsyncClient) -> None:
    """Create a conversation via API, then verify counters move."""
    created = await status_client.post("/api/v1/conversations", json={"title": "status-check"})
    assert created.status_code in (200, 201), created.text

    resp = await status_client.get("/api/v1/status/overview")
    body = resp.json()
    conv_section = body["conversations"]
    if conv_section.get("available", True):
        assert conv_section["total"] >= 1


@pytest.mark.asyncio
async def test_status_requires_device_token() -> None:
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as unauth:
        resp = await unauth.get("/api/v1/status/overview")
    assert resp.status_code == 401
