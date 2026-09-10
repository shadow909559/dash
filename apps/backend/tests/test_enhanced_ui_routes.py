"""Route-level tests for the new canvas/UI-facing enhanced endpoints.

Covers the endpoints added for the desktop UI pages:
- POST /enhanced/knowledge-graph/rebuild   (memory -> graph seeding)
- POST /enhanced/sounds/toggle             (master sounds on/off)
- POST /enhanced/dnd/exception/remove      (DND exception removal)

The live backend may predate these routes until restart; these tests run
the app in-process so they always exercise the current code.
"""

from __future__ import annotations

import os

import pytest

from tests.conftest import AUTH_HEADERS

pytestmark = pytest.mark.asyncio


@pytest.fixture()
def _kg_state(tmp_path, monkeypatch):
    monkeypatch.setenv("DASH_KG_STATE", str(tmp_path / "kg_route_state.json"))
    yield
    os.environ.pop("DASH_KG_STATE", None)


async def test_kg_rebuild_route(client, _kg_state):
    r = await client.post("/api/v1/enhanced/knowledge-graph/rebuild", headers=AUTH_HEADERS)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] is True
    for key in ("memories_scanned", "entities_extracted", "edges_created", "total_nodes"):
        assert key in d


async def test_sounds_toggle_route(client):
    r = await client.post("/api/v1/enhanced/sounds/toggle?enabled=false", headers=AUTH_HEADERS)
    assert r.status_code == 200
    assert r.json()["ok"] is True
    # state visible in GET
    g = await client.get("/api/v1/enhanced/sounds", headers=AUTH_HEADERS)
    assert g.status_code == 200
    assert g.json()["enabled"] is False
    await client.post("/api/v1/enhanced/sounds/toggle?enabled=true", headers=AUTH_HEADERS)


async def test_dnd_exception_remove_route(client):
    await client.post(
        "/api/v1/enhanced/dnd/exception?action=approval", headers=AUTH_HEADERS
    )
    r = await client.post(
        "/api/v1/enhanced/dnd/exception/remove?action=approval", headers=AUTH_HEADERS
    )
    assert r.status_code == 200
    assert r.json()["ok"] is True
    g = await client.get("/api/v1/enhanced/dnd", headers=AUTH_HEADERS)
    assert "approval" not in (g.json().get("exceptions") or [])
