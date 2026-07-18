"""WebSocket endpoint scaffold.

This provides only the connection plumbing (accept, receive, echo,
disconnect) that later milestones (remote control, streaming AI
responses, notifications, etc.) will build on. No authentication and
no business logic is implemented here.
"""

from typing import List

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from dash_backend.core.logging import get_logger

router = APIRouter()
logger = get_logger(__name__)


class ConnectionManager:
    """Tracks active WebSocket connections.

    Minimal in-memory implementation. A future milestone may replace
    this with a Redis-backed pub/sub manager for multi-process
    deployments.
    """

    def __init__(self) -> None:
        self._active_connections: List[WebSocket] = []

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._active_connections.append(websocket)
        logger.info("WebSocket connected (active=%d)", len(self._active_connections))

    def disconnect(self, websocket: WebSocket) -> None:
        if websocket in self._active_connections:
            self._active_connections.remove(websocket)
        logger.info("WebSocket disconnected (active=%d)", len(self._active_connections))


manager = ConnectionManager()


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket) -> None:
    """Minimal echo WebSocket endpoint.

    Accepts a connection, echoes back any text message it receives,
    and cleans up on disconnect. This is scaffolding only; real
    message routing/protocol handling belongs to a future milestone.
    """

    await manager.connect(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            logger.debug("WebSocket message received: %s", data)
            await websocket.send_text(data)
    except WebSocketDisconnect:
        manager.disconnect(websocket)
