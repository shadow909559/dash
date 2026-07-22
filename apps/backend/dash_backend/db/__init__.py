"""Database utilities for the DASH backend.

Importing this package registers all models on Base.metadata,
which Alembic needs for autogenerate and migration operations.
"""

# Import all models to populate Base.metadata
from dash_backend.db.models import (  # noqa: F401
    APIKey,
    Conversation,
    ConversationSummary,
    Device,
    DeviceType,
    Memory,
    Message,
    MessageRole,
    Notification,
    NotificationType,
    Plugin,
    Session,
    Task,
    TaskStatus,
    User,
    RefreshToken,
)

# Register external models (built outside db/models/)
from dash_backend.automation.models import Automation, AutomationExecution  # noqa: F401
from dash_backend.agents.models import Agent  # noqa: F401
from dash_backend.executive.models import Goal, ExecutiveTask, ExecutionHistory, Approval  # noqa: F401
from dash_backend.rag.models import Document, DocumentChunk  # noqa: F401
