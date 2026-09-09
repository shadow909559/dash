# -*- coding: utf-8 -*-
"""External Service Integrations — Slack, Telegram, GitHub, Notion, Discord, Twitter/X."""

import logging
import secrets
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class IntegrationConfig:
    """Configuration for an external service integration."""
    service: str
    api_key: str = ""
    webhook_url: str = ""
    bot_token: str = ""
    workspace_id: str = ""
    channel_id: str = ""
    enabled: bool = False
    configured_at: str = ""
    last_sync: str = ""


@dataclass
class IntegrationMessage:
    """Message sent/received via integration."""
    id: str
    service: str
    direction: str  # "inbound" or "outbound"
    content: str
    author: str = ""
    channel: str = ""
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: dict = field(default_factory=dict)


class IntegrationService:
    """Manages external service integrations."""

    SUPPORTED_SERVICES = [
        "slack", "telegram", "github", "notion",
        "discord", "twitter", "linkedin", "email_smtp",
    ]

    def __init__(self):
        self._configs: dict[str, IntegrationConfig] = {}
        self._messages: dict[str, list[IntegrationMessage]] = {}
        self._webhooks: dict[str, dict] = {}  # webhook_id -> config
        self._events: list[dict] = []

    def configure(self, service: str, **kwargs) -> dict:
        """Configure an external service integration."""
        if service not in self.SUPPORTED_SERVICES:
            raise ValueError(f"Unsupported service: {service}. Supported: {self.SUPPORTED_SERVICES}")

        config = IntegrationConfig(
            service=service,
            api_key=kwargs.get("api_key", ""),
            webhook_url=kwargs.get("webhook_url", ""),
            bot_token=kwargs.get("bot_token", ""),
            workspace_id=kwargs.get("workspace_id", ""),
            channel_id=kwargs.get("channel_id", ""),
            enabled=kwargs.get("enabled", True),
            configured_at=datetime.now(timezone.utc).isoformat(),
        )
        self._configs[service] = config
        logger.info("Integration configured: %s", service)
        return {"status": "configured", "service": service}

    def send_message(self, service: str, channel: str, content: str, author: str = "DASH") -> dict:
        """Send a message via an external service."""
        config = self._configs.get(service)
        if not config or not config.enabled:
            raise ValueError(f"Service not configured or disabled: {service}")

        msg = IntegrationMessage(
            id=secrets.token_hex(8),
            service=service,
            direction="outbound",
            content=content,
            author=author,
            channel=channel,
        )
        self._messages.setdefault(service, []).append(msg)

        return {
            "status": "sent",
            "message_id": msg.id,
            "service": service,
            "channel": channel,
            "timestamp": msg.timestamp,
        }

    def receive_message(self, service: str, channel: str, content: str, author: str, metadata: dict = None) -> dict:
        """Receive an inbound message from external service."""
        msg = IntegrationMessage(
            id=secrets.token_hex(8),
            service=service,
            direction="inbound",
            content=content,
            author=author,
            channel=channel,
            metadata=metadata or {},
        )
        self._messages.setdefault(service, []).append(msg)

        # Record event
        self._events.append({
            "type": "message_received",
            "service": service,
            "channel": channel,
            "author": author,
            "timestamp": msg.timestamp,
        })

        return {
            "status": "received",
            "message_id": msg.id,
            "service": service,
            "channel": channel,
        }

    def get_messages(self, service: str, channel: str = None, limit: int = 50) -> list[dict]:
        """Get messages for a service."""
        msgs = self._messages.get(service, [])
        if channel:
            msgs = [m for m in msgs if m.channel == channel]
        return [
            {
                "id": m.id,
                "direction": m.direction,
                "content": m.content,
                "author": m.author,
                "channel": m.channel,
                "timestamp": m.timestamp,
            }
            for m in msgs[-limit:]
        ]

    def create_webhook(self, service: str, url: str, events: list[str]) -> dict:
        """Register a webhook for receiving events."""
        webhook_id = f"wh_{secrets.token_hex(8)}"
        self._webhooks[webhook_id] = {
            "id": webhook_id,
            "service": service,
            "url": url,
            "events": events,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "active": True,
        }
        return {"webhook_id": webhook_id, "status": "created", "service": service, "events": events}

    def get_webhooks(self, service: str = None) -> list[dict]:
        """Get registered webhooks."""
        whs = list(self._webhooks.values())
        if service:
            whs = [w for w in whs if w["service"] == service]
        return whs

    def delete_webhook(self, webhook_id: str) -> dict:
        """Delete a webhook."""
        if webhook_id in self._webhooks:
            del self._webhooks[webhook_id]
            return {"status": "deleted", "webhook_id": webhook_id}
        return {"status": "not_found", "webhook_id": webhook_id}

    def get_integrations_status(self) -> list[dict]:
        """Get status of all configured integrations."""
        result = []
        for service in self.SUPPORTED_SERVICES:
            config = self._configs.get(service)
            msg_count = len(self._messages.get(service, []))
            result.append({
                "service": service,
                "configured": config is not None,
                "enabled": config.enabled if config else False,
                "messages": msg_count,
                "last_sync": config.last_sync if config else "",
            })
        return result

    def get_events(self, limit: int = 100) -> list[dict]:
        """Get recent integration events."""
        return self._events[-limit:]


# Singleton
_integration_service: Optional[IntegrationService] = None


def get_integration_service() -> IntegrationService:
    global _integration_service
    if _integration_service is None:
        _integration_service = IntegrationService()
    return _integration_service
