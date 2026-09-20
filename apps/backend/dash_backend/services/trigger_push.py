"""WebSocket push for workflow trigger state changes (decisions.md #80).

The Triggers tab polls every 5 s for counters (decisions.md #76); this
module adds server push so fires and pause/resume land the moment they
happen, over the EXISTING /ws connection and the same registration
pattern the notifications router uses — no new socket, no protocol
change beyond one message type:

    {"type": "trigger.update", "seq": N, "trigger": {snapshot}}

The snapshot is the engine's own state for that workflow at push time —
not a hand-built partial — so the client can merge it verbatim. Secrets
are never included (the webhook secret already reaches the local UI via
the authenticated REST route; push adds nothing to that surface, and a
live socket must not leak it to anything else that ever subscribes).

Delivery is best-effort by design: no connected client, a closed loop,
or a failed send drops the push silently — the poll remains the
reconciliation fallback, so push can never show state the next poll
would contradict. Safe to call from any thread (the scheduler's
to_thread worker and the bridge's bus callbacks included): the send is
marshalled onto the loop that registered the first socket.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# user_id -> list of live websockets (same shape as the notifications
# registry — the /ws endpoint registers each authenticated socket here).
_TRIGGER_CONNECTIONS: dict[str, list] = {}

# The app's event loop, captured at first registration. Sends from other
# threads are marshalled onto it; without a registered loop, pushes are
# dropped (nothing is listening anyway).
_main_loop: Optional[asyncio.AbstractEventLoop] = None

_seq = 0


def register_trigger_socket(user_id: str, websocket) -> None:
    """Register an authenticated /ws connection for trigger pushes."""
    global _main_loop
    _TRIGGER_CONNECTIONS.setdefault(user_id, []).append(websocket)
    try:
        _main_loop = asyncio.get_running_loop()
    except RuntimeError:
        pass


def unregister_trigger_socket(user_id: str, websocket) -> None:
    """Drop a connection (also called internally when a send fails)."""
    conns = _TRIGGER_CONNECTIONS.get(user_id)
    if conns is None:
        return
    _TRIGGER_CONNECTIONS[user_id] = [ws for ws in conns if ws is not websocket]
    if not _TRIGGER_CONNECTIONS[user_id]:
        del _TRIGGER_CONNECTIONS[user_id]


def _snapshot(engine: Any, workflow_id: str) -> Optional[dict]:
    """The engine's current trigger state for one workflow.

    Sections are included only when that trigger exists, so a workflow
    with a webhook but no schedule pushes no schedule key — the client
    merges, and an absent key can never erase real client state. Unknown
    workflow ids push nothing at all.
    """
    try:
        sched = engine.get_schedules().get(workflow_id)
        hook = engine.get_webhooks().get(workflow_id)
        trig = engine.get_event_triggers().get(workflow_id)
    except Exception:  # noqa: BLE001 — push must never break the engine path
        logger.exception("Trigger snapshot failed for %s", workflow_id)
        return None
    snap: dict[str, Any] = {"workflow_id": workflow_id, "at": time.time()}
    if sched is not None:
        snap["schedule"] = {
            "enabled": sched.get("enabled"),
            "cron": sched.get("cron"),
            "last_fired_at": sched.get("last_fired_at"),
            "last_status": sched.get("last_status"),
            "paused_since": sched.get("paused_since"),
            "skipped_fires": sched.get("skipped_fires", 0),
        }
    if hook is not None:
        # Deliberately no "secret": push rides an authenticated socket but
        # the snapshot must stay safe for any future broadcast widening.
        snap["webhook"] = {
            "webhook_id": hook.get("webhook_id"),
            "enabled": hook.get("enabled"),
            "trigger_count": hook.get("trigger_count"),
        }
    if trig is not None:
        snap["event"] = {
            "event": trig.get("event"),
            "enabled": trig.get("enabled"),
            "trigger_count": trig.get("trigger_count"),
            "last_fired_at": trig.get("last_fired_at"),
        }
    if len(snap) <= 2:  # only workflow_id + at: nothing to say
        return None
    return snap


def _schedule_send(payload: dict) -> None:
    """Deliver a push from any context.

    - On the app loop (route handlers): scheduled as a task.
    - From a worker thread (scheduler to_thread, file watcher): marshalled
      onto the app loop via call_soon_threadsafe.
    - No loop anywhere (sync script/test driving the engine directly):
      delivered synchronously on a fresh loop. Unreachable in production
      (a registered socket implies a registered loop), so the brief
      blocking send cannot stall a real fire path.
    """
    try:
        running = asyncio.get_running_loop()
    except RuntimeError:
        running = None
    loop = _main_loop
    if loop is not None and not loop.is_closed():
        if running is loop:
            loop.create_task(_broadcast(payload))
        else:
            loop.call_soon_threadsafe(lambda: loop.create_task(_broadcast(payload)))
        return
    if running is None:
        asyncio.run(_broadcast(payload))
    # else: a loop is running but none registered — nothing to send on.


async def _broadcast(payload: dict) -> None:
    dead: list[tuple[str, Any]] = []
    for user_id, conns in list(_TRIGGER_CONNECTIONS.items()):
        for ws in list(conns):
            try:
                await ws.send_json(payload)
            except Exception:  # noqa: BLE001 — dead socket, prune it
                dead.append((user_id, ws))
    for user_id, ws in dead:
        unregister_trigger_socket(user_id, ws)


def push_trigger_update(workflow_id: str, engine: Any = None) -> None:
    """Push the current trigger state for one workflow. Fire-and-forget.

    Never raises and never blocks: callers sit on hot paths (webhook
    fire, event fire, pause toggles, the scheduler's mark_fired).
    """
    global _seq
    try:
        if not any(_TRIGGER_CONNECTIONS.values()):
            return
        if engine is None:
            from dash_backend.services.workflow_builder import (
                workflow_engine as engine,
            )
        snap = _snapshot(engine, workflow_id)
        if snap is None:
            return
        _seq += 1
        _schedule_send({"type": "trigger.update", "seq": _seq, "trigger": snap})
    except Exception:  # noqa: BLE001 — a push failure must never fail the fire
        logger.exception("Trigger push failed for %s", workflow_id)
