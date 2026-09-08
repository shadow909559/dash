"""Communication: notification routing, message digest, batch processing, connectors."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class NotificationRouter:
    """Route notifications to the right channel based on priority and user preferences."""

    CHANNELS = ["desktop", "mobile", "email", "slack", "telegram", "sms", "webhook"]

    def __init__(self) -> None:
        self._rules: list[dict] = [
            {"id": "r1", "priority": "urgent", "channels": ["desktop", "mobile", "sms"], "enabled": True},
            {"id": "r2", "priority": "high", "channels": ["desktop", "mobile"], "enabled": True},
            {"id": "r3", "priority": "normal", "channels": ["desktop"], "enabled": True},
            {"id": "r4", "priority": "low", "channels": [], "enabled": True},
        ]
        self._queue: list[dict] = []
        self._sent: list[dict] = []
        self._dnd_enabled = False
        self._dnd_channels: list[str] = []

    def route(self, notification: dict) -> dict:
        if self._dnd_enabled:
            allowed = [ch for ch in self._rules[0]["channels"] if ch not in self._dnd_channels]
            if not allowed:
                self._queue.append(notification)
                return {"ok": True, "queued": True, "reason": "DND active"}
        priority = notification.get("priority", "normal")
        for rule in self._rules:
            if rule["priority"] == priority and rule["enabled"]:
                notification["routed_channels"] = rule["channels"]
                self._sent.append({**notification, "routed_at": datetime.now(timezone.utc).isoformat()})
                return {"ok": True, "channels": rule["channels"]}
        return {"ok": False, "reason": "No matching rule"}

    def get_rules(self) -> list[dict]:
        return list(self._rules)

    def update_rule(self, rule_id: str, channels: list[str]) -> dict:
        for r in self._rules:
            if r["id"] == rule_id:
                r["channels"] = channels
                return {"ok": True}
        return {"ok": False, "reason": "Rule not found"}

    def set_dnd(self, enabled: bool, channels: list[str] | None = None) -> dict:
        self._dnd_enabled = enabled
        self._dnd_channels = channels or self.CHANNELS
        return {"ok": True, "dnd": enabled}

    def get_queue(self) -> list[dict]:
        return list(self._queue)

    def flush_queue(self) -> dict:
        count = len(self._queue)
        self._sent.extend(self._queue)
        self._queue.clear()
        return {"flushed": count}

    def get_sent(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._sent[-limit:]))


class MessageDigest:
    """Aggregate and summarize notifications/messages into digests."""

    def __init__(self) -> None:
        self._digests: list[dict] = []
        self._pending: list[dict] = []

    def add_to_pending(self, message: dict) -> None:
        self._pending.append({**message, "added_at": datetime.now(timezone.utc).isoformat()})

    def generate_digest(self, period: str = "daily") -> dict:
        now = datetime.now(timezone.utc)
        if period == "hourly":
            cutoff = now - __import__("datetime").timedelta(hours=1)
        elif period == "daily":
            cutoff = now - __import__("datetime").timedelta(days=1)
        else:
            cutoff = now - __import__("datetime").timedelta(weeks=1)
        cutoff_str = cutoff.isoformat()
        items = [m for m in self._pending if m.get("added_at", "") >= cutoff_str]
        self._pending = [m for m in self._pending if m.get("added_at", "") < cutoff_str]
        digest = {"id": f"digest_{len(self._digests)}", "period": period, "count": len(items), "items": items[:20], "generated_at": now.isoformat()}
        self._digests.append(digest)
        return digest

    def get_digests(self, limit: int = 10) -> list[dict]:
        return list(reversed(self._digests[-limit:]))

    def get_pending_count(self) -> int:
        return len(self._pending)


class BatchProcessor:
    """Process large batches of items with progress tracking."""

    def __init__(self) -> None:
        self._jobs: list[dict] = []

    def create_job(self, job_type: str, items: list, batch_size: int = 50) -> dict:
        job = {"id": f"job_{len(self._jobs)}", "type": job_type, "total": len(items), "batch_size": batch_size, "processed": 0, "failed": 0, "status": "pending", "created_at": datetime.now(timezone.utc).isoformat()}
        self._jobs.append(job)
        return {"ok": True, "job": job}

    def process_batch(self, job_id: str, count: int = 1) -> dict:
        for job in self._jobs:
            if job["id"] == job_id:
                job["processed"] = min(job["processed"] + count, job["total"])
                if job["processed"] >= job["total"]:
                    job["status"] = "completed"
                else:
                    job["status"] = "running"
                return {"ok": True, "processed": job["processed"], "total": job["total"], "progress": round(job["processed"] / job["total"] * 100, 1)}
        return {"ok": False, "reason": "Job not found"}

    def get_jobs(self) -> list[dict]:
        return list(self._jobs)

    def get_job(self, job_id: str) -> Optional[dict]:
        return next((j for j in self._jobs if j["id"] == job_id), None)


class ExternalConnector:
    """Base for third-party service connectors (Slack, Telegram, etc.)."""

    def __init__(self) -> None:
        self._connectors: dict[str, dict] = {
            "slack": {"name": "Slack", "status": "disconnected", "config": {}},
            "telegram": {"name": "Telegram", "status": "disconnected", "config": {}},
            "notion": {"name": "Notion", "status": "disconnected", "config": {}},
            "github": {"name": "GitHub", "status": "disconnected", "config": {}},
            "google_calendar": {"name": "Google Calendar", "status": "disconnected", "config": {}},
            "email_imap": {"name": "Email (IMAP)", "status": "disconnected", "config": {}},
            "zapier": {"name": "Zapier", "status": "disconnected", "config": {}},
            "discord": {"name": "Discord", "status": "disconnected", "config": {}},
        }
        self._events: list[dict] = []

    def get_connectors(self) -> list[dict]:
        return [{"id": k, **v} for k, v in self._connectors.items()]

    def connect(self, connector_id: str, config: dict) -> dict:
        if connector_id not in self._connectors:
            return {"ok": False, "reason": "Unknown connector"}
        self._connectors[connector_id]["status"] = "connected"
        self._connectors[connector_id]["config"] = config
        return {"ok": True, "connector": self._connectors[connector_id]}

    def disconnect(self, connector_id: str) -> dict:
        if connector_id in self._connectors:
            self._connectors[connector_id]["status"] = "disconnected"
            self._connectors[connector_id]["config"] = {}
            return {"ok": True}
        return {"ok": False, "reason": "Not found"}

    def send_event(self, connector_id: str, event_type: str, payload: dict) -> dict:
        if self._connectors.get(connector_id, {}).get("status") != "connected":
            return {"ok": False, "reason": "Not connected"}
        event = {"connector": connector_id, "type": event_type, "payload": payload, "sent_at": datetime.now(timezone.utc).isoformat()}
        self._events.append(event)
        return {"ok": True, "event": event}

    def get_events(self, connector_id: Optional[str] = None, limit: int = 50) -> list[dict]:
        result = self._events
        if connector_id:
            result = [e for e in result if e["connector"] == connector_id]
        return list(reversed(result[-limit:]))


notification_router = NotificationRouter()
message_digest = MessageDigest()
batch_processor = BatchProcessor()
external_connector = ExternalConnector()
