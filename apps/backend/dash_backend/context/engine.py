"""Environment Context Engine.

Assembles live device + project + activity context into a single snapshot
that DASH can use to understand "where the user is" and "what they are
working on". Snapshots are cached briefly per collector so repeated calls
(per chat message) stay cheap while still being fresh.

Design: sync collectors (device, project) are safe anywhere. Activity
collection needs an async DB session, so full assembly is async-only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.context import collectors
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_TTL_DEVICE = 15.0
_TTL_PROJECT = 30.0
_TTL_ACTIVITY = 60.0


@dataclass
class EnvironmentContext:
    """A point-in-time view of the user's digital environment."""

    device: Dict[str, Any] = field(default_factory=dict)
    project: Dict[str, Any] = field(default_factory=dict)
    activity: Dict[str, Any] = field(default_factory=dict)
    assembled_at: float = field(default_factory=time.time)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "device": self.device,
            "project": self.project,
            "activity": self.activity,
            "assembled_at": self.assembled_at,
        }

    def as_text(self) -> str:
        """Compact text block safe to inject into an LLM prompt."""
        lines: List[str] = []
        dev = self.device
        if dev:
            parts = [f"OS: {dev.get('platform', '?')}"]
            if "cpu_percent" in dev:
                parts.append(f"CPU: {dev['cpu_percent']}%")
            if "ram_percent" in dev:
                parts.append(f"RAM: {dev['ram_percent']}% used ({dev.get('ram_used_mb')}/{dev.get('ram_total_mb')} MB)")
            if "disk_percent" in dev:
                parts.append(f"Disk: {dev['disk_percent']}% used ({dev.get('disk_free_gb')} GB free)")
            lines.append("[DEVICE] " + " | ".join(parts))
            if dev.get("top_processes"):
                tops = ", ".join(f"{p.get('name')} ({p.get('ram_mb')}MB)" for p in dev["top_processes"])
                lines.append(f"[TOP PROCESSES] {tops}")
        proj = self.project
        if proj:
            lines.append(
                f"[PROJECT] {proj.get('repo_name', '?')} on branch {proj.get('branch', 'unknown')}"
            )
            if "changed_files" in proj:
                lines.append(f"[PROJECT CHANGES] {proj['changed_files']} modified file(s)")
            if proj.get("last_commit"):
                lines.append(f"[LAST COMMIT] {proj['last_commit']}")
            if "commits_last_24h" in proj:
                lines.append(f"[RECENT COMMITS 24h] {proj['commits_last_24h']}")
        act = self.activity
        if act:
            goals = act.get("recent_goals") or []
            if goals:
                active = [g for g in goals if g.get("status") in ("pending", "running")]
                lines.append(
                    f"[ACTIVE GOALS] {len(active)} active: "
                    + ", ".join(f"{g.get('name')} ({g.get('status')})" for g in goals[:4])
                )
            dls = act.get("deadline_items") or []
            if dls:
                parts = []
                for it in dls[:4]:
                    stamp = it.get("deadline", "")[:10]
                    flag = " OVERDUE" if it.get("overdue") else ""
                    parts.append(f"{it.get('name')} due {stamp}{flag}")
                extra = f" (+{len(dls) - 4} more)" if len(dls) > 4 else ""
                lines.append("[DEADLINES] " + "; ".join(parts) + extra)
        return "\n".join(lines)


class ContextEngine:
    """Caching assembler for environment context."""

    def __init__(
        self,
        device_ttl: float = _TTL_DEVICE,
        project_ttl: float = _TTL_PROJECT,
        activity_ttl: float = _TTL_ACTIVITY,
    ) -> None:
        self._device_ttl = device_ttl
        self._project_ttl = project_ttl
        self._activity_ttl = activity_ttl
        self._cache: Dict[str, Dict[str, Any]] = {}
        self._project_dir: Optional[str] = None

    def set_project_dir(self, path: Optional[str]) -> None:
        """Pin the project DASH should report as the active repository."""
        self._project_dir = path
        self._cache.pop("project", None)

    # -- collection ---------------------------------------------------------

    def _cached(self, key: str, ttl: float, collect) -> Dict[str, Any]:
        now = time.time()
        entry = self._cache.get(key)
        if entry and now - entry["at"] < ttl:
            return entry["value"]
        try:
            value = collect()
        except Exception as exc:  # collectors are defensive; belt and braces
            logger.debug("Context collector %s failed: %s", key, exc)
            value = {}
        self._cache[key] = {"at": now, "value": value}
        return value

    def device(self, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            self._cache.pop("device", None)
        return self._cached("device", self._device_ttl, collectors.collect_device_context)

    def project(self, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            self._cache.pop("project", None)
        return self._cached(
            "project", self._project_ttl, lambda: collectors.collect_project_context(self._project_dir)
        )

    async def activity(self, session, user_id, hours: int = 24, refresh: bool = False) -> Dict[str, Any]:
        if refresh:
            self._cache.pop("activity", None)
        now = time.time()
        entry = self._cache.get("activity")
        if entry and now - entry["at"] < self._activity_ttl:
            return entry["value"]
        try:
            value = await collectors.collect_activity_context(session, user_id, hours)
        except Exception as exc:
            logger.debug("Activity context collection failed: %s", exc)
            value = {}
        self._cache["activity"] = {"at": now, "value": value}
        return value

    # -- assembly -----------------------------------------------------------

    def snapshot(self, refresh: bool = False) -> EnvironmentContext:
        """Sync snapshot: device + project only (no DB)."""
        return EnvironmentContext(
            device=self.device(refresh=refresh),
            project=self.project(refresh=refresh),
        )

    async def snapshot_async(self, session=None, user_id=None, refresh: bool = False) -> EnvironmentContext:
        """Full snapshot including activity context."""
        device = self.device(refresh=refresh)
        project = self.project(refresh=refresh)
        activity: Dict[str, Any] = {}
        if session is not None and user_id is not None:
            activity = await self.activity(session, user_id, refresh=refresh)
        return EnvironmentContext(device=device, project=project, activity=activity)

    async def context_block_async(self, session=None, user_id=None) -> str:
        """Compact text block for prompt injection. Never raises."""
        try:
            return (await self.snapshot_async(session=session, user_id=user_id)).as_text()
        except Exception as exc:
            logger.debug("Context block unavailable: %s", exc)
            return ""

    def context_block_sync(self) -> str:
        """Sync variant (device + project only). Never raises."""
        try:
            return self.snapshot().as_text()
        except Exception as exc:
            logger.debug("Context block unavailable: %s", exc)
            return ""

    # -- change awareness ---------------------------------------------------

    async def what_changed_since(self, session=None, user_id=None, hours: int = 24) -> Dict[str, Any]:
        """Summarize what changed in the environment over the last `hours`."""
        project = self.project()
        result: Dict[str, Any] = {"window_hours": hours}
        root = project.get("repo_root")
        if root:
            from pathlib import Path

            log = collectors._git(Path(root), "log", f"--since={hours} hours ago", "--format=%h %s")
            result["commits"] = [ln for ln in log.splitlines() if ln.strip()] if log else []
            result["changed_files"] = project.get("changed_files", 0)
        activity: Dict[str, Any] = {}
        if session is not None and user_id is not None:
            activity = await self.activity(session, user_id, hours=hours)
        result["goals_created"] = len(activity.get("recent_goals") or [])
        result["tasks_created"] = len(activity.get("recent_tasks") or [])
        result["active_goals"] = sum(
            1 for g in activity.get("recent_goals") or [] if g.get("status") in ("pending", "running")
        )
        return result


_engine: Optional[ContextEngine] = None


def get_context_engine() -> ContextEngine:
    """Process-wide singleton."""
    global _engine
    if _engine is None:
        _engine = ContextEngine()
    return _engine


async def build_context_block(session=None, user_id=None) -> str:
    """Convenience: compact prompt block from the singleton engine."""
    return await get_context_engine().context_block_async(session=session, user_id=user_id)