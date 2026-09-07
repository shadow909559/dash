"""Security and audit log API routes.

- GET /security/audit-log  -> query audit log entries
- GET /security/audit-log/stats -> audit log statistics
- GET /security/sessions -> list active sessions
- POST /security/sessions/{id}/revoke -> revoke a session
- POST /security/sessions/revoke-all -> revoke all sessions

Requires the local device token (internal API).
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status

from dash_backend.auth.dependencies import get_current_user, get_current_user_id
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger
from dash_backend.services.audit_logs import SecurityEventType, get_audit_service

logger = get_logger(__name__)

router = APIRouter(prefix="/security", tags=["security"])


@router.get("/audit-log")
async def get_audit_log(
    event_type: Optional[str] = Query(None, description="Filter by event type (e.g. LOGIN_SUCCESS)"),
    category: Optional[str] = Query(None, description="Filter by category (e.g. auth)"),
    severity: Optional[str] = Query(None, description="Filter by severity (INFO, WARNING, ERROR)"),
    limit: int = Query(100, ge=1, le=1000, description="Max entries to return"),
    _: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Query security audit log entries."""
    service = get_audit_service()
    entries = service.query(event_type=event_type, limit=limit)
    # Optional severity/category filtering (post-fetch on file-based store)
    if severity:
        entries = [e for e in entries if e.get("severity") == severity]
    if category:
        entries = [e for e in entries if e.get("category") == category]
    return {
        "count": len(entries),
        "entries": entries,
    }


@router.get("/audit-log/stats")
async def audit_log_stats(
    _: str = Depends(get_current_user_id),
) -> Dict[str, Any]:
    """Audit log statistics: file count, total entries, enabled state."""
    return get_audit_service().get_stats()


# ─── Session Management ──────────────────────────────────────────


@router.get("/sessions")
async def list_sessions(
    user: User = Depends(get_current_user),
    session=Depends(get_db_session),
    include_revoked: bool = Query(False, description="Include revoked/expired sessions"),
) -> Dict[str, Any]:
    """List all sessions for the current user.

    Shows active sessions with device info, creation time, and expiry.
    Revoked/expired sessions are hidden by default.
    """
    from dash_backend.auth.session_service import list_user_sessions, session_to_dict

    sessions = await list_user_sessions(session, user.id, include_revoked=include_revoked)
    return {
        "count": len(sessions),
        "sessions": [session_to_dict(s) for s in sessions],
    }


@router.post("/sessions/{session_id}/revoke")
async def revoke_session_endpoint(
    session_id: uuid.UUID,
    user: User = Depends(get_current_user),
    session=Depends(get_db_session),
) -> Dict[str, Any]:
    """Revoke a specific session.

    The session's refresh token is also revoked so it cannot be used again.
    """
    from dash_backend.auth.session_service import revoke_session

    revoked = await revoke_session(session, session_id, user.id)
    if not revoked:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found",
        )

    get_audit_service().log(
        SecurityEventType.SESSION_REVOKED,
        user_id=str(user.id),
        action="revoke_session",
        category="security",
        status="success",
        details={"session_id": str(session_id)},
        severity="INFO",
    )
    return {"revoked": True, "session_id": str(session_id)}


@router.post("/sessions/revoke-all")
async def revoke_all_sessions_endpoint(
    user: User = Depends(get_current_user),
    session=Depends(get_db_session),
) -> Dict[str, Any]:
    """Revoke all sessions for the current user.

    All refresh tokens are also revoked. The user must re-authenticate.
    """
    from dash_backend.auth.session_service import revoke_all_sessions

    count = await revoke_all_sessions(session, user.id)
    get_audit_service().log(
        SecurityEventType.SESSION_REVOKED,
        user_id=str(user.id),
        action="revoke_all_sessions",
        category="security",
        status="success",
        details={"sessions_revoked": count},
        severity="INFO",
    )
    return {"revoked": True, "count": count}
