"""ORM models for the DASH backend.

Importing this package registers every model on `Base.metadata`,
which is required both for SQLAlchemy relationship string
resolution (e.g. `Mapped["Conversation"]`) and for Alembic
autogenerate to see the full schema.
"""

from dash_backend.db.models.api_key import APIKey
from dash_backend.db.models.conversation import Conversation
from dash_backend.db.models.conversation_summary import ConversationSummary
from dash_backend.db.models.device import Device, DeviceType
from dash_backend.db.models.memory import Memory
from dash_backend.automation.models import Automation, AutomationExecution  # register automation models with Base
from dash_backend.agents.models import Agent  # register agent model with Base
from dash_backend.db.models.message import Message, MessageRole
from dash_backend.db.models.notification import Notification, NotificationType
from dash_backend.db.models.plugin import Plugin
from dash_backend.db.models.session import Session
from dash_backend.db.models.task import Task, TaskStatus
from dash_backend.db.models.user import User
from dash_backend.db.models.refresh_tokens import RefreshToken


__all__ = [
    "APIKey",
    "Conversation",
    "ConversationSummary",
    "Device",
    "DeviceType",
    "Memory",
    "Message",
    "MessageRole",
    "Notification",
    "NotificationType",
    "Plugin",
    "Session",
    "Task",
    "TaskStatus",
    "User",
    "RefreshToken",
]