"""Core Systems - Unified infrastructure for DASH AI OS."""

from dash_backend.core.global_context import get_global_context, GlobalAIContext
from dash_backend.core.event_bus import get_event_bus, EventBus, EventType, Event, event_handler
from dash_backend.core.task_executor import get_task_executor, UnifiedTaskExecutor, TaskRequest, TaskResult, TaskPriority, TaskStatus
from dash_backend.core.session_manager import get_session_manager, SessionManager, SessionState
from dash_backend.core.service_manager import get_service_manager, ServiceManager, ServiceHealth, ServiceStatus

__all__ = [
    # Global Context
    "get_global_context",
    "GlobalAIContext",
    # Event Bus
    "get_event_bus",
    "EventBus",
    "EventType",
    "Event",
    "event_handler",
    # Task Executor
    "get_task_executor",
    "UnifiedTaskExecutor",
    "TaskRequest",
    "TaskResult",
    "TaskPriority",
    "TaskStatus",
    # Session Manager
    "get_session_manager",
    "SessionManager",
    "SessionState",
    # Service Manager
    "get_service_manager",
    "ServiceManager",
    "ServiceHealth",
    "ServiceStatus",
]
