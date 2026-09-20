"""WebSocket push for task orchestrator progress (decisions.md #90).

Follows the exact registration/send pattern of ``services/trigger_push.py``
(decisions.md #80): sockets registered by the /ws endpoint, sends marshalled
onto the captured loop, best-effort delivery — the REST polling endpoints
remain the reconciliation fallback. No secrets in payloads: task snapshots
contain tool names/args the user already sees in the REST route, and the
agent's internal reasoning text is never included.
"""

from __future__ import annotations

import asyncio
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# user_id -> list of live websockets (same shape as trigger_push)
_TASK_CONNECTIONS: dict[str, list] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


def register_task_socket(user_id: str, ws) -> None:
    global _loop
    _TASK_CONNECTIONS.setdefault(user_id, []).append(ws)
    if _loop is None:
        _loop = asyncio.get_running_loop()


def unregister_task_socket(user_id: str, ws) -> None:
    conns = _TASK_CONNECTIONS.get(user_id)
    if conns and ws in conns:
        conns.remove(ws)
        if not conns:
            _TASK_CONNECTIONS.pop(user_id, None)


def push_task_event(user_id: str | None, payload: dict[str, Any]) -> None:
    """Best-effort push; silently drops when no client or no loop."""
    if not user_id or not _TASK_CONNECTIONS.get(user_id):
        return
    text = None
    try:
        import json
        text = json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return
    if _loop is None or _loop.is_closed():
        _send_sync(user_id, text)
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    if running is _loop:
        asyncio.ensure_future(_send_async(user_id, text))
    else:
        asyncio.run_coroutine_threadsafe(_send_async(user_id, text), _loop)


async def _send_async(user_id: str, text: str) -> None:
    for ws in list(_TASK_CONNECTIONS.get(user_id, [])):
        try:
            await ws.send_text(text)
        except Exception:
            unregister_task_socket(user_id, ws)


def _send_sync(user_id: str, text: str) -> None:
    """Synchronous fallback when no loop was ever registered (hermetic tests)."""
    for ws in list(_TASK_CONNECTIONS.get(user_id, [])):
        send = getattr(ws, "send_text_sync", None) or getattr(ws, "sync_send", None)
        if callable(send):
            try:
                send(text)
            except Exception:
                unregister_task_socket(user_id, ws)
