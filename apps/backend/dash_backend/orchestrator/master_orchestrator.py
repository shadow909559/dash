"""Master Orchestrator - Decomposes complex requests into agent-assigned
subtasks and runs independent agents in parallel, then merges results into a
natural response.

This is the top-level coordination layer for DASH's AI core. It integrates the
existing architecture:

    Request
      → Reasoning / Decision (what's needed)
      → TaskPlanner (decompose into dependency layers)
      → Agent assignment (coding / research / planning / desktop / browser /
        memory / execution)
      → Parallel execution (asyncio.gather within a layer)
      → Merge results (BrainService) → Natural response
      → Self-reflection (log learnings)

The orchestrator never hardcodes workflows — it reasons about the request,
decomposes it, assigns agents, and coordinates execution. It is purely additive
and plugs into the existing pipeline without recreating anything.
"""

from __future__ import annotations

import asyncio
import json
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, AsyncIterator, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class OrchestratorStatus(str, Enum):
    """Status of the master orchestration run."""
    PENDING = "pending"
    REASONING = "reasoning"
    PLANNING = "planning"
    EXECUTING = "executing"
    MERGING = "merging"
    REFLECTING = "reflecting"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class AgentRole(str, Enum):
    """The agent roles the orchestrator can assign to a subtask."""
    CODING = "coding"
    RESEARCH = "research"
    PLANNING = "planning"
    DESKTOP = "desktop"
    BROWSER = "browser"
    MEMORY = "memory"
    REASONING = "reasoning"
    EXECUTION = "execution"


@dataclass
class OrchestratorTask:
    """A single subtask assigned to an agent role."""
    id: str = ""
    name: str = ""
    description: str = ""
    role: AgentRole = AgentRole.REASONING
    dependencies: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    status: str = "pending"
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    def __post_init__(self) -> None:
        if not self.id:
            self.id = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "role": self.role.value,
            "dependencies": self.dependencies,
            "tools": self.tools,
            "status": self.status,
            "error": self.error,
        }


@dataclass
class OrchestrationResult:
    """The merged result of a master orchestration run."""
    request_id: str = ""
    goal: str = ""
    status: str = "completed"
    response: str = ""
    confidence: float = 0.0
    tasks: List[Dict[str, Any]] = field(default_factory=list)
    agent_summary: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)
    duration_ms: int = 0
    reflection: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "request_id": self.request_id,
            "goal": self.goal,
            "status": self.status,
            "response": self.response,
            "confidence": self.confidence,
            "tasks": self.tasks,
            "agent_summary": self.agent_summary,
            "errors": self.errors,
            "duration_ms": self.duration_ms,
            "reflection": self.reflection,
        }


@dataclass
class OrchestratorEvent:
    """Event emitted during orchestration for streaming to the client."""
    type: str
    data: Dict[str, Any]
    timestamp: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type,
            "data": self.data,
            "timestamp": self.timestamp or time.time(),
        }

    def to_json(self) -> str:
        """Serialize the event to a JSON string (for SSE streaming)."""
        return json.dumps(self.to_dict(), default=str)


class MasterOrchestrator:
    """Coordination layer that decomposes requests and runs agents in parallel.

    Responsibilities:
        1. Reason about the request (intent, required agents, risk).
        2. Decompose into tasks with dependency layers (TaskPlanner).
        3. Assign each task an agent role.
        4. Execute independent tasks in parallel (asyncio.gather).
        5. Merge results into a short, natural response (BrainService).
        6. Reflect and log learnings.
    """

    def __init__(self) -> None:
        self._active_runs: Dict[str, OrchestratorTask] = {}
        self._stats: Dict[str, Any] = {
            "runs_started": 0,
            "runs_completed": 0,
            "runs_failed": 0,
            "tasks_executed": 0,
            "parallel_executions": 0,
        }

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    async def run(
        self,
        request: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        memory_context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        max_tasks: int = 10,
        constraints: Optional[List[str]] = None,
    ) -> AsyncIterator[OrchestratorEvent]:
        """Run the full orchestration for a user request.

        Yields OrchestratorEvent objects for streaming (plan created, task
        started/completed, final response, etc.).
        """
        request_id = str(uuid.uuid4())
        start_time = time.time()
        self._stats["runs_started"] += 1

        logger.info("Master orchestrator run started: %s", request_id)

        try:
            # ── 1. Reason about the request ──────────────────────────────
            yield OrchestratorEvent(
                type="orchestrator.reasoning",
                data={"message": "Understanding your request..."},
            )
            intent = await self._analyze_request(request, constraints)

            # ── 2. Decompose into tasks ──────────────────────────────────
            yield OrchestratorEvent(
                type="orchestrator.planning",
                data={"message": "Breaking this into steps..."},
            )
            tasks = await self._decompose(
                request,
                user_id,
                memory_context,
                max_tasks,
                intent,
            )

            if not tasks:
                # Fall back to a single reasoning task
                tasks = [
                    OrchestratorTask(
                        name=request[:80],
                        description=request,
                        role=AgentRole.REASONING,
                    )
                ]

            # Assign agents to tasks
            for task in tasks:
                task.role = self._assign_role(task, intent)

            yield OrchestratorEvent(
                type="orchestrator.plan_created",
                data={
                    "request_id": request_id,
                    "tasks": [t.to_dict() for t in tasks],
                    "task_count": len(tasks),
                },
            )

            # ── 3. Execute in dependency layers (parallel within layer) ──
            layers = self._resolve_layers(tasks)
            yield OrchestratorEvent(
                type="orchestrator.execution_started",
                data={
                    "layers": [[t.name for t in layer] for layer in layers],
                    "layer_count": len(layers),
                },
            )

            task_map = {t.id: t for t in tasks}
            for layer_index, layer in enumerate(layers):
                yield OrchestratorEvent(
                    type="orchestrator.layer_started",
                    data={
                        "layer_index": layer_index,
                        "tasks": [t.name for t in layer],
                    },
                )

                # Run independent tasks in this layer in parallel.
                self._stats["parallel_executions"] += 1
                results = await asyncio.gather(
                    *[self._execute_task(t, user_id, conversation_id, available_tools) for t in layer],
                    return_exceptions=True,
                )

                for task, result in zip(layer, results):
                    if isinstance(result, Exception):
                        task.status = "failed"
                        task.error = str(result)
                        yield OrchestratorEvent(
                            type="orchestrator.task_failed",
                            data={
                                "task_id": task.id,
                                "task_name": task.name,
                                "error": str(result),
                            },
                        )
                    else:
                        task.status = "completed"
                        task.result = result
                        self._stats["tasks_executed"] += 1
                        yield OrchestratorEvent(
                            type="orchestrator.task_completed",
                            data={
                                "task_id": task.id,
                                "task_name": task.name,
                                "role": task.role.value,
                                "summary": self._summarize_result(result),
                            },
                        )

            # ── 4. Merge results into a natural response ────────────────
            yield OrchestratorEvent(
                type="orchestrator.merging",
                data={"message": "Putting it all together..."},
            )
            merged = await self._merge_results(request, user_id, conversation_id, tasks, memory_context)

            # ── 5. Self-reflection ───────────────────────────────────────
            reflection = await self._reflect(request, tasks, merged)

            elapsed_ms = int((time.time() - start_time) * 1000)
            result = OrchestrationResult(
                request_id=request_id,
                goal=request,
                status="completed",
                response=merged.get("response", ""),
                confidence=merged.get("confidence", 0.0),
                tasks=[t.to_dict() for t in tasks],
                agent_summary=self._build_agent_summary(tasks),
                duration_ms=elapsed_ms,
                reflection=reflection,
            )
            self._stats["runs_completed"] += 1

            yield OrchestratorEvent(
                type="orchestrator.completed",
                data=result.to_dict(),
            )

        except Exception as exc:
            logger.exception("Master orchestrator run failed: %s", request_id)
            self._stats["runs_failed"] += 1
            yield OrchestratorEvent(
                type="orchestrator.failed",
                data={
                    "request_id": request_id,
                    "error": str(exc),
                    "error_type": type(exc).__name__,
                },
            )

    # ──────────────────────────────────────────────
    # Reasoning / Intent analysis
    # ──────────────────────────────────────────────

    async def _analyze_request(
        self,
        request: str,
        constraints: Optional[List[str]],
    ) -> Dict[str, Any]:
        """Analyze the request to determine intent and required agents.

        Uses the existing DecisionEngine to classify the request, then maps
        the decision path to a set of agent roles.
        """
        from dash_backend.orchestrator.decision_engine import get_decision_engine

        decision_engine = get_decision_engine()
        path, meta = await decision_engine.decide(query=request, available_tools=[], user_id="")

        # Map decision path → primary agent roles
        roles: List[AgentRole] = []
        path_str = path.value if hasattr(path, "value") else str(path)

        if path_str in ("memory_only", "memory_and_rag", "memory_and_tool", "memory_rag_tool"):
            roles.append(AgentRole.MEMORY)
        if path_str in ("rag_only", "rag_and_tool", "memory_rag_tool"):
            roles.append(AgentRole.RESEARCH)
        if path_str in ("tool_only", "memory_and_tool", "rag_and_tool", "memory_rag_tool", "planner"):
            roles.append(AgentRole.EXECUTION)
        if path_str == "planner":
            roles.append(AgentRole.PLANNING)
        if "code" in request.lower() or "program" in request.lower() or "debug" in request.lower():
            roles.append(AgentRole.CODING)
        if "browser" in request.lower() or "web" in request.lower() or "search" in request.lower():
            roles.append(AgentRole.BROWSER)
        if "desktop" in request.lower() or "window" in request.lower() or "file" in request.lower():
            roles.append(AgentRole.DESKTOP)

        # Always include reasoning to ground the merge
        if AgentRole.REASONING not in roles:
            roles.append(AgentRole.REASONING)

        return {
            "path": path_str,
            "reason": meta.get("reason", ""),
            "confidence": meta.get("confidence", 0.0),
            "roles": [r.value for r in roles],
        }

    # ──────────────────────────────────────────────
    # Decomposition
    # ──────────────────────────────────────────────

    async def _decompose(
        self,
        request: str,
        user_id: str,
        memory_context: Optional[str],
        max_tasks: int,
        intent: Dict[str, Any],
    ) -> List[OrchestratorTask]:
        """Decompose the request into tasks using the existing TaskPlanner."""
        from dash_backend.orchestrator.task_planner import get_task_planner

        try:
            planner = get_task_planner()
            plan = await planner.create_plan(
                goal=request,
                context={
                    "domain": "general",
                    "memory_context": memory_context,
                    "user_id": user_id,
                },
                max_tasks=max_tasks,
                generate_alternatives=False,
            )

            tasks: List[OrchestratorTask] = []
            # Map plan tasks to OrchestratorTask, preserving dependencies.
            id_map: Dict[str, str] = {}
            for pt in plan.tasks.values():
                ot = OrchestratorTask(
                    name=pt.name,
                    description=pt.description,
                    dependencies=[],
                    tools=pt.required_tools,
                )
                id_map[pt.id] = ot.id
                tasks.append(ot)

            # Resolve dependency IDs (PlannedTask.id → OrchestratorTask.id)
            for pt in plan.tasks.values():
                ot = next((t for t in tasks if t.name == pt.name), None)
                if ot:
                    ot.dependencies = [id_map[d] for d in pt.dependencies if d in id_map]

            return tasks
        except Exception as exc:
            logger.warning("TaskPlanner decomposition failed: %s", exc)
            # Fallback: single reasoning task
            return [
                OrchestratorTask(
                    name=request[:80],
                    description=request,
                    role=AgentRole.REASONING,
                )
            ]

    def _assign_role(self, task: OrchestratorTask, intent: Dict[str, Any]) -> AgentRole:
        """Assign an agent role to a task based on keywords + intent."""
        # Prefer intent roles if the task matches
        text = f"{task.name} {task.description}".lower()
        roles = intent.get("roles", [])

        if any(kw in text for kw in ("code", "program", "debug", "refactor", "test", "function")):
            return AgentRole.CODING
        if any(kw in text for kw in ("research", "search", "summarize", "document", "report")):
            return AgentRole.RESEARCH
        if any(kw in text for kw in ("plan", "strategy", "organize", "schedule", "goal")):
            return AgentRole.PLANNING
        if any(kw in text for kw in ("desktop", "window", "file", "folder", "app", "process", "volume")):
            return AgentRole.DESKTOP
        if any(kw in text for kw in ("browser", "web", "internet", "website", "url", "page")):
            return AgentRole.BROWSER
        if any(kw in text for kw in ("remember", "memory", "recall", "preference", "habit")):
            return AgentRole.MEMORY
        if any(kw in text for kw in ("execute", "run", "perform", "do", "create", "delete", "send")):
            return AgentRole.EXECUTION

        # Fall back to intent roles or reasoning
        if roles:
            # Return the first role that isn't reasoning (prefer specific)
            for r in roles:
                if r != "reasoning":
                    try:
                        return AgentRole(r)
                    except ValueError:
                        continue
        return AgentRole.REASONING

    def _resolve_layers(self, tasks: List[OrchestratorTask]) -> List[List[OrchestratorTask]]:
        """Resolve task dependencies into parallel execution layers."""
        task_map = {t.id: t for t in tasks}
        layers: List[List[OrchestratorTask]] = []
        executed: set[str] = set()
        remaining = set(task_map.keys())

        while remaining:
            current_layer = []
            for task_id in list(remaining):
                task = task_map[task_id]
                if set(task.dependencies).issubset(executed):
                    current_layer.append(task)

            if not current_layer:
                # Circular dependency — break by adding remaining
                logger.warning("Circular dependency in orchestrator, breaking with %d tasks", len(remaining))
                current_layer = [task_map[tid] for tid in remaining]
                remaining.clear()
            else:
                for task in current_layer:
                    remaining.remove(task.id)

            layers.append(current_layer)
            for task in current_layer:
                executed.add(task.id)

        return layers

    # ──────────────────────────────────────────────
    # Execution
    # ──────────────────────────────────────────────

    async def _execute_task(
        self,
        task: OrchestratorTask,
        user_id: str,
        conversation_id: Optional[str],
        available_tools: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Execute a single task by dispatching to the appropriate agent."""
        from dash_backend.orchestrator.retry_manager import get_retry_manager

        retry_manager = get_retry_manager()

        # Delegate to the AgentSystem if a handler is registered for this role
        agent_result = await self._try_agent_system(task, user_id, conversation_id)
        if agent_result is not None:
            return agent_result

        # Otherwise use the brain + tool manager for the task
        try:
            return await retry_manager.execute_with_retry(
                self._execute_with_brain,
                task, user_id, conversation_id, available_tools,
                policy_name="tool_execution",
                fallback_strategy="return_default",
                default_value={"output": "Task completed with limited context.", "confidence": 0.5},
            )
        except Exception as exc:
            logger.warning("Task '%s' failed: %s", task.name, exc)
            return {"output": "", "confidence": 0.0, "error": str(exc)}

    async def _try_agent_system(
        self,
        task: OrchestratorTask,
        user_id: str,
        conversation_id: Optional[str],
    ) -> Optional[Dict[str, Any]]:
        """Try to dispatch the task to the AgentSystem's registered handler."""
        try:
            from dash_backend.intelligence.agent_system import AgentSystem, AgentType

            # Map our role to an AgentSystem AgentType
            role_to_type = {
                AgentRole.CODING: AgentType.CODING,
                AgentRole.RESEARCH: AgentType.RESEARCH,
                AgentRole.PLANNING: AgentType.PLANNING,
                AgentRole.DESKTOP: AgentType.DESKTOP,
                AgentRole.BROWSER: AgentType.BROWSER,
                AgentRole.MEMORY: AgentType.MEMORY,
                AgentRole.EXECUTION: AgentType.ORCHESTRATOR,
                AgentRole.REASONING: AgentType.ORCHESTRATOR,
            }
            agent_type = role_to_type.get(task.role)
            if agent_type is None:
                return None

            # Register the agent if not already present
            system = AgentSystem()
            agents = system.get_agent_by_type(agent_type)
            if not agents:
                from dash_backend.intelligence.agent_system import Agent
                agent = Agent(
                    name=f"{task.role.value.title()} Agent",
                    type=agent_type,
                    description=f"Handles {task.role.value} tasks.",
                )
                system.register_agent(agent)

            # Dispatch to handler if registered
            for agent in system.get_agent_by_type(agent_type):
                if agent.id in system.agent_handlers:
                    handler = system.agent_handlers[agent.id]
                    result = await handler(task.description, {"user_id": user_id, "task": task.to_dict()})
                    if result is not None:
                        return {"output": result, "confidence": 0.8, "agent": task.role.value}

        except Exception as exc:
            logger.debug("Agent system dispatch skipped: %s", exc)

        return None

    async def _execute_with_brain(
        self,
        task: OrchestratorTask,
        user_id: str,
        conversation_id: Optional[str],
        available_tools: Optional[List[Dict[str, Any]]],
    ) -> Dict[str, Any]:
        """Execute a task using the BrainService (reasoning + optional tools)."""
        from dash_backend.brain.brain_service import BrainService

        brain = BrainService()
        result = await brain.process(
            query=task.description or task.name,
            user_id=user_id,
            conversation_id=conversation_id,
            memory_context=None,
            conversation_history=None,
            available_tools=available_tools,
        )

        return {
            "output": result.get("conclusion", ""),
            "confidence": result.get("confidence", 0.0),
            "reasoning_steps": result.get("reasoning_steps", []),
        }

    # ──────────────────────────────────────────────
    # Merging / Reflection
    # ──────────────────────────────────────────────

    async def _merge_results(
        self,
        request: str,
        user_id: str,
        conversation_id: Optional[str],
        tasks: List[OrchestratorTask],
        memory_context: Optional[str],
    ) -> Dict[str, Any]:
        """Merge individual task results into a short, natural response."""
        from dash_backend.brain.brain_service import BrainService

        # Build a compact summary of task outputs
        task_summary_parts = []
        for task in tasks:
            if task.status == "completed" and task.result:
                output = str(task.result.get("output", ""))[:300]
                if output:
                    task_summary_parts.append(f"- {task.role.value}: {output}")

        summary_text = "\n".join(task_summary_parts) if task_summary_parts else "No task outputs produced."

        brain = BrainService()
        result = await brain.process(
            query=(
                f"User request: {request}\n\n"
                f"Agent results:\n{summary_text}\n\n"
                "Provide a concise, natural response to the user that summarizes "
                "what was accomplished. Do not expose internal reasoning or agent "
                "details. Just explain the conclusion in plain language."
            ),
            user_id=user_id,
            conversation_id=conversation_id,
            memory_context=memory_context,
        )

        return {
            "response": result.get("conclusion", "I've completed the task."),
            "confidence": result.get("confidence", 0.7),
        }

    async def _reflect(
        self,
        request: str,
        tasks: List[OrchestratorTask],
        merged: Dict[str, Any],
    ) -> Dict[str, Any]:
        """Self-reflect on the orchestration run and log learnings."""
        completed = sum(1 for t in tasks if t.status == "completed")
        failed = sum(1 for t in tasks if t.status == "failed")
        roles_used = sorted({t.role.value for t in tasks})

        reflection = {
            "success": failed == 0,
            "completed_tasks": completed,
            "failed_tasks": failed,
            "roles_used": roles_used,
            "confidence": merged.get("confidence", 0.0),
            "learnings": [],
        }

        # Log learnings for future runs
        if failed == 0:
            reflection["learnings"].append(
                f"Successful workflow for: {request[:80]} using roles {roles_used}"
            )
        else:
            reflection["learnings"].append(
                f"Workflow had {failed} failed tasks for: {request[:80]}"
            )

        logger.info("Reflection: %s", json.dumps(reflection, default=str))
        return reflection

    # ──────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────

    def _summarize_result(self, result: Dict[str, Any]) -> str:
        """Produce a short summary of a task result."""
        output = result.get("output", "")
        if isinstance(output, str):
            return output[:120]
        return str(output)[:120]

    def _build_agent_summary(self, tasks: List[OrchestratorTask]) -> Dict[str, Any]:
        """Build a per-agent-role summary of completed work."""
        summary: Dict[str, Any] = {}
        for task in tasks:
            role = task.role.value
            if role not in summary:
                summary[role] = {"completed": 0, "failed": 0}
            if task.status == "completed":
                summary[role]["completed"] += 1
            elif task.status == "failed":
                summary[role]["failed"] += 1
        return summary

    def get_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return dict(self._stats)


# Global singleton
_orchestrator: Optional[MasterOrchestrator] = None


def get_master_orchestrator() -> MasterOrchestrator:
    """Return the global MasterOrchestrator singleton."""
    global _orchestrator
    if _orchestrator is None:
        _orchestrator = MasterOrchestrator()
    return _orchestrator
