"""Client intelligence layer (spec #103/#104/#106/#144).

Everything here is deterministic retrieval over the real CRM store —
no LLM, no fabricated metrics. Answers to "what's happening with X"
come from structured queries plus light keyword search over record
text (spec #104: structured first, text search as the complement).
"""
from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# ── Keyword search over real records (spec #103/#104) ─────────────────

def search_intelligence(store, query: str, client_name: str | None = None) -> dict[str, Any]:
    """Search across every record type. Structured fields (status,
    client, dates) are matched too — this is a database query with a
    text fallback, never a guess."""
    q = (query or "").strip().lower()
    terms = [t for t in q.replace("?", " ").split() if len(t) >= 3]
    client = store.get_client(client_name) if client_name else None
    client_id = client["id"] if client else None

    def _match(text: str) -> bool:
        low = (text or "").lower()
        return any(t in low for t in terms)

    results: dict[str, list[dict[str, Any]]] = {
        "clients": [], "projects": [], "requirements": [],
        "communications": [], "meetings": [], "action_items": [],
        "follow_ups": [],
    }
    if not terms:
        return {"query": query, "counts": {k: 0 for k in results}, **results}

    for c in store.list_clients():
        if _match(f"{c.get('name')} {c.get('organization')} {c.get('notes', '')}"):
            results["clients"].append(_ref(c, "client", c.get("name")))
    for p in store.list_projects(client_id=client_id):
        if _match(f"{p.get('name')} {p.get('description', '')} {p.get('status', '')}"):
            results["projects"].append(_ref(p, "project", p.get("name")))
    for r in store.list_requirements(client_id=client_id):
        if _match(f"{r.get('text')} {r.get('status')}"):
            results["requirements"].append(_ref(
                r, "requirement", r.get("text", "")[:140],
                status=r.get("status"), confidence=r.get("confidence")))
    for com in store.list_communications(client_id=client_id):
        if _match(f"{com.get('summary')} {com.get('direction')} {com.get('channel')}"):
            results["communications"].append(_ref(
                com, "communication", com.get("summary", "")[:140],
                status="sent" if com.get("sent") else "recorded"))
    for m in store.list_meetings(client_id=client_id):
        if _match(f"{m.get('title')} {m.get('status')}"):
            results["meetings"].append(_ref(m, "meeting", m.get("title"),
                                            status=m.get("status")))
    for a in store.list_action_items():
        if (client_id and a.get("client_id") not in (None, client_id)):
            continue
        if _match(f"{a.get('text')} {a.get('owner', '')}"):
            results["action_items"].append(_ref(
                a, "action_item", a.get("text", "")[:140],
                status=a.get("status")))
    for f in store.list_follow_ups():
        if client_id and f.get("client_id") != client_id:
            continue
        if _match(f.get("reason", "")):
            results["follow_ups"].append(_ref(f, "follow_up",
                                              f.get("reason", "")[:140],
                                              status=f.get("status")))

    counts = {k: len(v) for k, v in results.items()}
    return {"query": query, "counts": counts, **results}


def _ref(rec: dict[str, Any], type_: str, text: str,
         status: str | None = None, confidence: float | None = None) -> dict[str, Any]:
    ref = {"type": type_, "id": rec.get("id"), "text": text,
           "ts": rec.get("created_at") or rec.get("scheduled_at") or 0}
    if status:
        ref["status"] = status
    if confidence is not None:
        ref["confidence"] = confidence
    return ref


# ── Client context block (#9/#20/#133) ────────────────────────────────

def client_context(store, client_name: str) -> dict[str, Any] | None:
    """The structured context DASH loads before speaking for/about a
    client — real records only, scoped to exactly this client (#55/#56)."""
    client = store.get_client(client_name)
    if client is None:
        return None
    cid = client["id"]
    projects = store.list_projects(client_id=cid)
    reqs = store.list_requirements(client_id=cid)
    comms = store.list_communications(client_id=cid)
    meetings = store.list_meetings(client_id=cid)
    follow_ups = [f for f in store.list_follow_ups(status="pending")
                  if f.get("client_id") == cid]
    last_comm = comms[-1] if comms else None
    next_meeting = None
    upcoming = [m for m in meetings
                if m.get("scheduled_at") and m["scheduled_at"] > time.time()
                and m.get("status") != "completed"]
    if upcoming:
        next_meeting = min(upcoming, key=lambda m: m["scheduled_at"])
    return {
        "client": {"id": cid, "name": client.get("name"),
                   "organization": client.get("organization"),
                   "priority": client.get("priority")},
        "projects": [{"id": p["id"], "name": p.get("name"),
                      "status": p.get("status")} for p in projects],
        "open_requirements": [
            {"id": r["id"], "text": r.get("text", "")[:140],
             "status": r.get("status")}
            for r in reqs if r.get("status") not in ("delivered", "rejected")],
        "pending_decisions": [
            {"id": r["id"], "text": r.get("text", "")[:140]}
            for r in reqs if r.get("status") == "clarification_needed"],
        "last_communication": ({
            "id": last_comm["id"], "direction": last_comm.get("direction"),
            "summary": last_comm.get("summary", "")[:140],
            "sent": last_comm.get("sent"),
            "when": last_comm.get("created_at")} if last_comm else None),
        "next_meeting": ({
            "id": next_meeting["id"], "title": next_meeting.get("title"),
            "scheduled_at": next_meeting.get("scheduled_at")}
            if next_meeting else None),
        "pending_follow_ups": len(follow_ups),
    }


# ── Project health (#106): real indicators only ───────────────────────

_DEADLINE_SOON_S = 7 * 86400.0


def project_health(store, project_name_or_id: str,
                   orchestrator=None) -> dict[str, Any] | None:
    project = store.get_project(project_name_or_id)
    if project is None:
        return None
    pid = project["id"]
    reqs = store.list_requirements(project_id=pid)
    now = time.time()

    reqs_open = [r for r in reqs
                 if r.get("status") not in ("delivered", "rejected")]
    reqs_pending_decision = [r for r in reqs
                             if r.get("status") == "clarification_needed"]
    reqs_planned = [r for r in reqs if r.get("status") == "planned"]

    tasks = _tasks_for(store, orchestrator, project)
    tasks_completed = [t for t in tasks if t.get("status") == "completed"]
    tasks_active = [t for t in tasks if t.get("status") in
                    ("running", "planning", "verifying")]
    tasks_paused = [t for t in tasks if t.get("status") == "paused"]
    tasks_failed = [t for t in tasks if t.get("status") == "failed"]

    next_deadline = _parse_deadline(project.get("deadline"))
    deadline_proximity = None
    if next_deadline:
        delta = next_deadline - now
        deadline_proximity = {
            "at": next_deadline,
            "within_7_days": 0 <= delta <= _DEADLINE_SOON_S,
            "overdue": delta < 0,
        }

    approval_delays = []
    try:
        approvals = store._approvals.read().get("approvals", [])
        approval_delays = [a for a in approvals
                           if a.get("status") == "pending"
                           and a.get("client_id") == project.get("client_id")]
    except Exception:
        logger.exception("project_health: approvals read failed")

    return {
        "project": {"id": pid, "name": project.get("name"),
                    "client_id": project.get("client_id")},
        "requirements": {
            "open": len(reqs_open),
            "pending_decision": len(reqs_pending_decision),
            "planned_to_tasks": len(reqs_planned),
        },
        "tasks": {
            "completed": len(tasks_completed),
            "active": len(tasks_active),
            "paused": len(tasks_paused),
            "failed": len(tasks_failed),
        },
        "next_deadline": deadline_proximity,
        "approvals_waiting": len(approval_delays),
        "notes": _health_notes(reqs_pending_decision, tasks_failed,
                               tasks_paused, deadline_proximity),
    }


def _parse_deadline(deadline: Any) -> float | None:
    """Project deadlines are ISO date strings in the store; parse or skip."""
    if not deadline or not isinstance(deadline, str):
        return None
    try:
        import datetime as _dt
        d = _dt.date.fromisoformat(deadline[:10])
        return _dt.datetime.combine(d, _dt.time.max).timestamp()
    except ValueError:
        return None


def _tasks_for(store, orchestrator, project: dict[str, Any]) -> list[dict[str, Any]]:
    """Tasks linked to this project's requirements (traceability #143):
    a task belongs to the project if some requirement of the project
    lists it in task_ids."""
    if orchestrator is None:
        return []
    try:
        all_tasks = {t.get("id"): t for t in orchestrator.list_tasks()}
    except Exception:
        logger.exception("project_health: orchestrator query failed")
        return []
    linked: list[dict[str, Any]] = []
    for r in store.list_requirements(project_id=project["id"]):
        for tid in (r.get("task_ids") or []):
            t = all_tasks.get(tid)
            if t is not None:
                linked.append(t)
    return linked


def _health_notes(pending_decision, failed, paused, deadline) -> list[str]:
    notes = []
    if pending_decision:
        notes.append(f"{len(pending_decision)} requirement(s) need client "
                     "clarification before work can proceed")
    if failed:
        notes.append(f"{len(failed)} task(s) failed and need review")
    if paused:
        notes.append(f"{len(paused)} task(s) paused")
    if deadline and deadline.get("overdue"):
        notes.append("a requirement deadline is overdue")
    elif deadline and deadline.get("within_7_days"):
        notes.append("a requirement deadline is within 7 days")
    return notes


# ── Client status report (#144) — from real data, nothing invented ────

def client_status_report(store, client_name: str,
                         orchestrator=None) -> dict[str, Any] | None:
    client = store.get_client(client_name)
    if client is None:
        return None
    cid = client["id"]
    projects = store.list_projects(client_id=cid)
    reqs = store.list_requirements(client_id=cid)

    completed: list[str] = []
    in_progress: list[str] = []
    blocked: list[str] = []
    pending_client: list[str] = []
    risks: list[str] = []

    for r in reqs:
        text = (r.get("text") or "")[:120]
        st = r.get("status")
        if st == "delivered":
            completed.append(text)
        elif st in ("planned", "approved"):
            in_progress.append(text)
        elif st == "clarification_needed":
            pending_client.append(text)
        elif st in ("detected", "requested", "confirmed"):
            in_progress.append(f"{text} (status: {st})")
        if (r.get("task_ids") and st not in ("delivered",)):
            linked_fail = _any_task_failed(orchestrator, r["task_ids"])
            if linked_fail:
                blocked.append(text)

    comms = store.list_communications(client_id=cid)
    failed_sends = [c for c in comms
                    if c.get("direction") == "outgoing" and not c.get("sent")]
    for c in failed_sends[-3:]:
        risks.append(f"an outgoing message was never confirmed delivered "
                     f"({(c.get('summary') or '')[:60]})")

    next_meeting = None
    upcoming = [m for m in store.list_meetings(client_id=cid)
                if m.get("scheduled_at") and m["scheduled_at"] > time.time()
                and m.get("status") != "completed"]
    if upcoming:
        m = min(upcoming, key=lambda x: x["scheduled_at"])
        next_meeting = {"title": m.get("title"),
                        "scheduled_at": m["scheduled_at"]}

    sections: list[str] = [f"Status for {client.get('name')}:"]
    if completed:
        sections.append(f"Completed: {len(completed)} requirement(s)")
    if in_progress:
        sections.append(f"In progress: {len(in_progress)}")
    if blocked:
        sections.append(f"Blocked: {len(blocked)}")
    if pending_client:
        sections.append(f"Waiting on client decision: {len(pending_client)}")
    if risks:
        sections.append(f"Risks: {len(risks)}")
    if next_meeting:
        sections.append("An upcoming meeting is scheduled")
    if len(sections) == 1:
        sections.append("No recorded activity yet.")

    return {
        "text": "\n".join(sections),
        "client_id": cid,
        "completed": completed,
        "in_progress": in_progress,
        "blocked": blocked,
        "pending_client_decision": pending_client,
        "risks": risks,
        "next_meeting": next_meeting,
        "projects": [{"id": p["id"], "name": p.get("name")} for p in projects],
    }


def _any_task_failed(orchestrator, task_ids: list[str]) -> bool:
    if not orchestrator or not task_ids:
        return False
    try:
        tasks = {t.get("id"): t for t in orchestrator.list_tasks()}
    except Exception:
        return False
    return any(tasks.get(tid, {}).get("status") == "failed"
               for tid in task_ids)
