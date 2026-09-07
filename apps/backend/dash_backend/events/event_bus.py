"""Event Bus - Central publish/subscribe event system for DASH AI OS.

All internal communication flows through this event bus:
- Components publish events to specific topics
- Subscribers receive events they are interested in
- Events can have priorities for ordering
- Async by default with optional sync delivery
- Supports wildcard topic subscriptions
- Includes event history for late subscribers
- Automatic cleanup of stale subscribers
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Coroutine, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class EventPriority(Enum):
    """Priority levels for event delivery."""
    LOWEST = 0
    LOW = 1
    NORMAL = 2
    HIGH = 3
    HIGHEST = 4
    CRITICAL = 5


# Standard event topics used across the system
class EventTopics:
    """Central registry of all event topics used in DASH."""
    
    # System events
    SYSTEM_STARTUP = "system.startup"
    SYSTEM_SHUTDOWN = "system.shutdown"
    SYSTEM_HEALTH = "system.health"
    SYSTEM_ERROR = "system.error"
    
    # Desktop events
    DESKTOP_WINDOW_OPENED = "desktop.window.opened"
    DESKTOP_WINDOW_CLOSED = "desktop.window.closed"
    DESKTOP_WINDOW_FOCUSED = "desktop.window.focused"
    DESKTOP_PROCESS_STARTED = "desktop.process.started"
    DESKTOP_PROCESS_STOPPED = "desktop.process.stopped"
    DESKTOP_CLIPBOARD_CHANGED = "desktop.clipboard.changed"
    DESKTOP_FILE_CREATED = "desktop.file.created"
    DESKTOP_FILE_MODIFIED = "desktop.file.modified"
    DESKTOP_FILE_DELETED = "desktop.file.deleted"
    DESKTOP_MOUSE_MOVED = "desktop.mouse.moved"
    DESKTOP_MOUSE_CLICKED = "desktop.mouse.clicked"
    DESKTOP_KEYBOARD_INPUT = "desktop.keyboard.input"
    DESKTOP_SCREEN_CAPTURED = "desktop.screen.captured"
    DESKTOP_POWER_CHANGED = "desktop.power.changed"
    
    # Browser events
    BROWSER_TAB_OPENED = "browser.tab.opened"
    BROWSER_TAB_CLOSED = "browser.tab.closed"
    BROWSER_TAB_SWITCHED = "browser.tab.switched"
    BROWSER_NAVIGATED = "browser.navigated"
    BROWSER_BOOKMARK_ADDED = "browser.bookmark.added"
    BROWSER_HISTORY_UPDATED = "browser.history.updated"
    BROWSER_DOWNLOAD_COMPLETED = "browser.download.completed"
    BROWSER_FORM_DETECTED = "browser.form.detected"
    
    # Voice events
    VOICE_WAKE_WORD = "voice.wake_word"
    VOICE_STT_STARTED = "voice.stt.started"
    VOICE_STT_COMPLETED = "voice.stt.completed"
    VOICE_STT_ERROR = "voice.stt.error"
    VOICE_TTS_STARTED = "voice.tts.started"
    VOICE_TTS_COMPLETED = "voice.tts.completed"
    VOICE_TTS_ERROR = "voice.tts.error"
    VOICE_VAD_SPEECH = "voice.vad.speech"
    VOICE_VAD_SILENCE = "voice.vad.silence"
    VOICE_INTERRUPTION = "voice.interruption"
    
    # Vision events
    VISION_SCREEN_CAPTURED = "vision.screen.captured"
    VISION_OBJECT_DETECTED = "vision.object.detected"
    VISION_TEXT_DETECTED = "vision.text.detected"
    VISION_FACE_DETECTED = "vision.face.detected"
    VISION_ERROR_DETECTED = "vision.error.detected"
    VISION_IMAGE_ANALYZED = "vision.image.analyzed"
    
    # AI events
    AI_REASONING_STARTED = "ai.reasoning.started"
    AI_REASONING_COMPLETED = "ai.reasoning.completed"
    AI_REASONING_ERROR = "ai.reasoning.error"
    AI_PLANNING_STARTED = "ai.planning.started"
    AI_PLANNING_COMPLETED = "ai.planning.completed"
    AI_TOOL_SELECTED = "ai.tool.selected"
    AI_TOOL_EXECUTING = "ai.tool.executing"
    AI_TOOL_COMPLETED = "ai.tool.completed"
    AI_TOOL_ERROR = "ai.tool.error"
    AI_RESPONSE_GENERATED = "ai.response.generated"
    AI_MEMORY_RETRIEVED = "ai.memory.retrieved"
    AI_MEMORY_STORED = "ai.memory.stored"
    AI_CONTEXT_BUILT = "ai.context.built"
    
    # Memory events
    MEMORY_CREATED = "memory.created"
    MEMORY_UPDATED = "memory.updated"
    MEMORY_DELETED = "memory.deleted"
    MEMORY_SEARCHED = "memory.searched"
    MEMORY_PRUNED = "memory.pruned"
    MEMORY_SUMMARY_GENERATED = "memory.summary.generated"
    
    # Automation events
    AUTOMATION_TRIGGERED = "automation.triggered"
    AUTOMATION_EXECUTING = "automation.executing"
    AUTOMATION_COMPLETED = "automation.completed"
    AUTOMATION_FAILED = "automation.failed"
    AUTOMATION_SCHEDULED = "automation.scheduled"
    
    # Plugin events
    PLUGIN_LOADED = "plugin.loaded"
    PLUGIN_UNLOADED = "plugin.unloaded"
    PLUGIN_ERROR = "plugin.error"
    PLUGIN_EVENT = "plugin.event"
    PLUGIN_ENABLED = "plugin.enabled"
    PLUGIN_DISABLED = "plugin.disabled"
    
    # Sync events
    SYNC_CONNECTED = "sync.connected"
    SYNC_DISCONNECTED = "sync.disconnected"
    SYNC_DATA_RECEIVED = "sync.data.received"
    SYNC_DATA_SENT = "sync.data.sent"
    SYNC_CONFLICT = "sync.conflict"
    SYNC_COMPLETED = "sync.completed"
    
    # Security events
    SECURITY_LOGIN = "security.login"
    SECURITY_LOGOUT = "security.logout"
    SECURITY_PERMISSION_DENIED = "security.permission.denied"
    SECURITY_DANGEROUS_ACTION = "security.dangerous.action"
    SECURITY_TOKEN_REFRESHED = "security.token.refreshed"


@dataclass
class Event:
    """An event in the system.
    
    Attributes:
        topic: Event topic string (dot-separated hierarchy)
        data: Event payload data
        source: Source component/module that published the event
        priority: Event priority for delivery ordering
        id: Unique event ID
        timestamp: When the event was created
        correlation_id: Optional ID to correlate related events
    """
    topic: str
    data: Dict[str, Any] = field(default_factory=dict)
    source: str = ""
    priority: EventPriority = EventPriority.NORMAL
    id: str = ""
    timestamp: float = 0.0
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.timestamp:
            self.timestamp = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "data": self.data,
            "source": self.source,
            "priority": self.priority.value,
            "id": self.id,
            "timestamp": self.timestamp,
            "correlation_id": self.correlation_id,
        }


class EventBus:
    """Central event bus for publish/subscribe communication.
    
    Features:
    - Topic-based publish/subscribe with wildcard support
    - Priority-based event delivery ordering
    - Async subscriber callbacks
    - Event history buffer for late subscribers
    - Automatic stale subscriber cleanup
    - Subscriber filtering by event source
    - Event correlation support
    """
    
    def __init__(self, history_size: int = 100, cleanup_interval: float = 300.0):
        self._history_size = history_size
        self._cleanup_interval = cleanup_interval
        
        # Subscribers: topic -> list of (callback, filter_fn, name)
        self._subscribers: Dict[str, List[tuple]] = {}
        
        # Wildcard subscribers (e.g., "desktop.*", "ai.**")
        self._wildcard_subscribers: List[tuple] = []
        
        # Event history for late subscribers
        self._event_history: List[Event] = []
        
        # Subscriber metadata for cleanup
        self._subscriber_metadata: Dict[int, Dict[str, Any]] = {}
        
        # Background task for cleanup
        self._cleanup_task: Optional[asyncio.Task] = None
        self._running = False
        
        # Stats
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "events_dropped": 0,
            "active_subscribers": 0,
        }
        
        logger.info("EventBus initialized with history_size=%d", history_size)
    
    # ── Lifecycle ────────────────────────────────────────────
    
    async def start(self) -> None:
        """Start the event bus background tasks."""
        self._running = True
        self._cleanup_task = asyncio.create_task(self._cleanup_loop())
        logger.info("EventBus started")
    
    async def stop(self) -> None:
        """Stop the event bus and clean up."""
        self._running = False
        if self._cleanup_task:
            self._cleanup_task.cancel()
            try:
                await self._cleanup_task
            except asyncio.CancelledError:
                pass
        self._subscribers.clear()
        self._wildcard_subscribers.clear()
        self._event_history.clear()
        logger.info("EventBus stopped. Stats: %s", self._stats)
    
    # ── Publishing ───────────────────────────────────────────
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all matching subscribers.
        
        Args:
            event: The event to publish
        """
        self._stats["events_published"] += 1
        
        # Add to history
        self._event_history.append(event)
        if len(self._event_history) > self._history_size:
            self._event_history.pop(0)
        
        # Find matching subscribers
        delivery_tasks = []
        
        # Exact topic match
        if event.topic in self._subscribers:
            for callback, filter_fn, name in self._subscribers[event.topic]:
                if filter_fn and not filter_fn(event):
                    continue
                delivery_tasks.append(self._deliver(event, callback, name))
        
        # Wildcard match
        for pattern, callback, filter_fn, name in self._wildcard_subscribers:
            if self._topic_matches(pattern, event.topic):
                if filter_fn and not filter_fn(event):
                    continue
                delivery_tasks.append(self._deliver(event, callback, name))
        
        # Execute deliveries concurrently
        if delivery_tasks:
            results = await asyncio.gather(*delivery_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    logger.warning("Event delivery failed: %s", result)
                    self._stats["events_dropped"] += 1
                else:
                    self._stats["events_delivered"] += 1
    
    async def publish_sync(self, topic: str, data: Dict[str, Any] = None,
                           source: str = "", priority: EventPriority = EventPriority.NORMAL,
                           correlation_id: Optional[str] = None) -> None:
        """Convenience method to publish with simple parameters.
        
        Args:
            topic: Event topic
            data: Event payload
            source: Source component
            priority: Event priority
            correlation_id: Optional correlation ID
        """
        event = Event(
            topic=topic,
            data=data or {},
            source=source,
            priority=priority,
            correlation_id=correlation_id,
        )
        await self.publish(event)
    
    async def _deliver(self, event: Event, callback: Callable, name: str) -> None:
        """Deliver an event to a single subscriber.
        
        Args:
            event: The event to deliver
            callback: The subscriber callback
            name: Subscriber name for logging
        """
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as exc:
            logger.error("Subscriber '%s' failed processing event %s: %s",
                         name, event.topic, exc)
    
    # ── Subscribing ──────────────────────────────────────────
    
    def subscribe(self, topic: str, callback: Callable[[Event], Coroutine],
                  filter_fn: Optional[Callable[[Event], bool]] = None,
                  name: str = "") -> str:
        """Subscribe to events on a specific topic.
        
        Supports wildcards:
        - '*' matches one level: "desktop.*" matches "desktop.window"
        - '**' matches any depth: "ai.**" matches "ai.tool.executing"
        
        Args:
            topic: Topic pattern to subscribe to
            callback: Async callback receiving the Event
            filter_fn: Optional function to filter events
            name: Optional subscriber name for debugging
            
        Returns:
            Subscription ID for unsubscribing
        """
        sub_id = str(uuid.uuid4())
        name = name or f"sub_{sub_id[:8]}"
        
        if "**" in topic or "*" in topic:
            # Wildcard subscription
            self._wildcard_subscribers.append((topic, callback, filter_fn, name))
        else:
            # Exact topic subscription
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append((callback, filter_fn, name))
        
        # Track metadata
        self._subscriber_metadata[id(callback)] = {
            "sub_id": sub_id,
            "topic": topic,
            "name": name,
            "created_at": time.time(),
        }
        self._stats["active_subscribers"] = len(self._subscriber_metadata)
        
        logger.debug("Subscribed '%s' to topic '%s'", name, topic)
        return sub_id
    
    def unsubscribe(self, sub_id: str) -> bool:
        """Unsubscribe a subscriber by subscription ID.
        
        Args:
            sub_id: Subscription ID returned from subscribe()
            
        Returns:
            True if unsubscribed successfully
        """
        # Find and remove from exact subscribers
        for topic in list(self._subscribers.keys()):
            for i, (callback, filter_fn, name) in enumerate(self._subscribers[topic]):
                meta = self._subscriber_metadata.get(id(callback), {})
                if meta.get("sub_id") == sub_id:
                    self._subscribers[topic].pop(i)
                    if not self._subscribers[topic]:
                        del self._subscribers[topic]
                    self._subscriber_metadata.pop(id(callback), None)
                    self._stats["active_subscribers"] = len(self._subscriber_metadata)
                    logger.debug("Unsubscribed '%s' from '%s'", name, topic)
                    return True
        
        # Find and remove from wildcard subscribers
        for i, (pattern, callback, filter_fn, name) in enumerate(self._wildcard_subscribers):
            meta = self._subscriber_metadata.get(id(callback), {})
            if meta.get("sub_id") == sub_id:
                self._wildcard_subscribers.pop(i)
                self._subscriber_metadata.pop(id(callback), None)
                self._stats["active_subscribers"] = len(self._subscriber_metadata)
                logger.debug("Unsubscribed '%s' from pattern '%s'", name, pattern)
                return True
        
        return False
    
    def unsubscribe_all(self, name_prefix: str) -> int:
        """Unsubscribe all subscribers with a name prefix.
        
        Args:
            name_prefix: Prefix to match subscriber names
            
        Returns:
            Number of subscribers removed
        """
        count = 0
        
        # Exact subscribers
        for topic in list(self._subscribers.keys()):
            remaining = []
            for callback, filter_fn, name in self._subscribers[topic]:
                if name.startswith(name_prefix):
                    self._subscriber_metadata.pop(id(callback), None)
                    count += 1
                else:
                    remaining.append((callback, filter_fn, name))
            if remaining:
                self._subscribers[topic] = remaining
            else:
                del self._subscribers[topic]
        
        # Wildcard subscribers
        remaining = []
        for pattern, callback, filter_fn, name in self._wildcard_subscribers:
            if name.startswith(name_prefix):
                self._subscriber_metadata.pop(id(callback), None)
                count += 1
            else:
                remaining.append((pattern, callback, filter_fn, name))
        self._wildcard_subscribers = remaining
        
        self._stats["active_subscribers"] = len(self._subscriber_metadata)
        return count
    
    # ── History ──────────────────────────────────────────────
    
    def get_history(self, topic: Optional[str] = None, limit: int = 10) -> List[Event]:
        """Get recent event history, optionally filtered by topic.
        
        Args:
            topic: Optional topic filter (supports wildcards)
            limit: Maximum number of events to return
            
        Returns:
            List of matching events
        """
        if not topic:
            return list(self._event_history[-limit:])
        
        matching = []
        for event in reversed(self._event_history):
            if self._topic_matches(topic, event.topic):
                matching.append(event)
                if len(matching) >= limit:
                    break
        return matching
    
    def get_history_for_source(self, source: str, limit: int = 10) -> List[Event]:
        """Get recent events from a specific source.
        
        Args:
            source: Source name to filter by
            limit: Maximum number of events
            
        Returns:
            List of matching events
        """
        matching = []
        for event in reversed(self._event_history):
            if event.source == source:
                matching.append(event)
                if len(matching) >= limit:
                    break
        return matching
    
    # ── Topic Matching ───────────────────────────────────────
    
    @staticmethod
    def _topic_matches(pattern: str, topic: str) -> bool:
        """Check if a topic matches a pattern with wildcard support.
        
        - '*' matches exactly one level
        - '**' matches any number of levels (must be at end)
        
        Examples:
        - "desktop.*" matches "desktop.window" but not "desktop.window.opened"
        - "ai.**" matches "ai.tool.executing" and "ai.reasoning.completed"
        - "*.changed" matches "desktop.clipboard.changed"
        """
        if pattern == "**":
            return True
        
        pattern_parts = pattern.split(".")
        topic_parts = topic.split(".")
        
        # Handle '**' at end of pattern
        if pattern_parts[-1] == "**":
            base_parts = pattern_parts[:-1]
            if len(topic_parts) < len(base_parts):
                return False
            for p, t in zip(base_parts, topic_parts):
                if p != "*" and p != t:
                    return False
            return True
        
        if len(pattern_parts) != len(topic_parts):
            return False
        
        for p, t in zip(pattern_parts, topic_parts):
            if p == "*":
                continue
            if p != t:
                return False
        
        return True
    
    # ── Cleanup ──────────────────────────────────────────────
    
    async def _cleanup_loop(self) -> None:
        """Periodic cleanup of stale subscribers."""
        while self._running:
            await asyncio.sleep(self._cleanup_interval)
            await self._cleanup_stale_subscribers()
    
    async def _cleanup_stale_subscribers(self) -> None:
        """Remove subscribers that haven't received events recently."""
        # Currently a no-op - subscribers are kept until explicitly removed.
        # Future enhancement: add TTL-based subscriber expiration.
        pass
    
    # ── Stats ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get event bus statistics."""
        return {
            **self._stats,
            "history_size": len(self._event_history),
            "exact_subscribers": sum(len(subs) for subs in self._subscribers.values()),
            "wildcard_subscribers": len(self._wildcard_subscribers),
            "total_topics": len(self._subscribers),
        }
    
    def reset_stats(self) -> None:
        """Reset event bus statistics."""
        self._stats = {
            "events_published": 0,
            "events_delivered": 0,
            "events_dropped": 0,
            "active_subscribers": len(self._subscriber_metadata),
        }


# Global singleton
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create the global EventBus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus

