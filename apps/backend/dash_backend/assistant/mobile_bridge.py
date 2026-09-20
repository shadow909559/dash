"""Android companion push bridge (spec #96, decisions.md #97).

Bridges assistant events to registered companion devices through the
existing PushNotificationService (services/mobile_companion.py).
send_push returns the honest split: ``queued`` = devices targeted (the
companion's fetch path: GET /api/v1/mobile/notifications) and
``delivered`` = provider-CONFIRMED sends only — 0 unless a real FCM
service account is configured (the transport boundary DASH_FCM_SERVICE
ACCOUNT occupies). Queued is never reported as delivered (spec #117).

What is pushed (all preference-gated, day-deduped):
  - approval.created  → "DASH needs approval" (the phone becomes an
    approval surface; resolve stays the authenticated REST endpoint)
  - urgent/critical proactive items (not important — avoid spam)
  - meeting.alert scope-change alerts

What is NEVER pushed: message content, secrets, client confidential
text — titles/bodies are operational summaries only (spec #115).
"""

from __future__ import annotations

import datetime as _dt
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_seen: dict[str, str] = {}  # dedupe key -> YYYY-MM-DD last sent

# Urgency floor for proactive items eligible for phone push. Read from
# owner preferences (notification_urgency_floor) with a safe default.
_URGENCY_ORDER = ["low", "normal", "important", "urgent", "critical"]


def _today() -> str:
    return _dt.date.today().isoformat()


def _fresh(key: str) -> bool:
    if _seen.get(key) == _today():
        return False
    _seen[key] = _today()
    return True


def reset_seen() -> None:
    _seen.clear()


def _push(title: str, body: str, data: dict[str, Any]) -> dict[str, Any] | None:
    try:
        from dash_backend.services.mobile_companion import push_service
        result = push_service.send_push(title, body, data=data)
        return result
    except Exception:
        logger.exception("mobile push failed")
        return None


def push_approval_request(approval: dict[str, Any], store) -> dict[str, Any] | None:
    """New approval request → phone. Day-deduped per approval id."""
    key = f"approval:{approval.get('id')}:{_today()}"
    if not _fresh(key):
        return None
    try:
        prefs = store.get_preferences()
        floor = prefs.get("notification_urgency_floor", "important")
        # An approval request is at least 'important' by definition; the
        # floor check only silences the phone when the owner set it to
        # urgent/critical (phone = urgent things only).
        if _URGENCY_ORDER.index(floor) > _URGENCY_ORDER.index("important"):
            return None
    except Exception:
        logger.exception("preferences read failed for mobile push (continuing)")
    return _push(
        title="DASH needs approval",
        body=f"{approval.get('description', 'Action')[:120]} — open Assistant Center to approve.",
        data={
            "kind": "approval_request",
            "approval_id": approval.get("id"),
            "risk_level": approval.get("risk_level"),
            "action": "resolve_approval",
        },
    )


def push_proactive_item(item: dict[str, Any], store=None) -> dict[str, Any] | None:
    """Proactive digest items → phone (day-deduped).

    Eligibility (decisions.md #119): urgent/critical by default, and the
    owner's notification_urgency_floor now applies when raised ABOVE the
    default — previously the floor was consulted for approvals only, so
    a floor of 'critical' still buzzed the phone for 'urgent' items.
    No store (legacy callers) → the pinned default applies.
    """
    urgency = (item.get("urgency") or "normal").lower()
    if urgency not in ("urgent", "critical"):
        return None
    if store is not None:
        try:
            from dash_backend.assistant.urgency import at_least, effective_floor
            floor = effective_floor("phone", floor_from_prefs(store))
            if not at_least(urgency, floor):
                return None
        except Exception:
            logger.exception("proactive push floor check failed (continuing)")
    key = f"proactive:{item.get('kind')}:{item.get('text', '')[:40]}:{_today()}"
    if not _fresh(key):
        return None
    return _push(
        title="DASH — urgent",
        body=item.get("text", "")[:160],
        data={"kind": "proactive", "item_kind": item.get("kind")},
    )


def floor_from_prefs(store) -> str:
    """Owner's notification_urgency_floor, defaulting safely."""
    try:
        from dash_backend.assistant.urgency import floor_from_preferences
        return floor_from_preferences(store.get_preferences())
    except Exception:
        return "important"


def push_meeting_alert(meeting_id: str, alerts: list[str]) -> dict[str, Any] | None:
    """Live meeting scope-change alerts → phone (day-deduped)."""
    key = f"meeting:{meeting_id}:{hash(tuple(alerts)) & 0xffffff}:{_today()}"
    if not _fresh(key):
        return None
    return _push(
        title="DASH — meeting alert",
        body=alerts[0][:160] if alerts else "Live meeting alert.",
        data={"kind": "meeting_alert", "meeting_id": meeting_id},
    )
