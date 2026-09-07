"""WebSocket endpoint for remote desktop streaming.

Streams live screen captures to mobile clients.
Supports multi-monitor, adjustable quality, mouse/keyboard relay.
AUTHENTICATION IS REQUIRED to prevent unauthorized screen access.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from dash_backend.logging_config import get_logger
from dash_backend.desktop.screen_stream import get_screen_streamer
from dash_backend.auth.security import InvalidTokenError, decode_access_token
from dash_backend.security.local_identity import verify_device_token
from dash_backend.services.audit_logs import get_audit_service
from dash_backend.auth.dependencies import get_current_user_id

router = APIRouter()
logger = get_logger(__name__)

_active_streams: dict[str, dict[str, Any]] = {}


@router.websocket("/ws/remote-desktop")
async def remote_desktop_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for remote desktop streaming. Requires auth."""
    await websocket.accept()

    # Authenticate before streaming any frames
    authenticated_user = None
    try:
        auth_msg = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
        msg = json.loads(auth_msg)
        if msg.get("type") == "auth":
            token = msg.get("access_token", "") or msg.get("token", "")
            if verify_device_token(token):
                authenticated_user = "device_owner"
            else:
                payload = decode_access_token(token)
                if payload and payload.get("sub"):
                    authenticated_user = payload["sub"]
                else:
                    await websocket.send_json({"type": "error", "error": "Invalid token"})
                    await websocket.close(code=4001)
                    return
        else:
            await websocket.send_json({"type": "error", "error": "First message must be auth"})
            await websocket.close(code=4001)
            return
    except asyncio.TimeoutError:
        await websocket.send_json({"type": "error", "error": "Authentication timeout"})
        await websocket.close(code=4001)
        return
    except (json.JSONDecodeError, InvalidTokenError, Exception):
        await websocket.send_json({"type": "error", "error": "Authentication failed"})
        await websocket.close(code=4001)
        return

    session_id = str(uuid.uuid4())
    client_host = websocket.client.host if websocket.client else "unknown"
    logger.info("Remote desktop client connected: user=%s session=%s host=%s", authenticated_user, session_id, client_host)

    # Audit log the session start
    try:
        audit = get_audit_service()
        audit.log(
            event_type="remote_desktop",
            user_id=authenticated_user or "",
            action="session_start",
            category="remote_desktop",
            status="success",
            details={"session_id": session_id, "host": client_host},
            source_ip=client_host,
        )
    except Exception:
        pass

    streamer = get_screen_streamer()
    frame_queue: asyncio.Queue = asyncio.Queue(maxsize=10)

    _active_streams[session_id] = {
        "ws": websocket,
        "queue": frame_queue,
        "quality": 70,
        "fps": 15,
        "monitor": 0,
    }

    # Start streaming task
    stream_task = asyncio.create_task(streamer.stream_to_client(session_id, frame_queue))

    try:
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=0.05)
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": time.time()})
                    elif msg_type == "set_quality":
                        quality = msg.get("quality", 70)
                        streamer.set_quality(quality)
                        _active_streams[session_id]["quality"] = quality
                    elif msg_type == "set_fps":
                        fps = msg.get("fps", 15)
                        streamer.set_fps(fps)
                        _active_streams[session_id]["fps"] = fps
                    elif msg_type == "set_monitor":
                        monitor = msg.get("monitor", 0)
                        streamer.set_monitor(monitor)
                        _active_streams[session_id]["monitor"] = monitor
                    elif msg_type == "get_monitors":
                        monitors = streamer.get_monitors()
                        await websocket.send_json({
                            "type": "monitors",
                            "data": monitors,
                            "timestamp": time.time(),
                        })
                    elif msg_type == "mouse_move":
                        x = msg.get("x", 0)
                        y = msg.get("y", 0)
                        try:
                            import pyautogui
                            pyautogui.moveTo(x, y)
                        except ImportError:
                            pass
                    elif msg_type == "mouse_click":
                        button = msg.get("button", "left")
                        try:
                            import pyautogui
                            pyautogui.click(button=button)
                        except ImportError:
                            pass
                    elif msg_type == "key_press":
                        key = msg.get("key", "")
                        try:
                            import pyautogui
                            pyautogui.press(key)
                        except ImportError:
                            pass
                    elif msg_type == "type_text":
                        text = msg.get("text", "")
                        try:
                            import pyautogui
                            pyautogui.write(text)
                        except ImportError:
                            pass
                    elif msg_type == "scroll":
                        clicks = msg.get("clicks", 1)
                        try:
                            import pyautogui
                            pyautogui.scroll(clicks)
                        except ImportError:
                            pass
                except (json.JSONDecodeError, Exception):
                    pass
            except asyncio.TimeoutError:
                pass

            # Send next frame if available
            try:
                frame = await asyncio.wait_for(frame_queue.get(), timeout=0.01)
                await websocket.send_json({
                    "type": "frame",
                    "data": frame,
                    "timestamp": time.time(),
                })
            except asyncio.TimeoutError:
                pass

    except WebSocketDisconnect:
        logger.info("Remote desktop client disconnected: %s", client_host)
    except Exception as exc:
        logger.debug("Remote desktop WS error: %s", exc)
    finally:
        stream_task.cancel()
        try:
            await stream_task
        except asyncio.CancelledError:
            pass
        _active_streams.pop(session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


@router.get("/remote-desktop/status")
async def remote_desktop_status(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Get remote desktop streaming status."""
    streamer = get_screen_streamer()
    return {
        "active_streams": len(_active_streams),
        "streamer": streamer.get_stats(),
    }
