"""DASH AI Orchestration Pipeline.

The orchestrator is the central nervous system of DASH. It routes every user
request through the full cognitive pipeline:

    User → Chat → Brain → Executive → Planner → Skill → Tool → Result → Memory → User

This package provides:
- pipeline: The main orchestration pipeline
- decision_engine: Decides which path to take (direct answer, tool, memory, RAG, etc.)
- execution_graph: DAG-based task execution with dependency resolution
- tool_chain: Chains multiple tools together with output passing
- retry_manager: Retry logic with exponential backoff and fallback strategies
"""

from __future__ import annotations

from .master_orchestrator import (
    AgentRole,
    MasterOrchestrator,
    OrchestrationResult,
    OrchestratorEvent,
    OrchestratorTask,
    get_master_orchestrator,
)

__all__ = [
    "AgentRole",
    "MasterOrchestrator",
    "OrchestrationResult",
    "OrchestratorEvent",
    "OrchestratorTask",
    "get_master_orchestrator",
]
