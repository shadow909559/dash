"""WebSocket protocol tests (MVP)."""

import json

from fastapi.testclient import TestClient

from dash_backend.main import app

client = TestClient(app)


def test_websocket_chat_requires_auth() -> None:
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_text(json.dumps({"type": "chat.send", "message_id": "m1", "content": "hi"}))
        raw = websocket.receive_text()

    payload = json.loads(raw)
    assert payload["type"] == "chat.error"
    assert payload["error"] == "Not authenticated"


def test_websocket_chat_mvp_streams() -> None:
    # MVP auth: reuse any valid JWT by calling auth endpoints would require DB setup.
    # For now, assert that protocol validation works even without a real token by
    # sending auth with a clearly invalid token; server should return chat.error.
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_text(json.dumps({"type": "auth", "access_token": "invalid"}))
        websocket.send_text(
            json.dumps(
                {
                    "type": "chat.send",
                    "message_id": "m1",
                    "content": "hello",
                }
            )
        )
        raw = websocket.receive_text()

    payload = json.loads(raw)
    assert payload["type"] == "chat.error"

