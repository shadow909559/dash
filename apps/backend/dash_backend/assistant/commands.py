"""Owner command handlers (spec #74/#75/#76) — the chat-facing surface.

Maps natural owner commands to real engine calls. Used by the command
interceptor / chat brain so "what needs my attention?" answers from
structured data instead of an LLM hallucinating status. Every answer is
grounded in store state — never fabricated.
"""

from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _store():
    from dash_backend.assistant.crm_store import get_crm_store
    return get_crm_store()


def handle_attention() -> str | None:
    """'what needs my attention' → grouped, deduplicated summary."""
    from dash_backend.assistant.attention import get_attention_engine
    return get_attention_engine().format_for_owner()


def handle_client_status(client_name: str) -> str | None:
    """'what's happening with Acme?' → grounded client context (spec #9/#20)."""
    from dash_backend.assistant.intel import client_context
    ctx = client_context(_store(), client_name)
    if ctx is None:
        return None
    lines = [f"Client: {ctx['client']['name']} ({ctx['client'].get('organization', '')})"]
    if ctx["open_requirements"]:
        lines.append(f"Open requirements ({len(ctx['open_requirements'])}):")
        for r in ctx["open_requirements"][-4:]:
            marker = " (needs clarification)" if r["status"] == "clarification_needed" else ""
            lines.append(f"  • {r['text'][:80]} [{r['status']}]{marker}")
    else:
        lines.append("No open requirements.")
    lc = ctx.get("last_communication")
    if lc:
        lines.append(
            f"Last communication: {lc['direction']} "
            f"({time.strftime('%Y-%m-%d', time.localtime(lc['when']))}) — "
            f"{lc['summary'][:70]}"
        )
    nm = ctx.get("next_meeting")
    if nm:
        lines.append("Next meeting: "
                     f"{nm['title']} at "
                     f"{time.strftime('%Y-%m-%d %H:%M', time.localtime(nm['scheduled_at']))}")
    if ctx["pending_follow_ups"]:
        lines.append(f"Follow-ups owed: {ctx['pending_follow_ups']}")
    return "\n".join(lines)


def handle_client_promises(client_name: str) -> str | None:
    """'what did I promise Acme?' — commitments and open asks on record."""
    store = _store()
    client = store.get_client(client_name)
    if client is None:
        return None
    actions = [a for a in store.list_action_items(status="pending")
               if a.get("client_id") == client["id"]]
    owed = [f for f in store.list_follow_ups(status="pending")
            if f.get("client_id") == client["id"]]
    reqs = [r for r in store.list_requirements(client_id=client["id"])
            if r.get("status") in ("confirmed", "planned", "approved")]
    lines = [f"Commitments and open asks for {client['name']}:"]
    if actions:
        lines.append("Action items (your commitments):")
        for a in actions:
            due = f" (due {a['due']})" if a.get("due") else ""
            lines.append(f"  • {a['text'][:80]}{due}")
    if reqs:
        lines.append("Confirmed/planned requirements:")
        for r in reqs[-4:]:
            lines.append(f"  • {r['text'][:80]} [{r['status']}]")
    if owed:
        lines.append(f"Follow-ups owed: {len(owed)}")
    if len(lines) == 1:
        lines.append("Nothing outstanding on record.")
    return "\n".join(lines)


def handle_client_waiting_for(client_name: str) -> str | None:
    """'what are we waiting for from Acme?' — pending clarifications,
    pending approvals, undelivered messages."""
    store = _store()
    client = store.get_client(client_name)
    if client is None:
        return None
    cid = client["id"]
    lines = [f"Waiting on, regarding {client['name']}:"]
    clar = [r for r in store.list_requirements(client_id=cid)
            if r.get("status") == "clarification_needed"]
    if clar:
        lines.append("Client clarification needed:")
        for r in clar:
            lines.append(f"  • {r['text'][:80]}")
    try:
        approvals = store._approvals.read().get("approvals", [])
        pending_appr = [a for a in approvals
                        if a.get("status") == "pending"
                        and a.get("client_id") == cid]
        if pending_appr:
            lines.append(f"Your approval: {len(pending_appr)} pending request(s)")
    except Exception:
        logger.exception("waiting_for: approvals read failed")
    undelivered = [c for c in store.list_communications(client_id=cid)
                   if c.get("direction") == "outgoing" and not c.get("sent")]
    if undelivered:
        lines.append(f"{len(undelivered)} outgoing message(s) never confirmed "
                     "delivered — the provider boundary recorded them as drafts")
    if len(lines) == 1:
        lines.append("Nothing — no open questions, approvals or undelivered "
                     "messages on record.")
    return "\n".join(lines)


def handle_outstanding_commitments(client_name: str | None = None) -> str | None:
    """'what are we waiting for?' — commitments + clarifications (spec #20)."""
    store = _store()
    client = store.get_client(client_name) if client_name else None
    reqs = store.list_requirements(
        client_id=client["id"] if client else None,
        status="clarification_needed",
    )
    items = store.list_action_items(status="pending")
    lines: list[str] = []
    if reqs:
        lines.append("Waiting on clarification:")
        for r in reqs[:4]:
            lines.append(f"  • {r['text'][:90]}")
    if items:
        lines.append("Action items owed:")
        for a in items[:4]:
            lines.append(f"  • {a['text'][:90]} (owner: {a['owner']})")
    return "\n".join(lines) if lines else None


def handle_meeting_briefing(meeting_id: str) -> str | None:
    from dash_backend.assistant.meeting_engine import get_meeting_engine
    briefing = get_meeting_engine().prepare_briefing(meeting_id)
    if briefing is None:
        return None
    lines = [f"Briefing for: {briefing['meeting']}"]
    if briefing.get("client"):
        lines.append(f"Client: {briefing['client']}")
    if briefing.get("project"):
        lines.append(f"Project: {briefing['project']}")
    open_reqs = briefing.get("open_requirements") or []
    if open_reqs:
        lines.append("Open requirements:")
        for r in open_reqs[-5:]:
            lines.append(f"  • {r['text'][:80]} [{r['status']}]")
    if briefing.get("questions_to_ask"):
        lines.append("Questions to ask:")
        for q in briefing["questions_to_ask"][:3]:
            lines.append(f"  • {q}")
    return "\n".join(lines)


def handle_meeting_summary(meeting_id: str) -> str | None:
    meeting = _store().get_meeting(meeting_id)
    if meeting is None or not meeting.get("summary"):
        return None
    s = meeting["summary"]
    lines = [
        f"Meeting summary: {meeting['title']}",
        f"Participants: {', '.join(s.get('participants', [])) or 'unknown'}",
        f"Turns: {s.get('turns', 0)}",
    ]
    reqs = s.get("requirements_detected") or []
    if reqs:
        lines.append("Requirements detected:")
        for r in reqs[:5]:
            lines.append(f"  • {r['text'][:80]} (confidence {r['confidence']})")
    flagged = s.get("commitments_flagged") or []
    if flagged:
        lines.append("Commitments flagged (none authorized):")
        for c in flagged[:3]:
            lines.append(f"  • {c['text'][:80]}")
    return "\n".join(lines)


def handle_briefing() -> str | None:
    """'daily briefing' → the executive brief (spec #77)."""
    from dash_backend.assistant.control import daily_briefing
    return daily_briefing(_store())["text"]


# Command patterns tried by the chat integration before any LLM call.
_PATTERNS: list[tuple[str, Any]] = [
    ("what needs my attention", lambda _: handle_attention()),
    ("what needs attention", lambda _: handle_attention()),
    ("what are you doing", lambda _:
        "I'm monitoring your clients, tasks and approvals. "
        "Ask 'what needs my attention?' for specifics."),
    ("what changed", lambda _: handle_attention()),
    ("daily briefing", lambda _: handle_briefing()),
    ("good morning", lambda _: handle_briefing()),
    ("what did you do today", lambda _: handle_today()),
    ("show me what you did today", lambda _: handle_today()),
]


def handle_today() -> str:
    """'show me what you did today' — count of real recorded actions."""
    from dash_backend.assistant.observe import actions_today
    return actions_today()


# ── Natural-language approvals (spec #129/#130) ──────────────────────

_APPROVE_PATTERNS = ("approve it", "approve that", "approve the message",
                     "approve", "yes, approve")
_REJECT_PATTERNS = ("reject it", "reject that", "don't send it",
                    "dont send it", "deny it", "reject")


def _parse_approval_decision(text: str) -> str | None:
    """Map a natural decision phrase to approve/reject — only when the
    message is clearly a decision (starts with a decision verb), so a
    passing mention of 'approve' never resolves anything.

    Injection hardening (spec #58/#137): a decision is a SHORT utterance,
    never a document. A pasted contract/email that merely begins with
    'approve …' (or rides 'approve it' in front of pages of content) is
    DATA and must reach the LLM path, not resolve a pending approval.
    The bare single-word verb ("approve"/"reject") resolves only as the
    entire message.
    """
    if len(text) > _DECISION_MAX_LEN:
        return None  # long content is data, not a decision
    for p in _APPROVE_PATTERNS:
        if text.startswith(p) and (
            len(p.split()) > 1 or text == p
        ):
            return "approve"
    for p in _REJECT_PATTERNS:
        if text.startswith(p) and (
            len(p.split()) > 1 or text == p
        ):
            return "reject"
    return None


async def _resolve_latest_pending(decision: str) -> str:
    """Resolve the oldest pending approval via the REAL engine — the same
    path the REST endpoint uses. Scope: ONCE unless the owner says more
    (tighten-only, spec #136)."""
    from dash_backend.assistant.authority import get_approval_engine
    from dash_backend.assistant.crm_store import get_crm_store
    from dash_backend.services.audit_logs import get_audit_service
    pending = get_crm_store().list_approvals(status="pending")
    if not pending:
        return ("There are no pending approvals right now — nothing was "
                "resolved.")
    oldest = min(pending, key=lambda a: a.get("requested_at", 0))
    rec = get_approval_engine().resolve(
        get_crm_store(), get_audit_service(), oldest["id"], decision,
        by="owner:chat",
    )
    if rec is None:
        return (f"Approval {oldest['id']} is no longer pending (expired or "
                "already resolved) — nothing was changed.")
    label = oldest.get("description", oldest.get("action_kind", "action"))
    if decision == "approve":
        return (f"Approved (one-time): {label[:80]}. The stored grant is "
                "what authorizes the send — it is consumed on use.")
    return f"Rejected: {label[:80]}. No message will be sent."

_STOP_MARKERS = ("pause all autonomous", "stop all autonomous",
                 "emergency stop")
_RESUME_MARKERS = ("resume autonomous", "resume tasks")
# A decision command is a short utterance; anything longer is pasted
# content and must never resolve an approval (spec #58/#137).
_DECISION_MAX_LEN = 120


def try_assistant_command(message: str) -> str | None:
    """Return a grounded answer if the message is an assistant command,
    else None (caller falls through to the normal chat path)."""
    text = (message or "").strip().lower()
    if not text:
        return None
    for pattern, handler in _PATTERNS:
        if pattern in text:
            try:
                return handler(text)
            except Exception:
                logger.exception("assistant command failed: %s", pattern)
                return None
    # Client-status shape: "what's happening with X" / "status of X"
    for marker in ("what's happening with ", "whats happening with ",
                   "status of ", "how is "):
        if text.startswith(marker):
            name = message[len(marker):].strip().rstrip("?").strip()
            if name:
                return handle_client_status(name)
    # Commitment/waiting shapes (spec #20): "what did I promise X",
    # "what are we waiting for from X"
    for marker in ("what did i promise ", "what did we promise ",
                   "what have i promised "):
        if text.startswith(marker):
            name = message[len(marker):].strip().rstrip("?").strip()
            if name:
                return handle_client_promises(name)
    for marker in ("what are we waiting for from ", "what is owed by "):
        if text.startswith(marker):
            name = message[len(marker):].strip().rstrip("?").strip()
            if name:
                return handle_client_waiting_for(name)
    return None


async def try_assistant_command_async(message: str) -> str | None:
    """Async variant used by the websocket chat path: everything the sync
    router handles, plus the control commands that need the event loop
    (emergency stop pauses async orchestrator tasks) and natural-language
    approval decisions (spec #129/#130).
    """
    text = (message or "").strip().lower()
    # Natural-language approval (spec #129/#130): "approve it", "reject
    # it" → the SAME authenticated resolve the API uses. Decisions are
    # SHORT whole utterances (see _parse_approval_decision) — pasted
    # content never resolves anything, and the stored grant (not the
    # words) is what authorizes later action (spec #61/#137). Voice-only
    # remains insufficient for OWNER_ONLY actions — resolve() enforces
    # stored grants at execution time.
    decision = _parse_approval_decision(text)
    if decision is not None:
        return await _resolve_latest_pending(decision)
    # Control commands (spec #41/#109) — matched as COMMAND SHAPE only:
    # start-of-message. A question *about* the emergency stop
    # ("what is the emergency stop procedure?") is information-seeking,
    # not an order, and must reach the normal chat path (spec #137: no
    # authority escalation through prompt content).
    if any(text.startswith(m) for m in _STOP_MARKERS):
        from dash_backend.assistant.control import emergency_stop
        from dash_backend.assistant.crm_store import get_crm_store
        from dash_backend.services.audit_logs import get_audit_service
        try:
            from dash_backend.autonomous.task_orchestrator import get_task_orchestrator
            orch = get_task_orchestrator()
        except Exception:
            orch = None
        result = await emergency_stop(
            get_crm_store(), get_audit_service(), orchestrator=orch)
        return ("Emergency stop active. "
                f"{len(result['paused_tasks'])} task(s) paused, "
                f"{len(result['revoked_approvals'])} pending approval(s) "
                "revoked, outbound sends gated. Say 'resume autonomous' to "
                "lift the gate — paused tasks stay paused until you resume "
                "each one.")
    if any(text.startswith(m) for m in _RESUME_MARKERS):
        from dash_backend.assistant.control import resume_from_emergency_stop
        from dash_backend.services.audit_logs import get_audit_service
        resume_from_emergency_stop(get_audit_service())
        return ("Gate lifted. Outbound sends need approval again as normal. "
                "Paused tasks remain paused — tell me which one to resume.")
    return try_assistant_command(message)
