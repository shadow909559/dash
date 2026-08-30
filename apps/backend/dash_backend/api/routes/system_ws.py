"""WebSocket endpoint for real-time system monitoring.

Broadcasts system metrics (CPU, RAM, GPU, storage, network, battery, system,
processes, applications, services, devices, windows, files, events)
to connected clients every second.

Protocol:
    Client connects to /api/v1/ws/system
    Server sends JSON snapshots every second:
    { "type": "system", "data": { cpu: {}, ram: {}, ... }, "timestamp": 1234567890.0 }

Features:
    - Heartbeat / ping-pong
    - Device registry
    - Session management
    - Automatic reconnect
    - zlib compression (negotiated via subscribe)
    - Delta updates (only changed values sent after first full snapshot)
    - Cache
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
import zlib
from typing import Any

from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.logging_config import get_logger
from dash_backend.security.local_identity import verify_device_token
from dash_backend.services.system import SystemMonitor, get_system_monitor

router = APIRouter()
logger = get_logger(__name__)

WS_UNAUTHORIZED_CODE = 4401


def _extract_ws_token(websocket: WebSocket) -> str | None:
    """Device token from query param (?token=...) or x-dash-token header."""
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.headers.get("x-dash-token")
    return token

# Active connections with session info
_active_connections: dict[str, dict[str, Any]] = {}
_broadcast_task: asyncio.Task[None] | None = None
_device_registry: dict[str, dict[str, Any]] = {}

# Compression threshold: payloads larger than this (in bytes) get zlib-compressed
_COMPRESSION_THRESHOLD = 512


def _compress_payload(payload: str) -> str:
    """Compress a JSON string with zlib and return base64-encoded compressed data.

    Returns the original string if compression doesn't reduce size.
    """
    raw_bytes = payload.encode("utf-8")
    if len(raw_bytes) < _COMPRESSION_THRESHOLD:
        return payload
    compressed = zlib.compress(raw_bytes, level=6)  # balanced speed/size
    # Only use compressed if it's actually smaller
    if len(compressed) < len(raw_bytes):
        import base64
        return f"__zlib__{base64.b64encode(compressed).decode('ascii')}"
    return payload


@router.websocket("/ws/system")
async def system_monitor_ws(websocket: WebSocket) -> None:
    """WebSocket endpoint for streaming live system metrics every second.

    Phase 12 optimizations:
      - Delta updates via SystemMonitor.get_delta_snapshot()
      - zlib compression for payloads > 512 bytes
      - Background collection loop started on first connect

    Authentication is mandatory: the handshake must carry the local device
    token (query `token` or header `x-dash-token`). System telemetry can
    reveal processes/windows/files and must never be served anonymously.
    """
    if not verify_device_token(_extract_ws_token(websocket)):
        await websocket.close(code=WS_UNAUTHORIZED_CODE)
        return

    await websocket.accept()
    session_id = str(uuid.uuid4())
    client_host = websocket.client.host if websocket.client else "unknown"
    client_info = {
        "session_id": session_id,
        "host": client_host,
        "connected_at": time.time(),
        "user_agent": websocket.headers.get("user-agent", "unknown"),
        "last_pong": time.time(),
    }
    _active_connections[session_id] = {
        "ws": websocket,
        "info": client_info,
        "last_snapshot": None,
        "use_compression": False,
        "use_deltas": True,
        "channels": None,
    }
    logger.info("System monitor client connected: %s (session=%s)", client_host, session_id)

    # Register device
    _device_registry[session_id] = {
        "host": client_host,
        "connected_at": time.time(),
        "last_seen": time.time(),
        "session_id": session_id,
    }

    monitor = get_system_monitor()

    # Start background collection on the SHARED singleton so both this
    # websocket and the /system/telemetry REST route serve cached snapshots
    # (previously a throwaway local instance was warmed up here while the
    # singleton used by REST collected synchronously on every request).
    await monitor.start_background_collection()

    # Ensure the global broadcast loop is running
    _ensure_broadcast_loop()

    try:
        # Keep connection alive; listen for client messages
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                try:
                    msg = json.loads(data)
                    msg_type = msg.get("type", "")

                    if msg_type == "ping":
                        await websocket.send_json({"type": "pong", "timestamp": time.time()})
                        _active_connections[session_id]["info"]["last_pong"] = time.time()
                    elif msg_type == "pong":
                        _active_connections[session_id]["info"]["last_pong"] = time.time()
                    elif msg_type == "subscribe":
                        channels = msg.get("channels", [])
                        use_compression = msg.get("compression", False)
                        use_deltas = msg.get("deltas", True)
                        _active_connections[session_id]["channels"] = channels or None
                        _active_connections[session_id]["use_compression"] = use_compression
                        _active_connections[session_id]["use_deltas"] = use_deltas
                        if not use_deltas:
                            monitor.reset_delta()
                        await websocket.send_json({
                            "type": "subscribed",
                            "channels": channels,
                            "compression": use_compression,
                            "deltas": use_deltas,
                            "timestamp": time.time(),
                        })
                    elif msg_type == "get_history":
                        category = msg.get("category", "cpu")
                        period = msg.get("period", "5m")
                        from dash_backend.services.system.performance_history import get_performance_history
                        ph = get_performance_history()
                        history_data = ph.get_history(category, period)
                        await websocket.send_json({
                            "type": "history",
                            "category": category,
                            "period": period,
                            "data": history_data,
                            "timestamp": time.time(),
                        })
                    elif msg_type == "get_full_snapshot":
                        snapshot = await monitor.get_latest_snapshot()
                        monitor.reset_delta()
                        await _send_to_client(websocket, {
                            "type": "system",
                            "data": snapshot,
                            "timestamp": time.time(),
                            "full": True,
                        }, conn_info=_active_connections[session_id])
                    elif msg_type == "get_processes":
                        from dash_backend.services.system.processes import get_processes
                        processes = get_processes(
                            limit=msg.get("limit", 50),
                            offset=msg.get("offset", 0),
                            sort_by=msg.get("sort_by", "cpu_percent"),
                            sort_desc=msg.get("sort_desc", True),
                            search=msg.get("search"),
                        )
                        await websocket.send_json({
                            "type": "processes",
                            "data": processes,
                            "timestamp": time.time(),
                        })
                except (json.JSONDecodeError, Exception):
                    pass
            except asyncio.TimeoutError:
                # Send a ping to check connection
                try:
                    await websocket.send_json({"type": "ping", "timestamp": time.time()})
                except Exception:
                    break
    except WebSocketDisconnect:
        logger.info("System monitor client disconnected: %s (session=%s)", client_host, session_id)
    except Exception as exc:
        logger.debug("System monitor WS error: %s", exc)
    finally:
        _active_connections.pop(session_id, None)
        _device_registry.pop(session_id, None)
        try:
            await websocket.close()
        except Exception:
            pass


async def _send_to_client(
    websocket: WebSocket,
    message_data: dict[str, Any],
    conn_info: dict[str, Any] | None = None,
) -> None:
    """Send message to client with optional compression."""
    use_compression = conn_info.get("use_compression", False) if conn_info else False
    payload = json.dumps(message_data, default=str)

    if use_compression:
        compressed = _compress_payload(payload)
        await websocket.send_text(compressed)
    else:
        await websocket.send_text(payload)


def _ensure_broadcast_loop() -> None:
    """Start the global broadcast loop if not already running."""
    global _broadcast_task
    if _broadcast_task is None or _broadcast_task.done():
        _broadcast_task = asyncio.create_task(_broadcast_loop())
        logger.debug("System monitor broadcast loop started")


async def _broadcast_loop() -> None:
    """Broadcast system snapshots to all connected clients every second.

    Phase 12: Uses SystemMonitor.get_delta_snapshot() to send only changed
    values after the first full snapshot. Supports zlib compression for
    payloads over 512 bytes.
    """
    monitor = get_system_monitor()
    while True:
        if not _active_connections:
            await asyncio.sleep(1)
            continue

        try:
            now = time.time()

            # Broadcast to all active connections
            disconnected: list[str] = []
            for session_id, conn in _active_connections.copy().items():
                try:
                    ws = conn["ws"]
                    channels = conn.get("channels")
                    use_deltas = conn.get("use_deltas", True)

                    # Get delta or full snapshot
                    if use_deltas:
                        snapshot_or_delta = await monitor.get_delta_snapshot()
                        is_full = "_d" not in snapshot_or_delta and conn.get("last_snapshot") is None
                    else:
                        snapshot_or_delta = await monitor.get_latest_snapshot()
                        is_full = True

                    # Build message
                    message_data: dict[str, Any] = {
                        "type": "system",
                        "data": snapshot_or_delta,
                        "timestamp": now,
                    }
                    if is_full:
                        message_data["full"] = True

                    # Filter by subscribed channels if needed
                    if channels:
                        filtered = {"type": "system", "timestamp": now, "data": {}}
                        for ch in channels:
                            if ch in snapshot_or_delta:
                                filtered["data"][ch] = snapshot_or_delta[ch]
                        if filtered["data"]:
                            await _send_to_client(ws, filtered, conn)
                    else:
                        await _send_to_client(ws, message_data, conn)

                    conn["last_snapshot"] = snapshot_or_delta
                except Exception:
                    disconnected.append(session_id)

            # Clean up disconnected clients
            for session_id in disconnected:
                _active_connections.pop(session_id, None)
                _device_registry.pop(session_id, None)

        except Exception as exc:
            logger.debug("Error in system broadcast loop: %s", exc)

        await asyncio.sleep(1)  # Broadcast every second


def get_device_registry() -> dict[str, Any]:
    """Return the current device registry."""
    return {
        "devices": list(_device_registry.values()),
        "total_connected": len(_active_connections),
    }


# ── REST endpoint for system stats (used by the desktop Orb HUD) ───────

def _as_percent(value: Any) -> float:
    """Coerce a metric value to a 0-100 float, falling back to 0.0."""
    try:
        return round(float(value), 1)
    except (TypeError, ValueError):
        return 0.0


@router.get("/system/stats")
async def get_system_stats(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Return a compact system stats snapshot for the Orb HUD.

    Aggregates the same data the /ws/system websocket streams, flattened into
    the lightweight shape the desktop UI expects:
        { cpu, gpu, ram, battery, storage, network }
    All values are percentages (0-100) unless otherwise noted.
    """
    monitor = get_system_monitor()
    # Idempotent: keeps the shared snapshot cache warm for instant reads.
    await monitor.start_background_collection()
    snapshot = await monitor.get_latest_snapshot()

    cpu = snapshot.get("cpu") or {}
    ram = snapshot.get("ram") or {}
    gpu = snapshot.get("gpu") or {}
    battery = snapshot.get("battery") or {}
    storage = snapshot.get("storage") or {}
    network = snapshot.get("network") or {}

    # GPU may be a list of devices or a dict; pick the first device percent.
    gpu_percent = 0.0
    if isinstance(gpu, list):
        if gpu and isinstance(gpu[0], dict):
            gpu_percent = _as_percent(gpu[0].get("percent"))
    elif isinstance(gpu, dict):
        gpu_percent = _as_percent(gpu.get("percent"))

    # Network: derive a percentage from link speed usage if available.
    network_percent = 0.0
    net_percent = network.get("percent")
    if net_percent is not None:
        network_percent = _as_percent(net_percent)

    return {
        "cpu": _as_percent(cpu.get("percent")),
        "gpu": gpu_percent,
        "ram": _as_percent(ram.get("percent")),
        "battery": _as_percent(battery.get("percent")),
        "storage": _as_percent(storage.get("percent")),
        "network": network_percent,
        "timestamp": time.time(),
    }


@router.get("/system/telemetry")
async def get_system_telemetry(user_id: str = Depends(get_current_user_id)) -> dict[str, Any]:
    """Return detailed system telemetry for the telemetry panel.

    Provides comprehensive system metrics including CPU, RAM, GPU, network,
    battery, and uptime information.
    """
    monitor = get_system_monitor()
    # Idempotent: keeps the shared snapshot cache warm for instant reads.
    await monitor.start_background_collection()
    snapshot = await monitor.get_latest_snapshot()

    cpu = snapshot.get("cpu") or {}
    ram = snapshot.get("ram") or {}
    gpu = snapshot.get("gpu") or {}
    battery = snapshot.get("battery") or {}
    network = snapshot.get("network") or {}
    system = snapshot.get("system") or {}

    # GPU handling
    gpu_percent = 0.0
    if isinstance(gpu, list):
        if gpu and isinstance(gpu[0], dict):
            gpu_percent = _as_percent(gpu[0].get("percent"))
    elif isinstance(gpu, dict):
        gpu_percent = _as_percent(gpu.get("percent"))

    # Network rates (bytes per second)
    network_up = network.get("up", 0) or 0
    network_down = network.get("down", 0) or 0

    # Battery percentage
    battery_percent = _as_percent(battery.get("percent"))

    # System uptime in seconds - use the correct key from system_info
    uptime = 0
    if isinstance(system, dict):
        uptime = system.get("uptime_seconds", 0) or 0

    return {
        "cpu": _as_percent(cpu.get("percent")),
        "ram": _as_percent(ram.get("percent")),
        "gpu": gpu_percent if gpu_percent > 0 else None,
        "network": {
            "up": network_up,
            "down": network_down,
        },
        "battery": battery_percent if battery_percent > 0 else None,
        "uptime": uptime,
        "timestamp": time.time(),
    }
