"""DASH Proactive Intelligence (DASH 2.0, section 5).

Detects useful context and proposes useful action. Signal detectors are pure
functions over an EnvironmentContext snapshot, so they are trivially testable
and never touch the network or filesystem.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List

from dash_backend.context.engine import EnvironmentContext

# Severity thresholds in percentage points (psutil reports 0-100)
_CPU_HIGH = 85.0
_CPU_CRITICAL = 90.0
_RAM_HIGH = 85.0
_RAM_CRITICAL = 90.0
_DISK_CRITICAL = 90.0
_STALE_DAYS = 3


@dataclass
class Signal:
    """A candidate proactive suggestion."""

    id: str  # stable id used for cooldown/dedup, e.g. "uncommitted_work"
    category: str  # system_health | project | goals
    title: str
    message: str
    importance: float  # 0..1
    payload: Dict[str, Any] = field(default_factory=dict)


def _last_commit_date(snap: EnvironmentContext) -> datetime | None:
    """Parse '310f07e fix: ... | 2026-09-05' -> date. None if unparseable."""
    last = (snap.project or {}).get("last_commit")
    if not last:
        return None
    try:
        date_part = last.rsplit("|", 1)[-1].strip()
        return datetime.strptime(date_part, "%Y-%m-%d")
    except Exception:
        return None


def _system_health_signals(snap: EnvironmentContext) -> List[Signal]:
    dev = snap.device
    signals: List[Signal] = []
    cpu = dev.get("cpu_percent")
    if cpu is not None:
        if cpu >= _CPU_CRITICAL:
            signals.append(
                Signal(
                    id="system_cpu_critical",
                    category="system_health",
                    title="CPU usage is critically high",
                    message=f"CPU is at {cpu:.0f}%. Top processes may need attention.",
                    importance=0.85,
                )
            )
        elif cpu >= _CPU_HIGH:
            signals.append(
                Signal(
                    id="system_cpu_high",
                    category="system_health",
                    title="CPU usage is high",
                    message=f"CPU is at {cpu:.0f}%.",
                    importance=0.6,
                )
            )
    ram = dev.get("ram_percent")
    if ram is not None:
        if ram >= _RAM_CRITICAL:
            signals.append(
                Signal(
                    id="system_ram_critical",
                    category="system_health",
                    title="Memory usage is critically high",
                    message=f"RAM is {ram:.0f}% used ({dev.get('ram_used_mb')}/{dev.get('ram_total_mb')} MB).",
                    importance=0.8,
                )
            )
        elif ram >= _RAM_HIGH:
            signals.append(
                Signal(
                    id="system_ram_high",
                    category="system_health",
                    title="Memory usage is high",
                    message=f"RAM is {ram:.0f}% used ({dev.get('ram_used_mb')}/{dev.get('ram_total_mb')} MB).",
                    importance=0.6,
                )
            )
    disk = dev.get("disk_percent")
    if disk is not None and disk >= _DISK_CRITICAL:
        signals.append(
            Signal(
                id="system_disk_critical",
                category="system_health",
                title="Disk space is running low",
                message=f"Disk is {disk:.0f}% used with {dev.get('disk_free_gb')} GB free.",
                importance=0.75,
            )
        )
    return signals


def _project_signals(snap: EnvironmentContext) -> List[Signal]:
    proj = snap.project
    if not proj:
        return []
    signals: List[Signal] = []
    repo = proj.get("repo_name", "project")
    branch = proj.get("branch", "unknown")
    changed = proj.get("changed_files", 0)
    if changed > 0:
        signals.append(
            Signal(
                id="uncommitted_work",
                category="project",
                title=f"{changed} modified file(s) in {repo}",
                message=f"{repo} (branch {branch}) has {changed} uncommitted change(s). "
                "Want me to review the diff or prepare a commit?",
                importance=0.65,
                payload={"repo": repo, "branch": branch, "changed_files": changed},
            )
        )
    commit_date = _last_commit_date(snap)
    if commit_date is not None and (datetime.now() - commit_date).days >= _STALE_DAYS and changed == 0:
        signals.append(
            Signal(
                id="stale_project",
                category="project",
                title=f"{repo} has had no activity for {_STALE_DAYS}+ days",
                message=f"Last commit on {repo} was {commit_date.date()}. Would you like a status review?",
                importance=0.45,
            )
        )
    return signals


def _deadline_signals(snap: EnvironmentContext) -> List[Signal]:
    """Deadline pressure from activity context: overdue items are the most
    important, then items due within 48 hours."""
    items = (snap.activity or {}).get("deadline_items") or []
    if not items:
        return []
    from datetime import datetime, timedelta, timezone

    # Deadlines may be naive (sqlite round-trip) or aware; compare in naive UTC.
    def _naive_utc(dt: datetime) -> datetime:
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt

    now = _naive_utc(datetime.now(timezone.utc))
    signals: List[Signal] = []
    for it in items[:8]:
        try:
            dl = _naive_utc(datetime.fromisoformat(it["deadline"]))
        except (KeyError, ValueError):
            continue
        if it.get("overdue") or dl < now:
            signals.append(
                Signal(
                    id=f"deadline_overdue_{it['id'][:8]}",
                    category="goals",
                    title=f"Overdue: {it.get('name', '?')}",
                    message=f"{it.get('type', 'item').capitalize()} \"{it.get('name', '?')}\" "
                    f"was due {dl.strftime('%Y-%m-%d')}.",
                    importance=0.85,
                    payload={"deadline": it.get("deadline"), "type": it.get("type")},
                )
            )
        elif dl - now <= timedelta(hours=48):
            signals.append(
                Signal(
                    id=f"deadline_approaching_{it['id'][:8]}",
                    category="goals",
                    title=f"Due soon: {it.get('name', '?')}",
                    message=f"{it.get('type', 'item').capitalize()} \"{it.get('name', '?')}\" "
                    f"is due {dl.strftime('%Y-%m-%d')}.",
                    importance=0.7,
                    payload={"deadline": it.get("deadline"), "type": it.get("type")},
                )
            )
    return signals


def _goal_signals(snap: EnvironmentContext) -> List[Signal]:
    goals = (snap.activity or {}).get("recent_goals") or []
    active = [g for g in goals if g.get("status") in ("pending", "running")]
    if not active:
        return []
    names = ", ".join(g.get("name", "?") for g in active[:3])
    extra = f" (+{len(active) - 3} more)" if len(active) > 3 else ""
    return [
        Signal(
            id="active_goals",
            category="goals",
            title=f"{len(active)} active goal(s)",
            message=f"Current goal(s): {names}{extra}. Want me to continue or reprioritize?",
            importance=0.7,
            payload={"count": len(active), "names": [g.get("name") for g in active]},
        )
    ]


def detect_signals(snap: EnvironmentContext) -> List[Signal]:
    """Run all detectors over a context snapshot."""
    return (
        _system_health_signals(snap)
        + _project_signals(snap)
        + _deadline_signals(snap)
        + _goal_signals(snap)
    )