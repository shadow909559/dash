"""Basic WebSocket endpoint for real-time communication."""

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger

router = APIRouter()
logger = get_logger(__name__)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """
    Basic WebSocket handler.

    Accepts JSON messages and echoes them back with a server timestamp.
    Foundation milestone only — no authentication or business logic.
    """
    await websocket.accept()
    client = websocket.client
    logger.info("WebSocket connected: %s:%s", client.host if client else "unknown", client.port if client else 0)

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                payload = json.loads(raw)
            except json.JSONDecodeError:
                payload = {"message": raw}

            response = {
                "type": "echo",
                "received": payload,
            }
            await websocket.send_json(response)
    except WebSocketDisconnect:
        logger.info("WebSocket disconnected")
    except Exception:
        logger.exception("WebSocket error")
        await websocket.close(code=1011)
