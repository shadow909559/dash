"""REST API routes for notification management with WebSocket push support."""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timezone

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
# In-memory notification storage with WebSocket broadcast
# ──────────────────────────────────────────────

_notifications_store: dict[str, dict] = {}
_next_notif_id = 0
_websocket_connections: dict[str, list] = {}  # user_id -> list of websocket connections

# Per-user notification category preferences
# Categories: "process" (app launch/close), "error" (error notifications), "system" (system alerts)
_notification_prefs: dict[str, dict[str, bool]] = {}

DEFAULT_PREFS: dict[str, bool] = {
    "process": True,
    "error": True,
    "system": True,
}



def get_user_notif_prefs(user_id: str) -> dict[str, bool]:
    """Get notification category preferences for a user."""
    return _notification_prefs.get(user_id, dict(DEFAULT_PREFS))



def is_notif_category_enabled(user_id: str, category: str) -> bool:
    """Check if a notification category is enabled for a user."""
    prefs = get_user_notif_prefs(user_id)
    return prefs.get(category, True)


def register_websocket(user_id: str, websocket):
    """Register a WebSocket connection for a user to receive push notifications."""
    if user_id not in _websocket_connections:
        _websocket_connections[user_id] = []
    _websocket_connections[user_id].append(websocket)


def unregister_websocket(user_id: str, websocket):
    """Unregister a WebSocket connection."""
    if user_id in _websocket_connections:
        _websocket_connections[user_id] = [ws for ws in _websocket_connections[user_id] if ws != websocket]
        if not _websocket_connections[user_id]:
            del _websocket_connections[user_id]


async def broadcast_notification(user_id: str, notification: dict):
    """Broadcast a notification to all connected WebSocket clients for a user.
    
    Filters by category preference. Notifications without a category are always sent.
    """
    # Check category filter
    category = notification.get("category", "system")
    if not is_notif_category_enabled(user_id, category):
        logger.debug("Notification filtered: category=%s user=%s title=%s", category, user_id, notification.get("title", ""))
        return
    if user_id in _websocket_connections:
        import asyncio
        for ws in _websocket_connections[user_id]:
            try:
                await ws.send_json({
                    "type": "notification.push",
                    "notification": notification
                })
            except Exception:
                # Remove dead connections
                _websocket_connections[user_id].remove(ws)


async def send_notification(user_id: str, title: str, message: str = "", notif_type: str = "info"):
    """Helper function to create and broadcast a notification from anywhere in the codebase."""
    notif_id = _generate_notif_id()
    notif = {
        "id": notif_id,
        "user_id": user_id,
        "title": title,
        "message": message,
        "type": notif_type,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications_store[notif_id] = notif
    await broadcast_notification(user_id, notif)
    return notif


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


class NotificationCreate(BaseModel):
    title: str
    message: str = ""
    type: str = "info"  # info, success, warning, error


@router.post("", response_model=NotificationRead, status_code=status.HTTP_201_CREATED)
async def create_notification(
    payload: NotificationCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> NotificationRead:
    """Create a new notification and push it to connected clients."""
    notif_id = _generate_notif_id()
    notif = {
        "id": notif_id,
        "user_id": str(user.id),
        "title": payload.title,
        "message": payload.message,
        "type": payload.type,
        "read": False,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    _notifications_store[notif_id] = notif
    
    # Broadcast to WebSocket clients
    await broadcast_notification(str(user.id), notif)
    
    return NotificationRead(
        id=notif["id"],
        title=notif["title"],
        message=notif["message"],
        read=notif["read"],
        created_at=notif["created_at"],
    )


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


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
async def clear_notifications(
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_db_session),
) -> None:
    """Clear all notifications for the current user."""
    to_delete = [nid for nid, n in _notifications_store.items() if n.get("user_id") == str(user.id)]
    for nid in to_delete:
        del _notifications_store[nid]
    return None


# ── Notification Category Preferences ──────────────────────


class NotificationPrefsResponse(BaseModel):
    process: bool = True
    error: bool = True
    system: bool = True


class NotificationPrefsUpdate(BaseModel):
    process: Optional[bool] = None
    error: Optional[bool] = None
    system: Optional[bool] = None


@router.get("/preferences", response_model=NotificationPrefsResponse)
async def get_notification_preferences(
    user: User = Depends(get_current_user),
) -> NotificationPrefsResponse:
    """Get notification category preferences for the current user."""
    prefs = get_user_notif_prefs(str(user.id))
    return NotificationPrefsResponse(**prefs)


@router.put("/preferences", response_model=NotificationPrefsResponse)
async def update_notification_preferences(
    payload: NotificationPrefsUpdate,
    user: User = Depends(get_current_user),
) -> NotificationPrefsResponse:
    """Update notification category preferences for the current user."""
    user_id = str(user.id)
    current = get_user_notif_prefs(user_id)
    updated = dict(current)
    if payload.process is not None:
        updated["process"] = payload.process
    if payload.error is not None:
        updated["error"] = payload.error
    if payload.system is not None:
        updated["system"] = payload.system
    _notification_prefs[user_id] = updated
    logger.info("Notification preferences updated for user %s: %s", user_id, updated)
    return NotificationPrefsResponse(**updated)
