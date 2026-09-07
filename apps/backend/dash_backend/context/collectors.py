"""Live context collectors.

Each collector is intentionally small and defensive: it returns whatever it
could gather and never raises, so the assembled environment context is always
available even when a subsystem (psutil, git, DB) is unavailable.
"""

from __future__ import annotations

import os
import platform
import subprocess
import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Device
# ---------------------------------------------------------------------------

def collect_device_context() -> Dict[str, Any]:
    """CPU / RAM / disk / network / platform snapshot. Never raises."""
    ctx: Dict[str, Any] = {"platform": platform.platform(), "python": platform.python_version()}
    try:
        import psutil

        ctx["cpu_percent"] = round(psutil.cpu_percent(interval=None), 1)
        ctx["cpu_count"] = psutil.cpu_count(logical=True)
        mem = psutil.virtual_memory()
        ctx["ram_percent"] = round(mem.percent, 1)
        ctx["ram_used_mb"] = mem.used // (1024 * 1024)
        ctx["ram_total_mb"] = mem.total // (1024 * 1024)
        try:
            disk = psutil.disk_usage("/")
            ctx["disk_percent"] = round(disk.percent, 1)
            ctx["disk_free_gb"] = round(disk.free / (1024 ** 3), 1)
            ctx["disk_total_gb"] = round(disk.total / (1024 ** 3), 1)
        except Exception:
            pass
        try:
            io = psutil.net_io_counters()
            ctx["net_bytes_sent_mb"] = round(io.bytes_sent / (1024 ** 2), 1)
            ctx["net_bytes_recv_mb"] = round(io.bytes_recv / (1024 ** 2), 1)
        except Exception:
            pass
        try:
            boot = psutil.boot_time()
            ctx["uptime_hours"] = round((time.time() - boot) / 3600, 1)
        except Exception:
            pass
        ctx["top_processes"] = _top_processes(psutil, n=3)
    except Exception:
        pass
    return ctx


def _top_processes(psutil: Any, n: int = 3) -> List[Dict[str, Any]]:
    procs: List[Dict[str, Any]] = []
    try:
        for p in sorted(
            psutil.process_iter(["pid", "name", "memory_info", "cpu_percent"]),
            key=lambda x: (x.info.get("memory_info") or type("", (), {"rss": 0})()).rss,
            reverse=True,
        )[:n]:
            procs.append(
                {
                    "name": p.info.get("name") or "?",
                    "pid": p.info.get("pid"),
                    "ram_mb": ((p.info.get("memory_info") or type("", (), {"rss": 0})()).rss) // (1024 * 1024),
                }
            )
    except Exception:
        pass
    return procs


# ---------------------------------------------------------------------------
# Project (git)
# ---------------------------------------------------------------------------

_GIT_TIMEOUT = 5  # seconds


def _git(cwd: Path, *args: str) -> Optional[str]:
    try:
        proc = subprocess.run(
            ["git", *args],
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=_GIT_TIMEOUT,
        )
        if proc.returncode != 0:
            return None
        return proc.stdout.strip()
    except Exception:
        return None


def find_git_root(start: Optional[str] = None) -> Optional[Path]:
    """Walk up from `start` (default: cwd) looking for a .git directory."""
    base = Path(start or os.getcwd()).resolve()
    for candidate in [base, *base.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def collect_project_context(project_dir: Optional[str] = None) -> Dict[str, Any]:
    """Active repository state: branch, changes, last commit, recent activity."""
    ctx: Dict[str, Any] = {}
    root = find_git_root(project_dir)
    if root is None:
        return ctx
    ctx["repo_root"] = str(root)
    ctx["repo_name"] = root.name

    branch = _git(root, "branch", "--show-current")
    if branch:
        ctx["branch"] = branch

    status = _git(root, "status", "--porcelain")
    if status is not None:
        lines = [ln for ln in status.splitlines() if ln.strip()]
        ctx["changed_files"] = len(lines)
        ctx["changed_files_sample"] = [ln[3:] if len(ln) > 3 else ln for ln in lines[:8]]

    last = _git(root, "log", "-1", "--format=%h %s | %ad", "--date=short")
    if last:
        ctx["last_commit"] = last

    remote = _git(root, "remote", "get-url", "origin")
    if remote:
        ctx["origin"] = remote

    recent = _git(root, "log", "--since=24 hours ago", "--format=%h %s")
    if recent is not None:
        commits_24h = [ln for ln in recent.splitlines() if ln.strip()]
        ctx["commits_last_24h"] = len(commits_24h)
        ctx["recent_commits"] = commits_24h[:5]
    return ctx


# ---------------------------------------------------------------------------
# Activity (goals / tasks) — requires an async DB session
# ---------------------------------------------------------------------------

async def collect_activity_context(session: Any, user_id: Any, hours: int = 24) -> Dict[str, Any]:
    """Recent goals/tasks and their status counts. Never raises."""
    from sqlalchemy import func, select

    from dash_backend.executive.models import ExecutiveTask, Goal

    ctx: Dict[str, Any] = {"window_hours": hours}
    cutoff = _now() - timedelta(hours=hours)
    try:
        # PGUUID columns require real uuid objects; routes hand us the owner id
        # as a string, so normalize here (fall back to string on odd inputs).
        try:
            user_uuid = _uuid.UUID(str(user_id))
        except (ValueError, TypeError):
            user_uuid = None
        if user_uuid is None:
            return ctx
        user_id = user_uuid
        user_filter = Goal.user_id == user_id
        goals = await session.execute(
            select(Goal).where(user_filter, Goal.created_at >= cutoff).order_by(Goal.created_at.desc()).limit(10)
        )
        goal_rows = goals.scalars().all()
        ctx["recent_goals"] = [
            {"name": g.name, "status": g.status, "created_at": g.created_at.isoformat() if g.created_at else None}
            for g in goal_rows
        ]
        if goal_rows:
            goal_ids = [g.id for g in goal_rows]
            tasks = await session.execute(
                select(ExecutiveTask).where(ExecutiveTask.goal_id.in_(goal_ids)).order_by(ExecutiveTask.created_at.desc()).limit(20)
            )
            ctx["recent_tasks"] = [
                {"name": t.name, "status": t.status, "goal_id": str(t.goal_id)}
                for t in tasks.scalars().all()
            ]
        counts = await session.execute(
            select(Goal.status, func.count()).where(user_filter).group_by(Goal.status)
        )
        ctx["goal_status_counts"] = {status: count for status, count in counts.all()}

        # Goal/task deadlines inside the next 7 days (or already overdue).
        # sqlite round-trips aware datetimes as naive, so compare in naive UTC.
        now_naive = datetime.now(timezone.utc).replace(tzinfo=None)

        def _naive(dt):
            return dt.astimezone(timezone.utc).replace(tzinfo=None) if dt.tzinfo is not None else dt

        horizon = now_naive + timedelta(days=7)
        deadline_items: List[Dict[str, Any]] = []
        goals = await session.execute(
            select(Goal)
            .where(
                user_filter,
                Goal.status.in_(["pending", "running"]),
                Goal.deadline.is_not(None),
                Goal.deadline <= horizon,
            )
            .order_by(Goal.deadline.asc())
            .limit(6)
        )
        for g in goals.scalars().all():
            dl = g.deadline
            if dl is not None:
                dl = _naive(dl)
                deadline_items.append(
                    {
                        "type": "goal",
                        "id": str(g.id),
                        "name": g.name,
                        "status": g.status,
                        "deadline": dl.isoformat(),
                        "overdue": dl < now_naive,
                    }
                )
        tasks = await session.execute(
            select(ExecutiveTask, Goal.name)
            .join(Goal, Goal.id == ExecutiveTask.goal_id)
            .where(
                user_filter,
                ExecutiveTask.status.in_(["pending", "queued", "running"]),
                ExecutiveTask.deadline.is_not(None),
                ExecutiveTask.deadline <= horizon,
            )
            .order_by(ExecutiveTask.deadline.asc())
            .limit(6)
        )
        for t, goal_name in tasks.all():
            dl = t.deadline
            if dl is not None:
                dl = _naive(dl)
                deadline_items.append(
                    {
                        "type": "task",
                        "id": str(t.id),
                        "name": t.name,
                        "status": t.status,
                        "deadline": dl.isoformat(),
                        "overdue": dl < now_naive,
                        "goal_id": str(t.goal_id),
                        "goal_name": goal_name,
                    }
                )
        if deadline_items:
            deadline_items.sort(key=lambda it: it["deadline"])
            ctx["deadline_items"] = deadline_items[:8]
    except Exception:
        pass
    return ctx