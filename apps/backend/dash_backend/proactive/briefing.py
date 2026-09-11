"""Daily Briefing and End-of-Day Summary (DASH 2.0, sections 6-7).

Built on the environment context engine: the briefing answers "what matters
right now" (system health, project state, active goals, attention items,
and predictive trends from accumulated history); the end-of-day summary
answers "what got done today" and stores the important parts into
long-term memory so DASH can recall them later.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dash_backend.context.engine import EnvironmentContext, get_context_engine
from dash_backend.logging_config import get_logger
from dash_backend.proactive.engine import ProactiveEngine, get_proactive_engine
from dash_backend.predictive.history import SampleStore

logger = get_logger(__name__)


def _device_line(dev: Dict[str, Any]) -> str:
    parts = [f"CPU {dev.get('cpu_percent', '?')}%", f"RAM {dev.get('ram_percent', '?')}%"]
    if dev.get("disk_percent") is not None:
        parts.append(f"Disk {dev['disk_percent']}% ({dev.get('disk_free_gb')} GB free)")
    return " | ".join(parts)


def _project_line(proj: Dict[str, Any]) -> str:
    if not proj:
        return "No active git repository detected."
    parts = [f"{proj.get('repo_name', '?')} (branch {proj.get('branch', 'unknown')})"]
    if "changed_files" in proj:
        parts.append(f"{proj['changed_files']} modified file(s)")
    if proj.get("last_commit"):
        parts.append(f"last commit {proj['last_commit']}")
    return " — ".join(parts)


def _goals_lines(activity: Dict[str, Any]) -> List[str]:
    goals = activity.get("recent_goals") or []
    active = [g for g in goals if g.get("status") in ("pending", "running")]
    lines: List[str] = []
    for g in active[:5]:
        lines.append(f"- {g.get('name', '?')} [{g.get('status', '?')}]")
    if not lines:
        lines.append("- No active goals.")
    return lines


def _deadline_lines(activity: Dict[str, Any]) -> List[str]:
    """Deadline pressure lines (due within the window or already overdue)."""
    items = activity.get("deadline_items") or []
    if not items:
        return []
    lines: List[str] = []
    for it in items[:5]:
        who = it.get("goal_name") or it.get("type", "item")
        flag = " (OVERDUE)" if it.get("overdue") else ""
        stamp = str(it.get("deadline", ""))[:10]
        lines.append(f"- [{who}] {it.get('name', '?')} due {stamp}{flag}")
    if len(items) > 5:
        lines.append(f"- (+{len(items) - 5} more)")
    return lines


# ---------------------------------------------------------------------------
# Trend lines (from accumulated predictive history)
# ---------------------------------------------------------------------------


def _trend_lines(store: Optional[SampleStore] = None) -> List[str]:
    """Summarize device trends from accumulated predictive history.

    Returns human-readable lines like:
    "Disk: falling 130 -> 87.6 GB over 14 days (confident)"
    "RAM: stable at ~85% over 8 hours"

    Returns an empty list when there is not enough history.
    """
    store = store or SampleStore()
    samples = store.samples()
    if len(samples) < 4:
        return []

    from dash_backend.predictive.predictors import _linear_fit, _span_hours, _fmt_hours

    def _metric(sample_list: List[dict], key: str, from_end: bool = False):
        """First non-None value of `key`, scanning from the start or end.

        Samples may lack a metric (None) even when the fit succeeded, so a
        raw samples[-1].get(key) can be None and crash the f-string format.
        """
        ordered = reversed(sample_list) if from_end else sample_list
        for s in ordered:
            v = s.get(key)
            if v is not None:
                return v
        return None

    lines: List[str] = []

    def _trend_block(key: str, fit: object, fmt_fn) -> Optional[str]:
        if fit is None:
            return None
        slope, _ = fit
        current = _metric(samples, key, from_end=True)
        first = _metric(samples, key)
        if current is None or first is None:
            return None
        span = _span_hours(samples)
        confident = span >= 24
        suffix = " (confident)" if confident else ""
        return fmt_fn(slope, first, current, span, suffix)

    # Disk trend
    def _disk_fmt(slope, first, current, span, suffix):
        if slope < -0.0005:
            return f"Disk: falling {first} -> {current:.1f} GB over {_fmt_hours(span)}{suffix}"
        if slope > 0.0005:
            return f"Disk: rising {first} -> {current:.1f} GB free over {_fmt_hours(span)}{suffix}"
        return None

    disk_line = _trend_block("disk_free_gb", _linear_fit(samples, "disk_free_gb"), _disk_fmt)
    if disk_line:
        lines.append(disk_line)

    # RAM trend
    def _ram_fmt(slope, first, current, span, suffix):
        if abs(slope) > 0.05:
            direction = "rising" if slope > 0 else "falling"
            return f"RAM: {direction} {first}% -> {current:.0f}% over {_fmt_hours(span)}{suffix}"
        return f"RAM: stable at ~{current:.0f}% over {_fmt_hours(span)}"

    ram_line = _trend_block("ram_pct", _linear_fit(samples, "ram_pct"), _ram_fmt)
    if ram_line:
        lines.append(ram_line)

    return lines


async def _prediction_lines(session=None, user_id: Optional[str] = None) -> List[str]:
    """Get predictive risk summary from the predictive engine.

    Returns one line per prediction with severity and horizon, or an empty
    list if no predictions were found.
    """
    try:
        from dash_backend.predictive.engine import get_predictive_engine

        engine = get_predictive_engine()
        result = await engine.analyze(session=session, user_id=user_id)
        predictions = result.get("predictions") or []
        lines: List[str] = []
        for p in predictions[:5]:
            sev = p.get("severity", "info")
            horizon = p.get("horizon", "")
            horizon_str = f" ({horizon})" if horizon and horizon != "unknown" else ""
            lines.append(f"- [{sev.upper()}] {p['title']}{horizon_str}")
        return lines
    except Exception as exc:
        logger.debug("Predictive analysis failed in briefing: %s", exc)
        return []


# ---------------------------------------------------------------------------
# Daily briefing
# ---------------------------------------------------------------------------


async def build_briefing(session=None, user_id: Optional[str] = None) -> Dict[str, Any]:
    engine = get_context_engine()
    snap = await engine.snapshot_async(session=session, user_id=user_id)

    proactive = get_proactive_engine()
    attention = await proactive.evaluate(session=session, user_id=user_id, limit=5)

    trends = _trend_lines()

    # The top predictive risk is surfaced via the proactive engine's
    # merged suggestions (predictive_* ids). Extract it separately for
    # the dedicated "Top risk" line in the formatted briefing.
    top_risk = _extract_top_risk(attention)

    sections: Dict[str, Any] = {
        "date": datetime.now().strftime("%A, %Y-%m-%d"),
        "system": _device_line(snap.device),
        "project": _project_line(snap.project),
        "goals": _goals_lines(snap.activity),
        "deadlines": _deadline_lines(snap.activity),
        "trends": trends,
        "top_risk": top_risk,
        "attention": attention,
    }
    return {"sections": sections, "text": format_briefing(sections)}


def _extract_top_risk(attention: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """Pull the highest-importance predictive suggestion from the attention list."""
    predictive = [s for s in attention if s.get("id", "").startswith("predictive_")]
    if not predictive:
        return None
    return max(predictive, key=lambda s: s.get("importance", 0))


def format_briefing(sections: Dict[str, Any]) -> str:
    lines = [f"Good morning. Briefing for {sections.get('date', 'today')}:"]
    lines.append(f"System: {sections.get('system', 'unavailable')}")
    lines.append(f"Project: {sections.get('project', 'unavailable')}")
    lines.append("Goals:")
    lines.extend(sections.get("goals") or ["- No active goals."])
    deadlines = sections.get("deadlines") or []
    if deadlines:
        lines.append("Deadlines:")
        lines.extend(deadlines)
    trends = sections.get("trends") or []
    if trends:
        lines.append("Device trends:")
        lines.extend(trends)
    # Top predictive risk gets its own highlighted line.
    top_risk = sections.get("top_risk")
    if top_risk:
        sev = top_risk.get("payload", {}).get("severity", "info")
        horizon = top_risk.get("payload", {}).get("horizon", "")
        horizon_str = f" ({horizon})" if horizon and horizon != "unknown" else ""
        lines.append(f"Top risk: [{sev.upper()}] {top_risk['title']}{horizon_str}")
    attention = sections.get("attention") or []
    if attention:
        lines.append("Needs your attention:")
        for s in attention[:5]:
            lines.append(f"- {s['title']}")
    else:
        lines.append("Nothing needs your attention right now.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# End-of-day summary
# ---------------------------------------------------------------------------

async def build_end_of_day(session=None, user_id: Optional[str] = None, store_memory: bool = True) -> Dict[str, Any]:
    """Summarize the last 24 hours: completed work, project activity, decisions.

    The summary is stored to long-term memory (category 'daily_summary') so
    DASH can reconstruct "what were we working on" in later sessions.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(hours=24)
    summary: Dict[str, Any] = {"window_hours": 24}

    # Project activity (git).
    engine = get_context_engine()
    project = engine.project()
    commits: List[str] = []
    if project.get("repo_root"):
        from pathlib import Path

        from dash_backend.context.collectors import _git

        log = _git(Path(project["repo_root"]), "log", "--since=24 hours ago", "--format=%h %s")
        commits = [ln for ln in log.splitlines() if ln.strip()] if log else []
    summary["commits"] = commits

    # Completed goals/tasks (DB).
    completed: Dict[str, int] = {"goals": 0, "tasks": 0}
    if session is not None and user_id is not None:
        try:
            from sqlalchemy import func, select

            from dash_backend.executive.models import ExecutiveTask, Goal

            g = await session.execute(
                select(func.count()).select_from(Goal).where(
                    Goal.user_id == user_id, Goal.status == "completed", Goal.created_at >= cutoff
                )
            )
            completed["goals"] = g.scalar() or 0
            t = await session.execute(
                select(func.count()).select_from(ExecutiveTask).where(
                    ExecutiveTask.status == "completed", ExecutiveTask.created_at >= cutoff
                )
            )
            completed["tasks"] = t.scalar() or 0
        except Exception as exc:
            logger.debug("End-of-day DB query failed: %s", exc)
    summary["completed"] = completed

    # Device trends from predictive history.
    summary["trends"] = _trend_lines()

    text = format_end_of_day(summary)
    summary["text"] = text

    stored = False
    if store_memory and session is not None and user_id is not None:
        try:
            from dash_backend.memory import service as memory_service

            await memory_service.save_memory(
                session,
                user_id,
                content=text,
                source="end_of_day_summary",
                category="daily_summary",
                memory_type="Summary",
                importance=0.7,
                title=f"End-of-day summary {datetime.now().strftime('%Y-%m-%d')}",
            )
            stored = True
        except Exception as exc:
            logger.debug("End-of-day memory store failed: %s", exc)
    summary["stored"] = stored
    return summary


def format_end_of_day(summary: Dict[str, Any]) -> str:
    completed = summary.get("completed") or {}
    lines = [
        f"End-of-day summary (last {summary.get('window_hours', 24)} hours):",
        f"Completed: {completed.get('goals', 0)} goal(s), {completed.get('tasks', 0)} task(s).",
    ]
    commits = summary.get("commits") or []
    if commits:
        lines.append(f"Commits ({len(commits)}):")
        lines.extend(f"- {c}" for c in commits[:10])
    else:
        lines.append("No commits in the last 24 hours.")
    trends = summary.get("trends") or []
    if trends:
        lines.append("Device trends:")
        lines.extend(trends)
    return "\n".join(lines)