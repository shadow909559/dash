"""Intelligence Layer - Brain of DASH AI OS.

This module contains all intelligence services:
- Agent System: Multi-agent orchestration
- Skill Engine: Skill registration and execution
- Memory System: Short and long-term memory
- Context Manager: Context window management
- Reasoning Engine: Chain-of-thought reasoning
- Planner: Task decomposition and planning
- Conversation Manager: Conversation state and history
- Tool Selection: Tool matching and execution
- LLM Router: Model selection and routing
- Streaming Service: Token streaming with interrupt
- Plugin Manager: Dynamic plugin loading
- Workflow Engine: Task automation
- Task Queue: Task scheduling and retry
- Caching Layer: Result caching
- Offline Mode: Offline functionality
"""

from dash_backend.intelligence.agent_system import AgentSystem, Agent, AgentType, AgentState, AgentMessage
from dash_backend.intelligence.skill_engine import SkillEngine, Skill, SkillParameter, SkillDependency, SkillStatus, SkillExecutionResult
from dash_backend.intelligence.memory_service import MemoryService, MemoryEntry, MemoryType, MemoryImportance, ShortTermMemory, MemorySearchResult
from dash_backend.intelligence.context_manager import ContextManager, ContextItem, ContextWindow, ContextPriority, RetentionStrategy
from dash_backend.intelligence.reasoning_engine import ReasoningEngine, ReasoningStep, ReasoningContext, ReasoningResult, ReasoningStepType
from dash_backend.intelligence.planner import Planner, Plan, Task, PlanStatus, TaskStatus, PlanExecutionResult
from dash_backend.intelligence.conversation_manager import ConversationManager, Conversation, Message, ConversationState, MessageRole, ConversationSummary
from dash_backend.intelligence.tool_selector import ToolSelector, Tool, ToolParameter, ToolExecution, ToolStatus, ToolMatch, ExecutionStatus
from dash_backend.intelligence.llm_router import LLMRouter, ModelInfo, LLMRequest, LLMResponse, Provider, ModelCapability, RoutingDecision
from dash_backend.intelligence.streaming_service import StreamingService, StreamChunk, StreamSession, StreamState, StreamConfig
from dash_backend.intelligence.plugin_manager import PluginManager, Plugin, PluginInfo, PluginState
from dash_backend.intelligence.workflow_engine import WorkflowEngine, Workflow, WorkflowStep, WorkflowState, StepType
from dash_backend.intelligence.task_queue import TaskQueue, Task as TaskQueueItem, TaskStatus as TaskQueueStatus, TaskPriority
from dash_backend.intelligence.caching_layer import CachingLayer, CacheEntry, CachePolicy
from dash_backend.intelligence.offline_mode import OfflineMode, OfflineAction, SyncStatus

__all__ = [
    # Agent System
    "AgentSystem",
    "Agent",
    "AgentType",
    "AgentState",
    "AgentMessage",
    # Skill Engine
    "SkillEngine",
    "Skill",
    "SkillParameter",
    "SkillDependency",
    "SkillStatus",
    "SkillExecutionResult",
    # Memory System
    "MemoryService",
    "MemoryEntry",
    "MemoryType",
    "MemoryImportance",
    "ShortTermMemory",
    "MemorySearchResult",
    # Context Manager
    "ContextManager",
    "ContextItem",
    "ContextWindow",
    "ContextPriority",
    "RetentionStrategy",
    # Reasoning Engine
    "ReasoningEngine",
    "ReasoningStep",
    "ReasoningContext",
    "ReasoningResult",
    "ReasoningStepType",
    # Planner
    "Planner",
    "Plan",
    "Task",
    "PlanStatus",
    "TaskStatus",
    "PlanExecutionResult",
    # Conversation Manager
    "ConversationManager",
    "Conversation",
    "Message",
    "ConversationState",
    "MessageRole",
    "ConversationSummary",
    # Tool Selection
    "ToolSelector",
    "Tool",
    "ToolParameter",
    "ToolExecution",
    "ToolStatus",
    "ToolMatch",
    "ExecutionStatus",
    # LLM Router
    "LLMRouter",
    "ModelInfo",
    "LLMRequest",
    "LLMResponse",
    "Provider",
    "ModelCapability",
    "RoutingDecision",
    # Streaming Service
    "StreamingService",
    "StreamChunk",
    "StreamSession",
    "StreamState",
    "StreamConfig",
    # Plugin Manager
    "PluginManager",
    "Plugin",
    "PluginInfo",
    "PluginState",
    # Workflow Engine
    "WorkflowEngine",
    "Workflow",
    "WorkflowStep",
    "WorkflowState",
    "StepType",
    # Task Queue
    "TaskQueue",
    "TaskQueueItem",
    "TaskQueueStatus",
    "TaskPriority",
    # Caching Layer
    "CachingLayer",
    "CacheEntry",
    "CachePolicy",
    # Offline Mode
    "OfflineMode",
    "OfflineAction",
    "SyncStatus",
]
