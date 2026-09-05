"""DASH status reporting API.

Aggregates REAL state from the running subsystems so the owner can ask
things like "what's the status of my work?", "any errors?", "what did you
finish?". Sections degrade gracefully (available=false) when a subsystem is
not running; nothing is fabricated.
"""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/status", tags=["status"])


async def _db_section(session: AsyncSession) -> dict[str, Any]:
    """Conversation/task/goal/approval/notification counters from the DB."""
    from dash_backend.db.models.conversation import Conversation
    from dash_backend.db.models.message import Message
    from dash_backend.db.models.notification import Notification
    from dash_backend.db.models.task import Task

    section: dict[str, Any] = {}

    try:
        conversations = int(
            (await session.execute(select(func.count()).select_from(Conversation))).scalar() or 0
        )
        messages = int(
            (await session.execute(select(func.count()).select_from(Message))).scalar() or 0
        )
        recent_messages = (
            await session.execute(select(Message.content).order_by(Message.created_at.desc()).limit(5))
        ).scalars().all()
        section["conversations"] = {
            "total": conversations,
            "messages_total": messages,
            "recent_user_activity": [str(c)[:120] for c in reversed(list(recent_messages))],
        }
    except Exception as exc:
        logger.warning("status: conversations section failed: %s", exc)
        section["conversations"] = {"available": False, "error": str(exc)}

    try:
        rows = (
            await session.execute(select(Task.status, func.count()).group_by(Task.status))
        ).all()
        by_status = {str(status_): int(n) for status_, n in rows}
        failed_recent = (
            await session.execute(
                select(Task.title).where(Task.status == "failed").order_by(Task.updated_at.desc()).limit(5)
            )
        ).scalars().all() if hasattr(Task, "title") else []
        section["tasks"] = {"by_status": by_status, "failed_recent": [str(t) for t in failed_recent]}
    except Exception as exc:
        logger.warning("status: tasks section failed: %s", exc)
        section["tasks"] = {"available": False, "error": str(exc)}

    try:
        from dash_backend.executive.models import Approval, ExecutiveTask, Goal

        goals_total = int(
            (await session.execute(select(func.count()).select_from(Goal))).scalar() or 0
        )
        exec_rows = (
            await session.execute(select(ExecutiveTask.status, func.count()).group_by(ExecutiveTask.status))
        ).all()
        pending_approvals = int(
            (
                await session.execute(
                    select(func.count()).select_from(Approval).where(Approval.resolved.is_(False))
                )
            ).scalar()
            or 0
        )
        section["planner"] = {
            "goals_total": goals_total,
            "executive_tasks_by_status": {str(s): int(n) for s, n in exec_rows},
            "pending_approvals": pending_approvals,
        }
    except Exception as exc:
        logger.warning("status: planner section failed: %s", exc)
        section["planner"] = {"available": False, "error": str(exc)}

    try:
        unread = int(
            (
                await session.execute(
                    select(func.count())
                    .select_from(Notification)
                    .where(Notification.read_at.is_(None))
                )
            ).scalar()
            or 0
        )
        section["notifications"] = {"unread": unread}
    except Exception as exc:
        logger.warning("status: notifications section failed: %s", exc)
        section["notifications"] = {"available": False, "error": str(exc)}

    return section


async def _cloud_section(session: AsyncSession) -> dict[str, Any]:
    """Safe cloud/outbox state; deliberately performs no network request."""
    try:
        from dash_backend.config import get_settings
        from dash_backend.sync.outbox import SyncOutboxEvent, STATUS_COMPLETED, STATUS_PROCESSING

        settings = get_settings()
        if not settings.supabase_sync_enabled:
            return {"state": "LOCAL_ONLY", "sync_enabled": False}

        rows = (await session.execute(
            select(SyncOutboxEvent.status, func.count()).group_by(SyncOutboxEvent.status)
        )).all()
        counts = {str(status): int(count) for status, count in rows}
        last_success = await session.scalar(
            select(func.max(SyncOutboxEvent.completed_at)).where(
                SyncOutboxEvent.status == STATUS_COMPLETED
            )
        )
        if counts.get(STATUS_PROCESSING, 0):
            state = "SYNCING"
        elif counts.get("dead_letter", 0) or counts.get("pending", 0):
            state = "DEGRADED"
        else:
            state = "SYNCED"
        return {
            "state": state,
            "sync_enabled": True,
            "outbox": counts,
            "last_successful_sync": last_success.isoformat() if last_success else None,
        }
    except Exception as exc:
        logger.warning("status: cloud section failed: %s", type(exc).__name__)
        return {"state": "ERROR", "available": False}


def _provider_section() -> dict[str, Any]:
    try:
        from dash_backend.config import get_settings
        from dash_backend.llm.provider_manager import get_ollama_manager, get_provider_status

        settings = get_settings()
        status_value = get_provider_status()
        manager = get_ollama_manager()
        status_str = str(getattr(status_value, "value", status_value)).lower()
        return {
            "provider": settings.ai_provider,
            "status": status_str,
            "configured_model": getattr(manager, "get_configured_model", lambda: None)(),
            "base_url": getattr(settings, "ollama_base_url", None),
            "available": status_str == "ready",
        }
    except Exception as exc:
        logger.warning("status: provider section failed: %s", exc)
        return {"available": False, "error": str(exc)}


def _system_section() -> dict[str, Any]:
    try:
        from dash_backend.services.system.system_info import get_system_info

        info = get_system_info()
        if isinstance(info, dict):
            slim = {
                k: info[k]
                for k in ("cpu_percent", "memory_percent", "disk_percent",
                           "hostname", "os", "architecture",
                           "memory_total_gb", "memory_used_gb",
                           "disk_total_gb", "disk_used_gb",
                           "gpu_usage", "gpu_name",
                           "gpu_memory_used_mb", "gpu_memory_total_mb")
                if k in info
            }
            if not slim:
                slim = {k: info.get(k) for k in list(info)[:6]}
            return {"snapshot": slim}
        return {"snapshot": info}
    except Exception as exc:
        logger.warning("status: system section failed: %s", exc)
        return {"available": False, "error": str(exc)}


def _services_section() -> dict[str, Any]:
    out: dict[str, Any] = {}
    try:
        from dash_backend.automation.scheduler import get_scheduler

        scheduler = get_scheduler()
        running = bool(getattr(scheduler, "_running", getattr(scheduler, "running", False)))
        jobs = getattr(scheduler, "jobs", None)
        out["automation_scheduler"] = {
            "running": running,
            "scheduled_jobs": len(jobs) if isinstance(jobs, (list, dict)) else None,
        }
    except Exception as exc:
        out["automation_scheduler"] = {"available": False, "error": str(exc)}

    try:
        from dash_backend.plugins.manager import get_plugin_manager

        manager = get_plugin_manager()
        loaded = getattr(manager, "plugins", None)
        count = len(loaded) if isinstance(loaded, (list, dict)) else None
        out["plugins"] = {"loaded": count}
    except Exception as exc:
        out["plugins"] = {"available": False, "error": str(exc)}

    try:
        from dash_backend.autonomous.background_task_manager import get_background_task_manager

        btm = get_background_task_manager()
        stats = getattr(btm, "get_stats", None)
        out["background_tasks"] = stats() if callable(stats) else {"running": True}
    except Exception as exc:
        out["background_tasks"] = {"available": False, "error": str(exc)}

    return out


@router.get("/overview")
async def status_overview(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> dict[str, Any]:
    """Aggregate work/system status for voice & UI consumption."""
    db_section = await _db_section(session)
    cloud = await _cloud_section(session)

    import asyncio

    provider = await asyncio.to_thread(_provider_section)
    system = await asyncio.to_thread(_system_section)
    services = await asyncio.to_thread(_services_section)

    return {
        "backend": {"status": "ok"},
        **db_section,
        "ai_provider": provider,
        "system": system,
        "services": services,
        "cloud": cloud,
    }
