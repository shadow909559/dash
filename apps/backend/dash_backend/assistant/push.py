"""WebSocket push for assistant events (decisions.md #92).

Follows the exact registration/send pattern of
``autonomous/task_push.py`` (which follows ``services/trigger_push.py``):
sockets registered by the /ws endpoint, sends marshalled onto the
captured loop, best-effort delivery — the REST polling endpoints remain
the reconciliation fallback, so a dropped push can never show state the
next poll would contradict.

Message types (one envelope shape, no protocol change):

    {"type": "approval.created",  "approval": {...}}   — full disclosure
    {"type": "approval.resolved", "approval": {...}}   — granted/rejected/expired
    {"type": "meeting.alert",     "meeting_id": ..., "alerts": [...]}

Payloads come from the authority engine's own records — no secrets, no
internal reasoning. DASH is a single-owner local system: when the caller
does not know a user_id, the event is pushed to every authenticated
socket (all of them belong to the local owner).
"""

from __future__ import annotations

import asyncio
import json
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# user_id -> list of live websockets (same shape as trigger_push/task_push)
_ASSISTANT_CONNECTIONS: dict[str, list] = {}
_loop: Optional[asyncio.AbstractEventLoop] = None


def register_assistant_socket(user_id: str, ws) -> None:
    global _loop
    _ASSISTANT_CONNECTIONS.setdefault(user_id, []).append(ws)
    if _loop is None:
        try:
            _loop = asyncio.get_running_loop()
        except RuntimeError:
            pass  # no loop (sync tests/scripts): the sync fallback delivers


def unregister_assistant_socket(user_id: str, ws) -> None:
    conns = _ASSISTANT_CONNECTIONS.get(user_id)
    if conns and ws in conns:
        conns.remove(ws)
        if not conns:
            _ASSISTANT_CONNECTIONS.pop(user_id, None)


def push_assistant_event(user_id: str | None, payload: dict[str, Any]) -> None:
    """Best-effort push; silently drops when no client or no loop.

    ``user_id=None`` broadcasts to every registered socket — valid because
    every socket is authenticated local-owner in this single-user system.
    """
    targets: list[str] = []
    if user_id:
        if _ASSISTANT_CONNECTIONS.get(user_id):
            targets.append(user_id)
    else:
        targets = list(_ASSISTANT_CONNECTIONS.keys())
    if not targets:
        return
    try:
        text = json.dumps(payload, default=str)
    except (TypeError, ValueError):
        return
    if _loop is None or _loop.is_closed():
        for uid in targets:
            _send_sync(uid, text)
        return
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    for uid in targets:
        if running is _loop:
            asyncio.ensure_future(_send_async(uid, text))
        else:
            asyncio.run_coroutine_threadsafe(_send_async(uid, text), _loop)


async def _send_async(user_id: str, text: str) -> None:
    for ws in list(_ASSISTANT_CONNECTIONS.get(user_id, [])):
        try:
            await ws.send_text(text)
        except Exception:
            unregister_assistant_socket(user_id, ws)


def _send_sync(user_id: str, text: str) -> None:
    """Synchronous fallback when no loop was ever registered (hermetic tests)."""
    for ws in list(_ASSISTANT_CONNECTIONS.get(user_id, [])):
        send = getattr(ws, "send_text_sync", None) or getattr(ws, "sync_send", None)
        if callable(send):
            try:
                send(text)
            except Exception:
                unregister_assistant_socket(user_id, ws)
