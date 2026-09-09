# -*- coding: utf-8 -*-
"""Push Notification Service — FCM, Apple Push, Web Push, notification channels, scheduling."""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class NotificationChannel:
    """A notification channel for routing."""
    id: str
    name: str
    type: str  # "push", "email", "sms", "webhook", "in_app"
    enabled: bool = True
    config: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class PushNotification:
    """A push notification."""
    id: str
    title: str
    body: str
    channel: str = "default"
    priority: str = "normal"  # "low", "normal", "high", "urgent"
    data: dict = field(default_factory=dict)
    image_url: str = ""
    action_url: str = ""
    status: str = "pending"  # "pending", "sent", "delivered", "failed"
    scheduled_at: str = ""
    sent_at: str = ""
    read_at: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class NotificationTemplate:
    """A notification template for recurring notifications."""
    id: str
    name: str
    title_template: str
    body_template: str
    channel: str = "default"
    schedule: str = ""  # "daily", "weekly", "custom_cron"
    enabled: bool = True
    variables: dict = field(default_factory=dict)


class PushNotificationService:
    """Push notification management service."""

    PRIORITY_LEVELS = ["low", "normal", "high", "urgent"]

    def __init__(self):
        self._channels: dict[str, NotificationChannel] = {}
        self._notifications: list[PushNotification] = []
        self._templates: dict[str, NotificationTemplate] = {}
        self._subscribers: dict[str, dict] = {}  # device_id -> config
        self._preferences: dict[str, dict] = {}  # user_id -> preferences
        self._quiet_hours: dict[str, dict] = {}

    # ── Channels ─────────────────────────────────────────────────────────

    def create_channel(self, name: str, channel_type: str, config: dict = None) -> dict:
        """Create a notification channel."""
        channel_id = f"ch_{secrets.token_hex(6)}"
        channel = NotificationChannel(
            id=channel_id,
            name=name,
            type=channel_type,
            config=config or {},
        )
        self._channels[channel_id] = channel
        return {"id": channel_id, "name": name, "type": channel_type}

    def get_channels(self) -> list[dict]:
        """Get all notification channels."""
        return [
            {"id": c.id, "name": c.name, "type": c.type, "enabled": c.enabled}
            for c in self._channels.values()
        ]

    def update_channel(self, channel_id: str, **kwargs) -> dict:
        """Update a notification channel."""
        if channel_id not in self._channels:
            return {"status": "not_found"}
        ch = self._channels[channel_id]
        for key, val in kwargs.items():
            if hasattr(ch, key):
                setattr(ch, key, val)
        return {"status": "updated", "id": channel_id}

    def delete_channel(self, channel_id: str) -> dict:
        """Delete a notification channel."""
        if channel_id in self._channels:
            del self._channels[channel_id]
            return {"status": "deleted"}
        return {"status": "not_found"}

    # ── Notifications ────────────────────────────────────────────────────

    def send(self, title: str, body: str, channel: str = "default", priority: str = "normal",
             data: dict = None, image_url: str = "", action_url: str = "",
             scheduled_at: str = "") -> dict:
        """Send a push notification."""
        notif = PushNotification(
            id=f"n_{secrets.token_hex(8)}",
            title=title,
            body=body,
            channel=channel,
            priority=priority,
            data=data or {},
            image_url=image_url,
            action_url=action_url,
            scheduled_at=scheduled_at,
        )

        # Check quiet hours
        if self._is_quiet_hours():
            notif.status = "deferred"
        elif scheduled_at:
            notif.status = "scheduled"
        else:
            notif.status = "sent"
            notif.sent_at = datetime.now(timezone.utc).isoformat()

        self._notifications.append(notif)
        return {
            "id": notif.id,
            "status": notif.status,
            "title": title,
            "channel": channel,
        }

    def get_notifications(self, channel: str = None, status: str = None, limit: int = 50) -> list[dict]:
        """Get notifications with filtering."""
        notifs = self._notifications
        if channel:
            notifs = [n for n in notifs if n.channel == channel]
        if status:
            notifs = [n for n in notifs if n.status == status]
        return [
            {
                "id": n.id, "title": n.title, "body": n.body, "channel": n.channel,
                "priority": n.priority, "status": n.status, "created_at": n.created_at,
                "read_at": n.read_at,
            }
            for n in notifs[-limit:]
        ]

    def mark_read(self, notification_id: str) -> dict:
        """Mark a notification as read."""
        for n in self._notifications:
            if n.id == notification_id:
                n.read_at = datetime.now(timezone.utc).isoformat()
                return {"status": "read", "id": notification_id}
        return {"status": "not_found"}

    def mark_all_read(self) -> dict:
        """Mark all notifications as read."""
        now = datetime.now(timezone.utc).isoformat()
        count = 0
        for n in self._notifications:
            if not n.read_at:
                n.read_at = now
                count += 1
        return {"marked_read": count}

    def clear(self, channel: str = None) -> dict:
        """Clear notifications."""
        if channel:
            before = len(self._notifications)
            self._notifications = [n for n in self._notifications if n.channel != channel]
            return {"cleared": before - len(self._notifications)}
        count = len(self._notifications)
        self._notifications.clear()
        return {"cleared": count}

    def get_unread_count(self) -> dict:
        """Get unread notification counts."""
        counts = {}
        for n in self._notifications:
            if not n.read_at:
                counts[n.channel] = counts.get(n.channel, 0) + 1
        counts["total"] = sum(counts.values())
        return counts

    # ── Templates ────────────────────────────────────────────────────────

    def create_template(self, name: str, title_template: str, body_template: str,
                       channel: str = "default", schedule: str = "") -> dict:
        """Create a notification template."""
        tpl_id = f"tpl_{secrets.token_hex(6)}"
        template = NotificationTemplate(
            id=tpl_id,
            name=name,
            title_template=title_template,
            body_template=body_template,
            channel=channel,
            schedule=schedule,
        )
        self._templates[tpl_id] = template
        return {"id": tpl_id, "name": name, "schedule": schedule}

    def get_templates(self) -> list[dict]:
        """Get all notification templates."""
        return [
            {"id": t.id, "name": t.name, "channel": t.channel, "schedule": t.schedule, "enabled": t.enabled}
            for t in self._templates.values()
        ]

    def send_from_template(self, template_id: str, variables: dict = None) -> dict:
        """Send notification using a template."""
        template = self._templates.get(template_id)
        if not template:
            return {"status": "template_not_found"}

        title = template.title_template
        body = template.body_template
        if variables:
            for key, val in variables.items():
                title = title.replace(f"{{{key}}}", str(val))
                body = body.replace(f"{{{key}}}", str(val))

        return self.send(title=title, body=body, channel=template.channel)

    def delete_template(self, template_id: str) -> dict:
        """Delete a notification template."""
        if template_id in self._templates:
            del self._templates[template_id]
            return {"status": "deleted"}
        return {"status": "not_found"}

    # ── Subscribers ──────────────────────────────────────────────────────

    def register_device(self, device_id: str, platform: str, token: str = "") -> dict:
        """Register a device for push notifications."""
        self._subscribers[device_id] = {
            "device_id": device_id,
            "platform": platform,
            "token": token,
            "registered_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        return {"status": "registered", "device_id": device_id, "platform": platform}

    def unregister_device(self, device_id: str) -> dict:
        """Unregister a device."""
        if device_id in self._subscribers:
            del self._subscribers[device_id]
            return {"status": "unregistered"}
        return {"status": "not_found"}

    def get_subscribers(self) -> list[dict]:
        """Get all registered devices."""
        return list(self._subscribers.values())

    # ── Preferences & Quiet Hours ────────────────────────────────────────

    def set_preferences(self, user_id: str, preferences: dict) -> dict:
        """Set user notification preferences."""
        self._preferences[user_id] = preferences
        return {"status": "saved", "user_id": user_id}

    def get_preferences(self, user_id: str) -> dict:
        """Get user notification preferences."""
        return self._preferences.get(user_id, {
            "channels": {"push": True, "email": False, "sms": False},
            "priority_filter": "normal",
            "sound_enabled": True,
        })

    def set_quiet_hours(self, user_id: str, start_hour: int, end_hour: int) -> dict:
        """Set quiet hours for notifications."""
        self._quiet_hours[user_id] = {
            "start_hour": start_hour,
            "end_hour": end_hour,
        }
        return {"user_id": user_id, "quiet_hours": f"{start_hour:02d}:00 - {end_hour:02d}:00"}

    def get_quiet_hours(self, user_id: str) -> dict:
        """Get quiet hours."""
        return self._quiet_hours.get(user_id, {"start_hour": 23, "end_hour": 7})

    def _is_quiet_hours(self) -> bool:
        """Check if current time is in quiet hours (global default)."""
        now = datetime.now(timezone.utc).hour
        return 23 <= now or now < 7

    # ── Stats ────────────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        """Get notification statistics."""
        total = len(self._notifications)
        sent = sum(1 for n in self._notifications if n.status == "sent")
        unread = sum(1 for n in self._notifications if not n.read_at)
        return {
            "total_notifications": total,
            "sent": sent,
            "unread": unread,
            "channels": len(self._channels),
            "templates": len(self._templates),
            "devices": len(self._subscribers),
        }


# Singleton
_notification_service: Optional[PushNotificationService] = None


def get_notification_service() -> PushNotificationService:
    global _notification_service
    if _notification_service is None:
        _notification_service = PushNotificationService()
    return _notification_service
