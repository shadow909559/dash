"""Plugin Event Integration - Connect plugins to the event bus."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable, Dict, List, Optional

from dash_backend.events.event_bus import get_event_bus
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class PluginEventIntegration:
    def __init__(self):
        self._event_bus = get_event_bus()
        self._subscriptions: Dict[str, List[Dict[str, Any]]] = {}
        self._plugin_topics: Dict[str, str] = {}

    async def subscribe(self, plugin_id: str, topic: str, handler: Callable) -> bool:
        topic_key = f"plugin.{plugin_id}.{topic}"
        self._event_bus.subscribe(topic, handler)
        if topic_key not in self._subscriptions:
            self._subscriptions[topic_key] = []
        self._subscriptions[topic_key].append({"plugin": plugin_id, "topic": topic, "handler": handler})
        logger.info("Plugin %s subscribed to event: %s", plugin_id, topic)
        return True

    async def unsubscribe(self, plugin_id: str, topic: str) -> bool:
        topic_key = f"plugin.{plugin_id}.{topic}"
        subs = self._subscriptions.pop(topic_key, [])
        for s in subs:
            self._event_bus.unsubscribe(topic, s["handler"])
        return True

    async def emit(self, plugin_id: str, topic: str, data: Any = None) -> None:
        await self._event_bus.publish(topic, {
            "source": f"plugin.{plugin_id}",
            "data": data,
            "timestamp": asyncio.get_event_loop().time(),
        })

    async def emit_plugin_event(self, plugin_id: str, event_type: str, data: Any = None) -> None:
        await self.emit(plugin_id, f"plugin.{plugin_id}.{event_type}", data)

    def get_subscriptions(self, plugin_id: str) -> List[Dict[str, Any]]:
        result = []
        for key, subs in self._subscriptions.items():
            for s in subs:
                if s["plugin"] == plugin_id:
                    result.append(s)
        return result

    async def unregister_plugin(self, plugin_id: str) -> None:
        keys_to_remove = []
        for key, subs in self._subscriptions.items():
            for s in subs:
                if s["plugin"] == plugin_id:
                    keys_to_remove.append(key)
                    self._event_bus.unsubscribe(s["topic"], s["handler"])
        for key in keys_to_remove:
            self._subscriptions.pop(key, None)


_plugin_event_integration: Optional[PluginEventIntegration] = None


def get_plugin_event_integration() -> PluginEventIntegration:
    global _plugin_event_integration
    if _plugin_event_integration is None:
        _plugin_event_integration = PluginEventIntegration()
    return _plugin_event_integration
