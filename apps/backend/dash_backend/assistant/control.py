"""Owner control plane (spec #107/#109/#142/#143/#77).

Three responsibilities, all deterministic (no LLM), all backed by real
store state:

- **Emergency stop** (#109): a global kill-switch that pauses the
  orchestrator's running/waiting tasks, marks every pending approval
  ``revoked``, and gates the outbound pipeline at send time. Stop is
  honest: it records what it could and could not do, and is itself
  audited. Resume restores the gate (paused tasks stay paused — the
  owner resumes them deliberately).

- **Requirement → task conversion** (#142/#143): turns a confirmed
  requirement into an orchestrator task whose goal carries the
  requirement id, so traceability survives: requirement → task →
  implementation → verification. The created task goes through the
  orchestrator's normal planning + authority gates — conversion never
  bypasses them.

- **Daily executive briefing** (#77): morning brief from real state
  only — meetings today, pending approvals, overdue actions, tasks
  running/failed. Sections with nothing to say are omitted, never
  padded.
"""

from __future__ import annotations

import datetime as _dt
import time
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Module-level emergency-stop gate; the outbound pipeline checks this at
# send time (not approval time) so a stop during review still blocks.
_emergency_stop: dict[str, Any] = {"active": False, "since": None, "by": None}


def emergency_stop_active() -> bool:
    return bool(_emergency_stop["active"])


def emergency_stop_status() -> dict[str, Any]:
    return dict(_emergency_stop)


async def emergency_stop(store, audit, orchestrator=None, by: str = "owner") -> dict[str, Any]:
    """STOP ALL AUTONOMOUS ACTIONS (spec #109).

    - pauses every orchestrator task in a runnable state (state is
      preserved; nothing is destroyed),
    - marks all pending approvals ``revoked`` (a stopped owner must not
      come back to approvals that were silently still grantable),
    - raises the send gate checked by the outbound pipeline.

    Never terminates system processes; only DASH's own autonomy is
    stopped. The action itself is audited.
    """
    stopped_tasks: list[str] = []
    failed_tasks: list[dict[str, str]] = []
    if orchestrator is not None:
        for t in orchestrator.list_tasks():
            if t.get("status") in ("running", "waiting_confirmation",
                                   "planning", "verifying"):
                try:
                    ok = await orchestrator.pause_task(t["id"])
                except Exception as exc:
                    failed_tasks.append({"id": t["id"], "error": str(exc)[:120]})
                    continue
                if ok:
                    stopped_tasks.append(t["id"])
                else:
                    failed_tasks.append({"id": t["id"], "error": "pause refused"})

    revoked: list[str] = []
    for a in store.list_approvals(status="pending"):
        if store.resolve_approval(a["id"], "revoked", by="emergency_stop"):
            revoked.append(a["id"])

    _emergency_stop["active"] = True
    _emergency_stop["since"] = time.time()
    _emergency_stop["by"] = by

    try:
        audit.log(
            event_type="emergency_stop",
            action="STOP ALL AUTONOMOUS ACTIONS",
            category="authority",
            status="active",
            details={"paused_tasks": stopped_tasks, "revoked_approvals": revoked},
        )
    except Exception:
        logger.exception("audit log failed for emergency stop")

    return {
        "ok": True,
        "active": True,
        "paused_tasks": stopped_tasks,
        "pause_failures": failed_tasks,
        "revoked_approvals": revoked,
    }


def resume_from_emergency_stop(audit, by: str = "owner") -> dict[str, Any]:
    """Lift the send gate. Paused tasks stay paused deliberately — the
    owner resumes each one (resume-all would re-launch everything at
    once, which is what an emergency stop exists to prevent)."""
    _emergency_stop["active"] = False
    _emergency_stop["since"] = None
    _emergency_stop["by"] = None
    try:
        audit.log(
            event_type="emergency_stop_cleared",
            action="Autonomous actions re-enabled (paused tasks remain paused)",
            category="authority",
            status="cleared",
            details={"by": by},
        )
    except Exception:
        logger.exception("audit log failed for emergency-stop clear")
    return {"ok": True, "active": False}


async def convert_requirement_to_task(
    store, audit, requirement_id: str, user_id: str | None = None,
    orchestrator=None,
) -> dict[str, Any]:
    """Turn a confirmed requirement into an orchestrator task (#142).

    The requirement id travels inside the goal text so the orchestrator's
    deterministic planner and the task's persisted record both carry the
    traceability link. Only requirements in ``confirmed`` / ``approved``
    status convert — a requested or ambiguous statement is not work
    authorization.
    """
    req = store.get_requirement(requirement_id)
    if req is None:
        return {"ok": False, "error": "requirement not found"}
    if req["status"] not in ("confirmed", "approved"):
        return {
            "ok": False,
            "error": (f"requirement status is '{req['status']}' — only "
                      "confirmed/approved requirements convert to tasks"),
        }
    if orchestrator is None:
        return {"ok": False, "error": "task orchestrator unavailable"}

    client = store.get_client(req["client_id"]) if req.get("client_id") else None
    goal = (f"Implement confirmed requirement {req['id']} "
            f"for {client['name'] if client else 'unknown client'}: "
            f"{req['text'][:200]}")
    try:
        task = await orchestrator.create_task(goal, user_id=user_id)
    except ValueError as exc:
        # Candor refusal / concurrency limit — surfaced, never swallowed
        return {"ok": False, "error": str(exc)[:200]}

    store.link_requirement_task(requirement_id, task.id)
    store.update_requirement_status(requirement_id, "planned")
    try:
        audit.log(
            event_type="requirement_converted",
            action=f"{req['id']} -> task {task.id}",
            category="assistant",
            status="ok",
            details={"requirement_id": req["id"], "task_id": task.id},
        )
    except Exception:
        logger.exception("audit log failed for requirement conversion")
    return {"ok": True, "task_id": task.id, "requirement_id": req["id"],
            "goal": goal}


def end_of_day_summary(store, orchestrator=None) -> dict[str, Any]:
    """Evening summary from real records (spec #78). Today's comms,
    meetings held, requirement changes, and what carries over."""
    today = _dt.date.today()
    start = _dt.datetime.combine(today, _dt.time.min).timestamp()

    comms_today: list[dict[str, Any]] = []
    meetings_today: list[dict[str, Any]] = []
    reqs_changed_today = 0
    if store is not None:
        for c in store.list_communications():
            if c.get("created_at", 0) >= start:
                comms_today.append(c)
        for m in store.list_meetings():
            if m.get("status") == "completed" and (
                    m.get("created_at", 0) >= start or m.get("summary")):
                meetings_today.append(m)
        for r in store.list_requirements():
            if any(h.get("ts", 0) >= start for h in r.get("history", [])):
                reqs_changed_today += 1

    completed_tasks: list[dict[str, Any]] = []
    failed_tasks: list[dict[str, Any]] = []
    outstanding: list[dict[str, Any]] = []
    if orchestrator is not None:
        try:
            for t in orchestrator.list_tasks():
                if t.get("status") == "completed" and t.get("completed_at", 0) >= start:
                    completed_tasks.append(t)
                elif t.get("status") == "failed":
                    failed_tasks.append(t)
                elif t.get("status") in ("running", "planning", "verifying",
                                         "waiting_confirmation", "paused"):
                    outstanding.append(t)
        except Exception:
            logger.exception("end-of-day: orchestrator query failed")

    lines: list[str] = ["Today's summary:"]
    if comms_today:
        lines.append(f"- {len(comms_today)} client communication(s) recorded")
    if meetings_today:
        lines.append(f"- {len(meetings_today)} meeting(s) completed")
    if reqs_changed_today:
        lines.append(f"- {reqs_changed_today} requirement status change(s)")
    if completed_tasks:
        lines.append(f"- {len(completed_tasks)} autonomous task(s) completed")
    if failed_tasks:
        lines.append(f"- {len(failed_tasks)} task(s) failed — need review tomorrow")
    if outstanding:
        lines.append(f"- {len(outstanding)} task(s) still open, carrying over")
    if len(lines) == 1:
        lines.append("A quiet day — nothing recorded.")

    return {
        "text": "\n".join(lines),
        "communications_today": len(comms_today),
        "meetings_completed": len(meetings_today),
        "requirement_changes": reqs_changed_today,
        "tasks_completed": len(completed_tasks),
        "tasks_failed": len(failed_tasks),
        "tasks_outstanding": len(outstanding),
        "generated_at": time.time(),
    }


def daily_briefing(store, orchestrator=None) -> dict[str, Any]:
    """Morning brief from REAL state only (spec #77). Empty sections are
    omitted — the brief never invents items to look full."""
    now = time.time()
    meetings_today: list[dict[str, Any]] = []
    if store is not None:
        today = _dt.date.today()
        for m in store.list_meetings():
            sched = m.get("scheduled_at")
            if not sched:
                continue
            try:
                when = _dt.date.fromtimestamp(float(sched))
            except (TypeError, ValueError):
                continue
            if when == today and m.get("status") not in ("completed", "cancelled"):
                meetings_today.append({
                    "id": m["id"], "title": m["title"], "when": sched,
                })
        meetings_today.sort(key=lambda m: m["when"] or 0)

    pending_approvals = (store.list_approvals(status="pending") if store else [])
    overdue_actions = []
    if store is not None:
        for a in store.list_action_items(status="pending"):
            if a.get("due"):
                try:
                    due = _dt.date.fromisoformat(str(a["due"])[:10])
                    if due <= today:
                        overdue_actions.append(a)
                except ValueError:
                    pass

    tasks_running: list[dict[str, Any]] = []
    tasks_failed: list[dict[str, Any]] = []
    if orchestrator is not None:
        try:
            for t in orchestrator.list_tasks():
                if t.get("status") in ("running", "planning", "verifying",
                                       "waiting_confirmation"):
                    tasks_running.append(t)
                elif t.get("status") == "failed":
                    tasks_failed.append(t)
        except Exception:
            logger.exception("briefing: orchestrator query failed")

    lines: list[str] = ["Good morning. Here is today's brief."]
    if meetings_today:
        lines.append(f"- {len(meetings_today)} meeting(s) today"
                     + (f", next: {meetings_today[0]['title']}" if meetings_today else ""))
    if pending_approvals:
        lines.append(f"- {len(pending_approvals)} approval(s) waiting for you")
    if overdue_actions:
        lines.append(f"- {len(overdue_actions)} overdue action item(s)")
    if tasks_failed:
        lines.append(f"- {len(tasks_failed)} failed task(s) needing review")
    if tasks_running:
        lines.append(f"- {len(tasks_running)} autonomous task(s) active")
    if len(lines) == 1:
        lines.append("Nothing needs your attention right now.")

    return {
        "text": "\n".join(lines),
        "meetings_today": meetings_today,
        "pending_approvals": len(pending_approvals),
        "overdue_actions": len(overdue_actions),
        "tasks_running": len(tasks_running),
        "tasks_failed": len(tasks_failed),
        "generated_at": now,
    }
