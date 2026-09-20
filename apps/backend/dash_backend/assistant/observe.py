"""Observability layer (spec #71/#72/#73/#74/#127/#150).

Unified activity timeline, "why did you do that?" answers from the
operational decision record (never hidden chain-of-thought), per-task
timelines, and the owner debug view. Everything reads real persisted
records: CRM store + audit log + orchestrator task state.
"""
from __future__ import annotations

import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _audit():
    from dash_backend.services.audit_logs import get_audit_service
    return get_audit_service()


# ── Global activity timeline (#127) ───────────────────────────────────

def global_timeline(store, orchestrator=None, audit=None,
                    client: str | None = None, project: str | None = None,
                    type_: str | None = None, status: str | None = None,
                    start: float | None = None, end: float | None = None,
                    limit: int = 200) -> dict[str, Any]:
    """Unified chronological timeline across every record type, with
    the spec #127 filters: client, project, date, type, status."""
    client_id = None
    if client:
        c = store.get_client(client)
        if c is None:
            return {"events": [], "total": 0, "error": f"unknown client: {client}"}
        client_id = c["id"]
    project_id = None
    if project:
        p = store.get_project(project)
        if p is None:
            return {"events": [], "total": 0, "error": f"unknown project: {project}"}
        project_id = p["id"]

    events: list[dict[str, Any]] = []
    want = (type_ or "").lower() or None

    def _add(ts, type_name, text, ev_status, rec_id, client_of=None):
        if want and type_name != want:
            return
        if status and (ev_status or "") != status:
            return
        if start and (ts or 0) < start:
            return
        if end and (ts or 0) > end:
            return
        events.append({"ts": ts or 0, "type": type_name, "text": (text or "")[:140],
                       "status": ev_status, "id": rec_id, "client_id": client_of})

    for c in store.list_clients():
        if client_id and c["id"] != client_id:
            continue  # client filter isolates (#127/#55)
        _add(c.get("created_at"), "client", f"client created: {c.get('name')}",
             "active", c["id"], c["id"])
    if not project_id:
        for p in store.list_projects(client_id=client_id):
            _add(p.get("created_at"), "project", f"project started: {p.get('name')}",
                 p.get("status"), p["id"], p.get("client_id"))
    for r in store.list_requirements(client_id=client_id):
        if project_id and r.get("project_id") != project_id:
            continue
        _add(r.get("created_at"), "requirement", r.get("text"),
             r.get("status"), r["id"], r.get("client_id"))
        for h in r.get("history", []):
            if h.get("status") and h.get("ts"):
                _add(h["ts"], "requirement_status",
                     f"{(r.get('text') or '')[:70]} -> {h['status']}",
                     h["status"], r["id"], r.get("client_id"))
    for m in store.list_meetings(client_id=client_id):
        if project_id and m.get("project_id") != project_id:
            continue
        _add(m.get("scheduled_at") or m.get("created_at"), "meeting",
             m.get("title"), m.get("status"), m["id"], m.get("client_id"))
    for com in store.list_communications(client_id=client_id):
        _add(com.get("created_at"), "communication",
             f"{com.get('direction')}: {com.get('summary')}",
             "sent" if com.get("sent") else "recorded", com["id"],
             com.get("client_id"))
    for a in store.list_action_items():
        if client_id and a.get("client_id") not in (None, client_id):
            continue
        _add(a.get("created_at"), "action_item", a.get("text"),
             a.get("status"), a["id"], a.get("client_id"))
    for f in store.list_follow_ups():
        if client_id and f.get("client_id") != client_id:
            continue
        _add(f.get("created_at"), "follow_up", f.get("reason"),
             f.get("status"), f["id"], f.get("client_id"))

    # Autonomous task events from the real orchestrator state
    if orchestrator is not None:
        try:
            tasks = orchestrator.list_tasks()
        except Exception:
            logger.exception("timeline: orchestrator query failed")
            tasks = []
        for t in tasks:
            base_ts = t.get("created_at")
            _add(base_ts, "task", f"task: {t.get('goal')}",
                 t.get("status"), t.get("id"))
            events = t.get("events")
            if events is None:
                # list_tasks() snapshots omit events (include_events=False
                # default); fetch the full object for the event history.
                getter = getattr(orchestrator, "get_task", None)
                obj = getter(t.get("id")) if callable(getter) else None
                events = getattr(obj, "events", None) or []
            for ev in events:
                _add(ev.get("ts"), "task_event",
                     f"{t.get('goal', '')[:60]}: {ev.get('type', '')}",
                     t.get("status"), t.get("id"))

    # Audit entries (approvals, sends, denials) — the authoritative action log
    try:
        svc = audit or _audit()
        for entry in svc.query(event_type=None, limit=300):
            _add(entry.get("timestamp"), "audit",
                 f"{entry.get('event_type', '')} {entry.get('action', '')}".strip(),
                 entry.get("status") or "logged", entry.get("request_id", ""))
    except Exception:
        logger.exception("timeline: audit query failed")

    events.sort(key=lambda e: e["ts"])
    return {"events": events[-limit:], "total": len(events)}


# ── Task timeline (#71) ───────────────────────────────────────────────

def task_timeline(orchestrator, task_id: str) -> dict[str, Any] | None:
    if orchestrator is None:
        return None
    try:
        for t in orchestrator.list_tasks():
            if t.get("id") == task_id:
                return {
                    "task_id": task_id,
                    "goal": t.get("goal"),
                    "status": t.get("status"),
                    "progress": t.get("progress"),
                    "verification": t.get("final_report", {}).get("verification"),
                    "timeline": [
                        {"ts": ev.get("ts"), "event": ev.get("event_type"),
                         "detail": (ev.get("detail") or "")[:160]}
                        for ev in (t.get("events") or [])
                    ],
                }
    except Exception:
        logger.exception("task_timeline query failed")
    return None


# ── Decision traces (#43) ─────────────────────────────────────────────

def record_decision_trace(store, situation: str, observed: dict[str, Any],
                          options: list[str], authority: int,
                          reason: str, approval_required: bool,
                          action: str, result: dict[str, Any]) -> dict[str, Any]:
    """Persist a concise machine-readable operational trace for an
    important decision. This is the record 'why did you...?' reads from.
    Contains situation/context/authority/action/result — never hidden
    model reasoning (spec #43/#162.28)."""
    rec = {
        "id": f"dt_{int(time.time() * 1000)}",
        "situation": situation[:300],
        "observed": {k: str(v)[:200] for k, v in (observed or {}).items()},
        "options": [o[:120] for o in options],
        "authority_level": int(authority),
        "reason": reason[:300],
        "approval_required": bool(approval_required),
        "action": action[:200],
        "result": {k: str(v)[:200] for k, v in (result or {}).items()},
        "ts": time.time(),
    }
    try:
        import json
        path = store._decisions
        data = path.read()
        data.setdefault("version", 1)
        data.setdefault("decisions", []).append(rec)
        path.write(data)
    except Exception:
        logger.exception("decision trace persist failed")
        return rec
    return rec


def list_decision_traces(store, limit: int = 50) -> list[dict[str, Any]]:
    try:
        return store._decisions.read().get("decisions", [])[-limit:]
    except Exception:
        logger.exception("decision trace read failed")
        return []


# ── "Why did you do that?" (#73) / action log (#72) ───────────────────

def why_did_you(store, audit, subject: str) -> dict[str, Any]:
    """Answer from the operational decision record: matching audit
    entries + the linked records' own facts. Explicitly operational —
    no hidden model reasoning is exposed (spec #43/#162.28)."""
    subject_low = (subject or "").lower().strip()
    entries = []
    try:
        entries = audit.query(limit=500) if audit else _audit().query(limit=500)
    except Exception:
        logger.exception("why_did_you: audit query failed")
    matches = [e for e in entries
               if subject_low in json_dumps_safe(e).lower()][-10:]
    # Ground in real records too: communications and approvals matching
    comms = [c for c in store.list_communications()
             if subject_low and subject_low in (c.get("summary") or "").lower()][-5:]
    approvals = []
    try:
        approvals = [a for a in store._approvals.read().get("approvals", [])
                     if subject_low in json_dumps_safe(a).lower()][-5:]
    except Exception:
        logger.exception("why_did_you: approvals read failed")

    lines = []
    if matches:
        lines.append(f"{len(matches)} matching action log entr"
                     f"{'y' if len(matches) == 1 else 'ies'}:")
        for e in matches[-4:]:
            ts = e.get("timestamp")
            when = time.strftime("%Y-%m-%d %H:%M", time.localtime(ts)) if ts else "?"
            lines.append(f"  • {when} {e.get('event_type', '')} "
                         f"{e.get('action', '')}".strip())
    if approvals:
        lines.append(f"{len(approvals)} matching approval record(s)")
    if comms:
        lines.append(f"{len(comms)} matching communication record(s), "
                     "delivery evidence recorded on each")
    if not lines:
        lines.append("No matching actions on record — I have no events "
                     "for that, so I did not do it.")
    return {
        "text": "\n".join(lines),
        "audit_entries": matches,
        "approvals": approvals,
        "communications": comms,
        "note": "Operational record only — no hidden model reasoning.",
    }


def actions_today(audit=None) -> str:
    """'show me what you did today' (#76) — real audit entries, today.

    `audit` is injectable (hermetic tests); the singleton service is the
    live default so the answer always reflects real operational records.
    """
    import datetime as _dt
    start = _dt.datetime.combine(_dt.date.today(), _dt.time.min).timestamp()
    svc = audit or _audit()
    try:
        entries = [e for e in svc.query(limit=1000)
                   if (e.get("timestamp") or 0) >= start]
    except Exception:
        logger.exception("actions_today query failed")
        entries = []
    if not entries:
        return "No actions recorded yet today."
    kinds: dict[str, int] = {}
    for e in entries:
        kinds[e.get("event_type", "other")] = kinds.get(e.get("event_type", "other"), 0) + 1
    parts = [f"{n} {k.split('.')[-1]}" for k, n in sorted(kinds.items())]
    return f"Today I recorded {len(entries)} action(s): " + ", ".join(parts) + "."


def json_dumps_safe(obj: Any) -> str:
    try:
        import json
        return json.dumps(obj, default=str)
    except Exception:
        return str(obj)


# ── Owner debug view (#150) ───────────────────────────────────────────

def debug_view(store, orchestrator=None, audit=None,
               section: str = "all") -> dict[str, Any]:
    """Owner-accessible debug surface: tasks, events, decisions,
    authority, tools, approvals, results, verification, errors — with
    secrets and hidden model reasoning excluded by construction."""
    out: dict[str, Any] = {"generated_at": time.time()}
    if section in ("all", "tasks"):
        tasks = []
        if orchestrator is not None:
            try:
                tasks = orchestrator.list_tasks()
            except Exception:
                logger.exception("debug_view: orchestrator query failed")
        out["tasks"] = [{
            "id": t.get("id"), "goal": (t.get("goal") or "")[:100],
            "status": t.get("status"),
            "steps": len(t.get("steps") or []),
            "events": len(t.get("events") or []),
            "progress": t.get("progress"),
        } for t in tasks]
    if section in ("all", "approvals"):
        try:
            approvals = store._approvals.read().get("approvals", [])
        except Exception:
            approvals = []
        out["approvals"] = [{
            "id": a.get("id"), "action": a.get("action_kind"),
            "status": a.get("status"), "risk": a.get("risk_level"),
            "scope": a.get("scope"), "created": a.get("created_at"),
        } for a in approvals[-50:]]
    if section in ("all", "actions"):
        try:
            svc = audit or _audit()
            entries = svc.query(limit=100)
        except Exception:
            entries = []
        out["recent_actions"] = [{
            "ts": e.get("timestamp"), "event": e.get("event_type"),
            "action": e.get("action"), "status": e.get("status"),
        } for e in entries]
    if section in ("all", "counts"):
        out["counts"] = {
            "clients": len(store.list_clients()),
            "requirements": len(store.list_requirements()),
            "communications": len(store.list_communications()),
            "meetings": len(store.list_meetings()),
        }
    return out
