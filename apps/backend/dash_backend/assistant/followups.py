"""Client follow-up engine (spec #50, decisions.md #95).

Detects clients awaiting a response from REAL communication records:

    last communication for client is OUTGOING and older than the
    owner's configured follow_up_days  →  a follow-up is owed.

Nothing is sent automatically — the engine creates a *pending follow-up
record* (one per client, idempotent) and the proactive loop surfaces it;
the owner decides whether to draft, send, or dismiss. Silence is never
fabricated: a client whose last record is INCOMING needs nothing.
"""

from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def detect_follow_ups(store) -> list[dict[str, Any]]:
    """One idempotent pass over all clients. Returns new follow-ups."""
    created: list[dict[str, Any]] = []
    prefs = store.get_preferences()
    try:
        days = int(prefs.get("follow_up_days", 5))
    except (TypeError, ValueError):
        days = 5
    threshold = time.time() - days * 86400.0

    pending_by_client = {
        f.get("client_id") for f in store.list_follow_ups(status="pending")
    }
    for client in store.list_clients():
        if client["id"] in pending_by_client:
            continue  # already owed — never duplicate (spec #149)
        comms = store.list_communications(client_id=client["id"])
        if not comms:
            continue
        last = comms[-1]
        if last.get("direction") != "outgoing":
            continue  # client spoke last; we owe nothing
        if not last.get("sent"):
            # Delivery never confirmed — a different problem, handled by
            # the pipeline's own failure notification, not a follow-up.
            continue
        if last["created_at"] > threshold:
            continue  # still inside the silence window
        reason = (f"No response {days}+ days since last outgoing message "
                  f"({time.strftime('%Y-%m-%d', time.localtime(last['created_at']))}).")
        created.append(store.add_follow_up(
            client["id"], reason,
            last_communication_id=last.get("id")))
        logger.info("follow-up created for client %s", client["id"])
    return created
