"""Unified Event Bus - Central communication system for all modules."""

from typing import Dict, List, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class EventType(str, Enum):
    # Voice events
    VOICE_STARTED = "voice_started"
    VOICE_STOPPED = "voice_stopped"
    VOICE_INTERRUPTED = "voice_interrupted"
    VOICE_ERROR = "voice_error"
    
    # Task events
    TASK_STARTED = "task_started"
    TASK_FINISHED = "task_finished"
    TASK_FAILED = "task_failed"
    TASK_PROGRESS = "task_progress"
    
    # Desktop events
    WINDOW_CHANGED = "window_changed"
    APPLICATION_CHANGED = "application_changed"
    CLIPBOARD_UPDATED = "clipboard_updated"
    SCREENSHOT_TAKEN = "screenshot_taken"
    
    # Device events
    DEVICE_CONNECTED = "device_connected"
    DEVICE_DISCONNECTED = "device_disconnected"
    DEVICE_OFFLINE = "device_offline"
    ANDROID_CONNECTED = "android_connected"
    DESKTOP_CONNECTED = "desktop_connected"
    
    # Memory events
    MEMORY_UPDATED = "memory_updated"
    MEMORY_RETRIEVED = "memory_retrieved"
    MEMORY_DELETED = "memory_deleted"
    
    # Skill events
    SKILL_LOADED = "skill_loaded"
    SKILL_UNLOADED = "skill_unloaded"
    SKILL_EXECUTED = "skill_executed"
    SKILL_FAILED = "skill_failed"
    
    # Model events
    MODEL_CHANGED = "model_changed"
    MODEL_LOADED = "model_loaded"
    MODEL_UNLOADED = "model_unloaded"
    
    # Notification events
    NOTIFICATION_RECEIVED = "notification_received"
    NOTIFICATION_DISMISSED = "notification_dismissed"
    NOTIFICATION_CLICKED = "notification_clicked"
    
    # Network events
    INTERNET_AVAILABLE = "internet_available"
    INTERNET_UNAVAILABLE = "internet_unavailable"
    
    # Service events
    SERVICE_STARTED = "service_started"
    SERVICE_STOPPED = "service_stopped"
    SERVICE_FAILED = "service_failed"
    SERVICE_RESTARTED = "service_restarted"
    
    # Conversation events
    CONVERSATION_STARTED = "conversation_started"
    CONVERSATION_ENDED = "conversation_ended"
    MESSAGE_RECEIVED = "message_received"
    MESSAGE_SENT = "message_sent"
    
    # Planning events
    PLANNING_STARTED = "planning_started"
    PLANNING_COMPLETED = "planning_completed"
    PLAN_EXECUTED = "plan_executed"
    PLAN_FAILED = "plan_failed"
    
    # File events
    FILE_SELECTED = "file_selected"
    FILE_OPENED = "file_opened"
    FILE_SAVED = "file_saved"
    FILE_DELETED = "file_deleted"
    
    # Automation events
    AUTOMATION_STARTED = "automation_started"
    AUTOMATION_COMPLETED = "automation_completed"
    AUTOMATION_FAILED = "automation_failed"
    
    # System events
    SYSTEM_SHUTDOWN = "system_shutdown"
    SYSTEM_STARTUP = "system_startup"
    SESSION_SAVED = "session_saved"
    SESSION_RESTORED = "session_restored"


@dataclass
class Event:
    type: EventType
    data: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    source: str = ""
    correlation_id: Optional[str] = None


class EventBus:
    """Central event bus for all DASH modules."""
    
    def __init__(self):
        self._subscribers: Dict[EventType, List[Callable]] = {}
        self._event_history: List[Event] = []
        self._max_history = 1000
        self._lock = asyncio.Lock()
        
        logger.info("Event Bus initialized")
    
    async def subscribe(self, event_type: EventType, callback: Callable) -> None:
        """Subscribe to an event type."""
        async with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)
            logger.debug(f"Subscribed to {event_type}")
    
    async def unsubscribe(self, event_type: EventType, callback: Callable) -> None:
        """Unsubscribe from an event type."""
        async with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb != callback
                ]
                logger.debug(f"Unsubscribed from {event_type}")
    
    async def publish(self, event: Event) -> None:
        """Publish an event to all subscribers."""
        async with self._lock:
            # Add to history
            self._event_history.append(event)
            if len(self._event_history) > self._max_history:
                self._event_history.pop(0)
            
            # Get subscribers
            subscribers = self._subscribers.get(event.type, []).copy()
        
        logger.debug(f"Publishing event: {event.type} from {event.source}")
        
        # Notify subscribers asynchronously
        tasks = []
        for callback in subscribers:
            try:
                task = asyncio.create_task(self._notify_subscriber(callback, event))
                tasks.append(task)
            except Exception as e:
                logger.error(f"Error creating task for subscriber: {e}")
        
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
    
    async def _notify_subscriber(self, callback: Callable, event: Event) -> None:
        """Notify a single subscriber."""
        try:
            if asyncio.iscoroutinefunction(callback):
                await callback(event)
            else:
                callback(event)
        except Exception as e:
            logger.error(f"Error in subscriber callback: {e}")
    
    async def publish_sync(self, event_type: EventType, data: Dict[str, Any], source: str = "") -> None:
        """Publish event synchronously (convenience method)."""
        event = Event(type=event_type, data=data, source=source)
        await self.publish(event)
    
    async def get_history(self, event_type: Optional[EventType] = None, limit: int = 100) -> List[Event]:
        """Get event history."""
        async with self._lock:
            if event_type:
                events = [e for e in self._event_history if e.type == event_type]
            else:
                events = self._event_history.copy()
            
            return events[-limit:]
    
    async def clear_history(self) -> None:
        """Clear event history."""
        async with self._lock:
            self._event_history = []
            logger.info("Event history cleared")
    
    async def get_subscriber_count(self, event_type: EventType) -> int:
        """Get number of subscribers for an event type."""
        async with self._lock:
            return len(self._subscribers.get(event_type, []))
    
    async def get_all_event_types(self) -> List[EventType]:
        """Get all event types with subscribers."""
        async with self._lock:
            return list(self._subscribers.keys())


# Singleton instance
_event_bus: Optional[EventBus] = None


def get_event_bus() -> EventBus:
    """Get or create event bus singleton."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


# Decorator for event handlers
def event_handler(event_type: EventType):
    """Decorator to register a function as an event handler."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            bus = get_event_bus()
            await bus.subscribe(event_type, func)
            return func
        return wrapper
    return decorator
