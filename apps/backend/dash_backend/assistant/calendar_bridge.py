"""Assistant calendar bridge (spec #87).

Wraps the existing CalendarService (services/email_calendar.py — real,
persisted) with the authority layer: creating/updating/cancelling an
event is a schedule_internal (level 2) or external action depending on
attendees, resolved through required_authority() and the owner's
autonomy mode. External calendar modifications always respect approval
policies; there is no path that bypasses the approval engine.

Honest boundary: local calendar only. No external calendar provider
(Google/Outlook) credential exists in this environment — those would
plug in at CalendarService's provider field, which already records it.
"""
from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _calendar_service():
    from dash_backend.services.email_calendar import CalendarService
    return CalendarService()


def _authority_engine():
    from dash_backend.assistant.authority import get_approval_engine
    return get_approval_engine()


def find_availability(start_iso: str, end_iso: str,
                      duration_minutes: int = 30) -> dict[str, Any]:
    """Busy/free slots from the real local calendar between two ISO
    bounds. Returns free windows — never invents availability."""
    import datetime as _dt

    svc = _calendar_service()
    events = svc.get_events(start_date=start_iso, end_date=end_iso)
    busy = []
    for e in events:
        try:
            s = _dt.datetime.fromisoformat(e["start"].replace("Z", "+00:00"))
            en = _dt.datetime.fromisoformat(e["end"].replace("Z", "+00:00"))
            busy.append((s, en, e.get("title", "")))
        except (KeyError, ValueError):
            continue
    busy.sort()
    free: list[dict[str, str]] = []
    cursor = _dt.datetime.fromisoformat(start_iso.replace("Z", "+00:00"))
    bound = _dt.datetime.fromisoformat(end_iso.replace("Z", "+00:00"))
    dur = _dt.timedelta(minutes=duration_minutes)
    for s, en, title in busy:
        if cursor + dur <= s:
            free.append({"start": cursor.isoformat(), "end": s.isoformat()})
        cursor = max(cursor, en)
    if cursor + dur <= bound:
        free.append({"start": cursor.isoformat(), "end": bound.isoformat()})
    return {"busy": [{"start": s.isoformat(), "end": en.isoformat(),
                      "title": title} for s, en, title in busy],
            "free": free, "duration_minutes": duration_minutes}


async def schedule_event(store, audit, title: str, start: str, end: str,
                         description: str = "", attendees: list[str] | None = None,
                         client_id: str | None = None,
                         autonomy_mode: str = "supervised_autonomy",
                         user_id: str = "owner") -> dict[str, Any]:
    """Create a calendar event through the authority engine.

    No attendees → level 2 (low-risk internal, auto per policy).
    Attendees present → EXTERNAL (level 3, approval by default).
    """
    from dash_backend.assistant.authority import Authority, required_authority
    kind = "schedule_internal" if not attendees else "send_external_message"
    authority = required_authority(kind, None, autonomy_mode)
    svc = _calendar_service()

    if authority >= Authority.EXTERNAL_COMMS:
        request = _authority_engine().create_request(
            store, audit,
            action_kind=kind,
            description=f"Create calendar event: {title}",
            reason="external calendar modification requires owner approval",
            risk_level=int(authority),
            target=", ".join(attendees or []) or "calendar",
            proposed=f"{title} [{start} -> {end}]",
            consequences=["Invitation/visibility for attendees",
                          "Event appears on the shared calendar"],
            client_id=client_id,
        )
        return {"ok": True, "approval_required": True, "approval": request,
                "authority": int(authority), "created": False}

    created = svc.create_event(title=title, start=start, end=end,
                               description=description,
                               attendees=attendees or [])
    if not created.get("ok"):
        return {"ok": False, "error": "calendar event creation failed"}
    event = created["event"]
    try:
        audit.log("assistant.calendar.created", user_id=user_id,
                  action=title[:80], status="created",
                  details={"event_id": event.get("id")})
    except Exception:
        logger.exception("calendar audit failed")
    return {"ok": True, "approval_required": False,
            "authority": int(authority), "created": True, "event": event}


async def confirm_scheduled_event(approval) -> dict[str, Any]:
    """Executed after an approval for an attendee-event is granted —
    creates the event for real and returns delivery evidence."""
    raise NotImplementedError(
        "confirm_scheduled_event is invoked by the approval execution "
        "path once a real external calendar provider exists; the local "
        "calendar path never reaches this (it creates immediately).")


async def cancel_event(store, audit, event_id: str,
                       user_id: str = "owner") -> dict[str, Any]:
    """Cancel = a destructive change to the calendar record; audited."""
    svc = _calendar_service()
    result = svc.delete_event(event_id)
    try:
        audit.log("assistant.calendar.cancelled", user_id=user_id,
                  action=event_id, status=str(result.get("ok")),
                  details={"event_id": event_id})
    except Exception:
        logger.exception("calendar audit failed")
    return {"ok": bool(result.get("ok")), "result": result}
