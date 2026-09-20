"""REST contract for /assistant/presence/history (decisions.md #123).

The owner-observable view of the PresenceEngine: the endpoint must serve
the same real transitions the engine records — no fabrication, no
unauthenticated access, and the limit parameter must actually bound the
response.

Boots only the assistant router with the auth dependency overridden —
no full-app lifespan. Boot-heavy API tests hang on the third full-app
boot in one process (decisions.md #121); this test must not add to that
budget, and it exercises the exact route + dependency the desktop calls.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from dash_backend.assistant.routes import router
    from dash_backend.assistant.presence import reset_presence_engine
    from dash_backend.auth import dependencies as auth_deps

    reset_presence_engine()
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[auth_deps.get_current_user_id] = lambda: "test-user"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    reset_presence_engine()


def test_presence_history_rest_contract(client):
    from dash_backend.assistant.presence import get_presence_engine

    # Real transitions flow from the engine to the endpoint.
    engine = get_presence_engine()
    engine.claim("voice_loop", "speaking", "reply playback")
    engine.release("voice_loop")
    engine.claim("orchestrator", "executing", "task run")

    r = client.get("/api/v1/assistant/presence/history")
    assert r.status_code == 200, r.text
    items = r.json()
    states = [i["state"] for i in items]
    assert states == ["speaking", "idle", "executing"]
    assert items[0]["source"] == "voice_loop"
    assert items[2]["source"] == "orchestrator"
    # Monotonic, numeric epoch seconds (the UI formats these).
    times = [i["at"] for i in items]
    assert times == sorted(times)
    assert all(isinstance(t, (int, float)) for t in times)

    # The limit parameter actually bounds the response (newest last).
    r = client.get("/api/v1/assistant/presence/history?limit=2")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 2
    assert items[-1]["state"] == "executing"


def test_presence_history_limit_defaults_to_50(client):
    from dash_backend.assistant.presence import get_presence_engine

    engine = get_presence_engine()
    for i in range(60):
        engine.claim("chat", "thinking", f"run {i}")
        engine.release("chat")

    r = client.get("/api/v1/assistant/presence/history")
    assert r.status_code == 200, r.text
    items = r.json()
    assert len(items) == 50
    assert items[-1]["state"] == "idle"      # newest: the final release
    assert items[-2]["detail"] == "run 59"   # just before it
