"""REST contract for the quiet-hours preference (decisions.md #122).

Pins that quiet_hours is settable through PUT /assistant/preferences —
the surface the desktop Assistant Contact Policy panel uses — and that
the full policy round-trips: invalid values are rejected with 422, valid
windows persist, and a change is observable in the routing policy.

Boot-free by design (decisions.md #123): full-app boots deadlock on the
second/third boot in one process (observed again in the #128 gate).
Mounting only the assistant router with the auth dependency overridden
exercises the exact route + dependency the desktop calls, and the
preference store is isolated via DASH_CRM_DIR + singleton reset.
"""
from __future__ import annotations

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient


@pytest.fixture()
def client(monkeypatch, tmp_path):
    from dash_backend.assistant import crm_store
    from dash_backend.assistant.routes import router
    from dash_backend.auth import dependencies as auth_deps

    monkeypatch.setenv("DASH_CRM_DIR", str(tmp_path / "crm"))
    monkeypatch.setattr(crm_store, "_store", None)
    app = FastAPI()
    app.include_router(router, prefix="/api/v1")
    app.dependency_overrides[auth_deps.get_current_user_id] = lambda: "test-user"
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()
    monkeypatch.setattr(crm_store, "_store", None)


def test_quiet_hours_rest_roundtrip(client):
    # Defaults: never quiet
    r = client.get("/api/v1/assistant/preferences")
    assert r.status_code == 200, r.text
    assert r.json()["quiet_hours"] == {"start": 0, "end": 0}

    # Set an overnight window
    r = client.put("/api/v1/assistant/preferences",
                   json={"quiet_hours": {"start": 22, "end": 7}})
    assert r.status_code == 200, r.text
    assert r.json()["quiet_hours"] == {"start": 22, "end": 7}

    # Persists on re-read
    r = client.get("/api/v1/assistant/preferences")
    assert r.json()["quiet_hours"] == {"start": 22, "end": 7}

    # Invalid values rejected with 422 (pydantic validation)
    r = client.put("/api/v1/assistant/preferences",
                   json={"quiet_hours": {"start": 24, "end": 7}})
    assert r.status_code == 422, r.text


def test_quiet_hours_change_is_observable_in_routing(client):
    # A REST-set window changes the shared routing policy's decision —
    # the preference is wired to behavior, not just storage.
    r = client.put("/api/v1/assistant/preferences",
                   json={"quiet_hours": {"start": 22, "end": 7}})
    assert r.status_code == 200, r.text

    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.assistant.urgency import route_contact

    prefs = get_crm_store().get_preferences()
    day = route_contact("urgent", prefs=prefs, local_hour=lambda: 12)
    night = route_contact("urgent", prefs=prefs, local_hour=lambda: 23)
    assert "desktop" in day.channels
    assert "desktop" not in night.channels
    assert "ws" in night.channels  # ambient record never suppressed
