"""Smoke test for the WebSocket echo scaffold."""

from fastapi.testclient import TestClient

from dash_backend.main import app

client = TestClient(app)


def test_websocket_echoes_message() -> None:
    with client.websocket_connect("/api/v1/ws") as websocket:
        websocket.send_text("hello")
        data = websocket.receive_text()

    assert data == "hello"
