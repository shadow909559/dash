"""REST API routes for notification management."""

from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.auth.dependencies import get_current_user
from dash_backend.db.models.user import User
from dash_backend.db.session import get_db_session
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/notifications", tags=["notifications"])


# ──────────────────────────────────────────────
# In-memory notification storage
# ──────────────────────────────────────────────

_notifications_store: dict[str, dict] = {}
_next_notif_id = 0


def _generate_notif_id() -> str:
    global _next_notif_id
    _next_notif_id += 1
    return f"notif_{_next_notif_id}"


class NotificationRead(BaseModel):
    id: str
    title: str
    message: str
    read: bool = False
    created_at: str


@router.get("", response_model=List[NotificationRead])
async def list_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> List[NotificationRead]:
    """List all notifications for the current user."""
    user_notifs = [
        n for n in _notifications_store.values()
        if n.get("user_id") == str(user.id)
    ]
    # Sort by created_at descending
    user_notifs.sort(key=lambda n: n.get("created_at", ""), reverse=True)
    return [
        NotificationRead(
            id=n["id"],
            title=n["title"],
            message=n.get("message", n.get("body", "")),
            read=n.get("read", False),
            created_at=n.get("created_at", ""),
        )
        for n in user_notifs
    ]


@router.patch("/{notification_id}/read", status_code=status.HTTP_204_NO_CONTENT)
async def mark_notification_read(
    notification_id: str,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Mark a notification as read."""
    notif = _notifications_store.get(notification_id)
    if notif is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    if notif.get("user_id") != str(user.id):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not your notification")
    notif["read"] = True
    return None
