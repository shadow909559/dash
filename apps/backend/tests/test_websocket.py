"""WebSocket protocol tests (device-token authenticated)."""

import json

import pytest
from fastapi.testclient import TestClient

from dash_backend.main import app
from tests.conftest import _TEST_TOKEN

client = TestClient(app)


def _ws_url(token: str | None) -> str:
    if token is None:
        return "/api/v1/ws"
    return f"/api/v1/ws?token={token}"


def test_websocket_rejects_missing_token() -> None:
    """Unauthenticated sockets must be rejected before accept (4401/403)."""
    with pytest.raises(Exception):
        with client.websocket_connect(_ws_url(None)):
            pass


def test_websocket_rejects_invalid_token() -> None:
    with pytest.raises(Exception):
        with client.websocket_connect(_ws_url("forged-invalid-token")):
            pass


def test_websocket_session_info_after_auth() -> None:
    """With a valid device token, the first message received is session.info."""
    with client.websocket_connect(_ws_url(_TEST_TOKEN)) as websocket:
        # A ping triggers the session.info greeting.
        websocket.send_text(json.dumps({"type": "ping"}))
        raw = websocket.receive_text()

    payload = json.loads(raw)
    assert payload["type"] == "session.info"
    assert payload.get("session_id")


def test_websocket_unknown_type_returns_error() -> None:
    """An unsupported message type must produce a chat.error (protocol error),
    not a fake assistant message, and must never surface as a user message."""
    with client.websocket_connect(_ws_url(_TEST_TOKEN)) as websocket:
        # A ping triggers session.info first, then a pong.
        websocket.send_text(json.dumps({"type": "ping"}))
        greeting = json.loads(websocket.receive_text())
        assert greeting["type"] == "session.info"
        json.loads(websocket.receive_text())  # consume pong

        # An unsupported message type must be rejected cleanly.
        websocket.send_text(json.dumps({"type": "not_a_real_type", "message_id": "m1"}))
        raw = websocket.receive_text()

    payload = json.loads(raw)
    assert payload["type"] == "chat.error"
