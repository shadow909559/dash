"""Route tests for endpoints added during the desktop page wiring:
- POST /features/email/mark-read
- POST /features/browser/tabs/close
- DELETE /features/workspaces/{id}
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH_HEADERS

pytestmark = pytest.mark.asyncio


async def test_email_mark_read_route(client):
    # Seed an email through the service
    from dash_backend.services.email_calendar import email_service

    received = email_service.receive_email("a@b.com", "Test subject", "body")
    email_id = received["email"]["id"] if isinstance(received, dict) and "email" in received else received.get("id")

    r = await client.post(
        "/api/v1/features/email/mark-read",
        json={"email_id": email_id},
        headers=AUTH_HEADERS,
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True


async def test_browser_tab_open_close_route(client):
    opened = await client.post(
        "/api/v1/features/browser/tabs/open",
        json={"url": "https://example.com", "title": "Example"},
        headers=AUTH_HEADERS,
    )
    assert opened.status_code == 200
    tab_id = opened.json().get("tab", {}).get("id") or opened.json().get("id")

    closed = await client.post(
        "/api/v1/features/browser/tabs/close",
        json={"tab_id": tab_id},
        headers=AUTH_HEADERS,
    )
    assert closed.status_code == 200
    assert closed.json()["ok"] is True


async def test_workspace_create_delete_route(client):
    created = await client.post(
        "/api/v1/features/workspaces",
        json={"name": "Temp WS", "description": "route test"},
        headers=AUTH_HEADERS,
    )
    assert created.status_code == 200
    body = created.json()
    ws = body.get("workspace") or body
    assert ws["name"] == "Temp WS"
    # owner must be a stable id (user UUID), not a memory address like '22403...'
    owner = str(ws.get("owner", ""))
    assert owner and not owner.isdigit()

    deleted = await client.delete(
        f"/api/v1/features/workspaces/{ws['id']}",
        headers=AUTH_HEADERS,
    )
    assert deleted.status_code == 200
    assert deleted.json()["ok"] is True
