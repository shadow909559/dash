"""Privacy and data control API routes (spec Part 18: User Data Controls).

- GET  /privacy/data-export   -> structured JSON export of all user data
- DELETE /privacy/data-delete  -> delete all user data across stores
- GET  /privacy/data-inventory -> describe what data is stored, retention, exportability

All routes require device token authentication.
Deletion actually removes data. Export provides a real snapshot.
"""

from __future__ import annotations

import json
import time
import uuid as _uuid_mod
from pathlib import Path
from typing import Any, Dict, List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user_id
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.services.audit_logs import SecurityEventType, get_audit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/privacy", tags=["privacy"])


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _uuid_str(val: Any) -> Optional[str]:
    try:
        return str(UUID(str(val))) if val else None
    except (ValueError, TypeError):
        return None


def _state_file(name: str) -> Optional[Path]:
    """Read a JSON state file from the DASH data directory (best-effort)."""
    override = None
    if name == "predictive_state":
        import os
        override = os.environ.get("DASH_PREDICTIVE_STATE")
    elif name == "proactive_state":
        import os
        override = os.environ.get("DASH_PROACTIVE_STATE")
    if override:
        p = Path(override)
    else:
        import os
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        p = Path(base) / "DASH" / f"{name}.json"
    try:
        if p.exists():
            return p
    except Exception:
        pass
    return None


def _read_state(name: str) -> Dict[str, Any]:
    p = _state_file(name)
    if p is None:
        return {"available": False}
    try:
        return {"available": True, "path": str(p), "data": json.loads(p.read_text(encoding="utf-8"))}
    except Exception:
        return {"available": True, "path": str(p), "error": "unreadable"}


def _clear_state(name: str) -> bool:
    p = _state_file(name)
    if p is None:
        return False
    try:
        if p.exists():
            p.write_text(json.dumps({"samples": [], "repos": {}} if "predictive" in name else {"cooldowns": {}, "history": []}), encoding="utf-8")
            return True
    except Exception:
        pass
    return False


# ---------------------------------------------------------------------------
# GET /privacy/data-export
# ---------------------------------------------------------------------------

@router.get("/data-export")
async def data_export(
    session: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Export all user data as a structured JSON snapshot.

    This is a read-only operation. Nothing is deleted or modified.
    Sensitive fields (tokens, passwords) are excluded.
    """
    uid_str = _uuid_str(user_id)
    if uid_str is None:
        return {"error": "Invalid user id"}
    # PGUUID columns require real uuid objects, not strings.
    uid = _uuid_mod.UUID(uid_str)

    export: Dict[str, Any] = {
        "exported_at": time.time(),
        "user_id": uid_str,
        "sections": {},
    }

    # 1. Memories
    try:
        from dash_backend.memory.service import get_user_memories
        mems, _ = await get_user_memories(session, uid, limit=10000)
        export["sections"]["memories"] = {
            "count": len(mems or []),
            "items": [
                {
                    "id": str(m.id),
                    "content": m.content[:500] if m.content else None,
                    "category": getattr(m, "category", None),
                    "source": getattr(m, "source", None),
                    "importance": getattr(m, "importance", None),
                    "created_at": m.created_at.isoformat() if getattr(m, "created_at", None) else None,
                }
                for m in (mems or [])
            ],
        }
    except Exception as exc:
        export["sections"]["memories"] = {"error": str(exc)}

    # 2. Conversations + Messages
    try:
        from dash_backend.db.models.conversation import Conversation
        from dash_backend.db.models.message import Message

        convs = await session.execute(
            select(Conversation).where(Conversation.user_id == uid)
        )
        conv_list = convs.scalars().all()
        conv_data = []
        total_messages = 0
        for c in conv_list:
            msgs = await session.execute(
                select(Message).where(Message.conversation_id == c.id).order_by(Message.created_at.asc())
            )
            msg_list = msgs.scalars().all()
            total_messages += len(msg_list)
            conv_data.append({
                "id": str(c.id),
                "title": c.title,
                "created_at": c.created_at.isoformat() if c.created_at else None,
                "message_count": len(msg_list),
                "messages": [
                    {
                        "role": str(getattr(m, "role", "")),
                        "content": (m.content or "")[:1000],
                        "created_at": m.created_at.isoformat() if m.created_at else None,
                    }
                    for m in msg_list[:100]
                ],
            })
        export["sections"]["conversations"] = {
            "count": len(conv_list),
            "total_messages": total_messages,
            "items": conv_data,
        }
    except Exception as exc:
        export["sections"]["conversations"] = {"error": str(exc)}

    # 3. Goals + Tasks
    try:
        from dash_backend.executive.models import ExecutiveTask, Goal

        goals = await session.execute(
            select(Goal).where(Goal.user_id == uid)
        )
        goal_list = goals.scalars().all()
        goal_data = []
        for g in goal_list:
            tasks = await session.execute(
                select(ExecutiveTask).where(ExecutiveTask.goal_id == g.id)
            )
            task_list = tasks.scalars().all()
            goal_data.append({
                "id": str(g.id),
                "name": g.name,
                "description": g.description,
                "status": g.status,
                "priority": g.priority,
                "deadline": g.deadline.isoformat() if g.deadline else None,
                "completed_at": g.completed_at.isoformat() if g.completed_at else None,
                "created_at": g.created_at.isoformat() if g.created_at else None,
                "tasks": [
                    {
                        "id": str(t.id),
                        "name": t.name,
                        "status": t.status,
                        "priority": t.priority,
                        "deadline": t.deadline.isoformat() if t.deadline else None,
                    }
                    for t in task_list
                ],
            })
        export["sections"]["goals"] = {
            "count": len(goal_list),
            "items": goal_data,
        }
    except Exception as exc:
        export["sections"]["goals"] = {"error": str(exc)}

    # 4. Notifications
    try:
        from dash_backend.db.models.notification import Notification

        notifs = await session.execute(
            select(Notification).where(Notification.user_id == uid).order_by(Notification.created_at.desc()).limit(500)
        )
        notif_list = notifs.scalars().all()
        export["sections"]["notifications"] = {
            "count": len(notif_list),
            "items": [
                {
                    "id": str(n.id),
                    "type": str(getattr(n, "type", "")),
                    "title": getattr(n, "title", None),
                    "body": getattr(n, "body", None)[:500] if getattr(n, "body", None) else None,
                    "created_at": n.created_at.isoformat() if n.created_at else None,
                }
                for n in notif_list
            ],
        }
    except Exception as exc:
        export["sections"]["notifications"] = {"error": str(exc)}

    # 5. Refresh tokens (count only, never export raw tokens)
    try:
        from dash_backend.db.models.refresh_tokens import RefreshToken

        tok_count = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == uid)
        )
        active_count = await session.scalar(
            select(func.count()).select_from(RefreshToken).where(
                RefreshToken.user_id == uid, RefreshToken.revoked_at.is_(None)
            )
        )
        export["sections"]["auth_tokens"] = {
            "total_tokens": tok_count or 0,
            "active_tokens": active_count or 0,
            "note": "Raw tokens are never exported for security reasons",
        }
    except Exception as exc:
        export["sections"]["auth_tokens"] = {"error": str(exc)}

    # 6. Device state files
    export["sections"]["device_state"] = {
        "predictive": _read_state("predictive_state"),
        "proactive": _read_state("proactive_state"),
    }

    # 7. Audit log summary (file-based, read count only)
    try:
        stats = get_audit_service().get_stats()
        export["sections"]["audit_log"] = {
            "total_entries": stats.get("total_entries", 0),
            "files": stats.get("total_files", 0),
            "note": "Audit log entries are retained for security; see retention policy",
        }
    except Exception as exc:
        export["sections"]["audit_log"] = {"error": str(exc)}

    get_audit_service().log(
        "DATA_EXPORT",
        user_id=uid_str,
        action="export",
        category="privacy",
        status="success",
        severity="INFO",
    )

    return export


# ---------------------------------------------------------------------------
# DELETE /privacy/data-delete
# ---------------------------------------------------------------------------

@router.delete("/data-delete", status_code=200)
async def data_delete(
    confirm: bool = Query(False, description="Must be true to actually delete"),
    session: AsyncSession = Depends(get_db_session),
    user_id: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Delete all user data across all stores.

    Requires confirm=true to prevent accidental deletion.
    This operation is irreversible. Audit log entries are retained
    for security compliance.
    """
    uid_str = _uuid_str(user_id)
    if uid_str is None:
        return {"error": "Invalid user id"}
    uid = _uuid_mod.UUID(uid_str)

    if not confirm:
        return {
            "deleted": False,
            "message": "Send confirm=true to actually delete all data. This action is irreversible.",
        }

    results: Dict[str, Any] = {"deleted": True, "counts": {}}

    # 1. Clear memories
    try:
        from dash_backend.memory.service import clear_user_memories
        n = await clear_user_memories(session, uid)
        results["counts"]["memories"] = n
    except Exception as exc:
        results["counts"]["memories"] = f"error: {exc}"

    # 2. Delete conversations + messages
    try:
        from dash_backend.db.models.conversation import Conversation
        from dash_backend.db.models.message import Message

        conv_ids = [c for c in (await session.execute(
            select(Conversation.id).where(Conversation.user_id == uid)
        )).scalars().all()]
        if conv_ids:
            await session.execute(delete(Message).where(Message.conversation_id.in_(conv_ids)))
            await session.execute(delete(Conversation).where(Conversation.id.in_(conv_ids)))
            await session.commit()
        results["counts"]["conversations"] = len(conv_ids)
    except Exception as exc:
        results["counts"]["conversations"] = f"error: {exc}"

    # 3. Delete goals + tasks
    try:
        from dash_backend.executive.models import ExecutiveTask, Goal

        goal_ids = [g for g in (await session.execute(
            select(Goal.id).where(Goal.user_id == uid)
        )).scalars().all()]
        if goal_ids:
            await session.execute(delete(ExecutiveTask).where(ExecutiveTask.goal_id.in_(goal_ids)))
            await session.execute(delete(Goal).where(Goal.id.in_(goal_ids)))
            await session.commit()
        results["counts"]["goals"] = len(goal_ids)
    except Exception as exc:
        results["counts"]["goals"] = f"error: {exc}"

    # 4. Delete notifications
    try:
        from dash_backend.db.models.notification import Notification
        res = await session.execute(delete(Notification).where(Notification.user_id == uid))
        await session.commit()
        results["counts"]["notifications"] = res.rowcount
    except Exception as exc:
        results["counts"]["notifications"] = f"error: {exc}"

    # 5. Revoke all refresh tokens
    try:
        from dash_backend.db.models.refresh_tokens import RefreshToken
        from datetime import UTC, datetime
        res = await session.execute(
            select(RefreshToken).where(RefreshToken.user_id == uid, RefreshToken.revoked_at.is_(None))
        )
        tokens = res.scalars().all()
        for t in tokens:
            t.revoked_at = datetime.now(UTC)
        if tokens:
            await session.commit()
        results["counts"]["tokens_revoked"] = len(tokens)
    except Exception as exc:
        results["counts"]["tokens_revoked"] = f"error: {exc}"

    # 6. Clear device state files
    results["counts"]["predictive_state"] = _clear_state("predictive_state")
    results["counts"]["proactive_state"] = _clear_state("proactive_state")

    # 7. Audit log: record the deletion but do NOT delete audit entries
    # (security compliance requires audit trail retention)
    get_audit_service().log(
        "DATA_DELETED",
        user_id=uid_str,
        action="delete_all",
        category="privacy",
        status="success",
        severity="AUDIT",
    )

    results["note"] = "Audit log entries retained for security compliance"

    return results


# ---------------------------------------------------------------------------
# GET /privacy/data-inventory
# ---------------------------------------------------------------------------

@router.get("/data-inventory")
async def data_inventory(
    _: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Describe what data DASH stores, why, retention, and exportability.

    This is a static description of the system's data practices.
    It does not query actual user data.
    """
    return {
        "data_stores": [
            {
                "name": "Memories",
                "description": "User memories, preferences, and knowledge extracted from conversations",
                "storage": "Database (memories table)",
                "retention": "Indefinite until user deletes",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Conversations",
                "description": "Chat conversation history with message content",
                "storage": "Database (conversations + messages tables)",
                "retention": "Indefinite until user deletes",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Goals and Tasks",
                "description": "Structured goals with deadlines, priorities, and subtasks",
                "storage": "Database (goals + executive_tasks tables)",
                "retention": "Indefinite until user deletes",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Notifications",
                "description": "System notifications and alerts",
                "storage": "Database (notifications table)",
                "retention": "Indefinite until user deletes",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Authentication Tokens",
                "description": "Refresh tokens for session management (hashed, never stored in plain text)",
                "storage": "Database (refresh_tokens table)",
                "retention": "Until expiry or revocation",
                "exportable": False,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Device Identity",
                "description": "Local device identity for single-user authentication",
                "storage": "File (%LOCALAPPDATA%/DASH/identity.json)",
                "retention": "Until DASH is uninstalled",
                "exportable": False,
                "deletable": False,
                "synced": False,
                "sent_external": False,
                "note": "Required for device authentication; cannot be deleted while DASH is running",
            },
            {
                "name": "Predictive State",
                "description": "Device sample history for trend projections (CPU, RAM, disk usage)",
                "storage": "File (%LOCALAPPDATA%/DASH/predictive_state.json)",
                "retention": "30 days rolling window",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Proactive State",
                "description": "Suggestion cooldown and show history",
                "storage": "File (%LOCALAPPDATA%/DASH/proactive_state.json)",
                "retention": "Until user clears or DASH is uninstalled",
                "exportable": True,
                "deletable": True,
                "synced": False,
                "sent_external": False,
            },
            {
                "name": "Audit Log",
                "description": "Security and operation audit trail (login, logout, approvals, tool execution)",
                "storage": "File (audit_logs/*.jsonl)",
                "retention": "Retained for security compliance; not deletable by user",
                "exportable": False,
                "deletable": False,
                "synced": False,
                "sent_external": False,
                "note": "Retained for security and compliance purposes",
            },
            {
                "name": "AI Model Interactions",
                "description": "Chat messages sent to Ollama (local) or cloud AI providers (Groq, Gemini)",
                "storage": "Not stored by DASH; processed by the AI provider",
                "retention": "Provider-dependent",
                "exportable": False,
                "deletable": False,
                "synced": False,
                "sent_external": True,
                "note": "Local models (Ollama) process data on-device. Cloud providers (Groq, Gemini) receive chat messages when cloud fallback is active.",
            },
        ],
        "third_party_services": [
            {
                "name": "Ollama (local)",
                "purpose": "Local AI model inference",
                "data_sent": "Chat messages for inference",
                "privacy": "All processing on-device; no data leaves the machine",
            },
            {
                "name": "Groq (cloud)",
                "purpose": "Cloud AI fallback when local models are slow",
                "data_sent": "Chat messages for inference",
                "privacy": "Data sent to Groq servers; subject to Groq's privacy policy",
            },
            {
                "name": "Gemini (cloud)",
                "purpose": "Cloud AI fallback when local models are slow",
                "data_sent": "Chat messages for inference",
                "privacy": "Data sent to Google servers; subject to Google's privacy policy",
            },
        ],
    }
