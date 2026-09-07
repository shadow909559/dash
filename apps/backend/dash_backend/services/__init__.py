"""DASH backend services package.

Aggregates all service modules for safe, unified import.
"""

from __future__ import annotations

# AI Execution OS
from dash_backend.services.ai_os.executor import AIExecutor, get_executor, ExecutionResult

# Context management
from dash_backend.services.ai_os.context_manager import ContextManager, get_context_manager

# Command parsing
from dash_backend.services.ai_os.command_parser import CommandParser, get_command_parser

# Planning
from dash_backend.services.ai_os.planner import PlannerEngine, get_planner, Plan, PlanStep

# Permission & command services
from dash_backend.services.permissions import PermissionService, get_permission_service
from dash_backend.services.command.service import CommandService, get_command_service
from dash_backend.services.command.models import CommandRequest, CommandResult, CommandStatus, CommandCategory
from dash_backend.services.command.queue import CommandQueue

# AI Providers
from dash_backend.services.ai_providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderConfig,
    ProviderHealth,
)
from dash_backend.services.ai_providers.provider_manager import ProviderManager, get_provider_manager

__all__ = [
    "AIExecutor",
    "ExecutionResult",
    "get_executor",
    "ContextManager",
    "get_context_manager",
    "CommandParser",
    "get_command_parser",
    "PlannerEngine",
    "get_planner",
    "Plan",
    "PlanStep",
    "PermissionService",
    "get_permission_service",
    "CommandService",
    "get_command_service",
    "CommandRequest",
    "CommandResult",
    "CommandStatus",
    "CommandCategory",
    "CommandQueue",
    "AIProvider",
    "CompletionRequest",
    "CompletionResponse",
    "ProviderConfig",
    "ProviderHealth",
    "ProviderManager",
    "get_provider_manager",
]
