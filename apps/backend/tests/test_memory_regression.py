"""Regression test: GET /memory/{id} must return 200 (not greenlet 500).

Root cause fixed in memory/service.py: access-stat updates commit and expire
ORM attributes; serialization then triggered lazy loads outside a greenlet.
The service now refreshes the instance after the stats commit.
"""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from dash_backend.main import create_app
from tests.conftest import AUTH_HEADERS


@pytest.fixture
async def memory_client():
    app = create_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test", headers=AUTH_HEADERS) as ac:
        yield ac


@pytest.mark.asyncio
async def test_create_then_get_memory_by_id(memory_client: AsyncClient) -> None:
    import uuid as _uuid

    marker = f"DASH regression { _uuid.uuid4().hex[:8] }"
    created = await memory_client.post(
        "/api/v1/memory",
        json={
            "content": marker,
            "category": "test",
            "type": "fact",
            "importance": 0.5,
        },
    )
    assert created.status_code == 201, created.text
    memory_id = created.json()["id"]

    # This exact call used to 500 with MissingGreenlet.
    fetched = await memory_client.get(f"/api/v1/memory/{memory_id}")
    assert fetched.status_code == 200, fetched.text

    body = fetched.json()
    assert body["id"] == memory_id
    assert body["content"] == marker
    # Service normalizes category->type with capitalized names; explicit
    # type must round-trip case-insensitively.
    assert body["type"].lower() == "fact"
