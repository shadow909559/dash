"""Task Planner - Advanced goal decomposition and task planning for DASH AI OS.

Provides:
- Goal decomposition into structured subtasks
- Dependency resolution with parallel execution layers
- Alternative plan generation (multiple strategies)
- Plan scoring and selection
- Plan revision on failure
- Resource-aware planning
- Time estimation
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    """Priority levels for tasks."""
    CRITICAL = 0
    HIGH = 1
    MEDIUM = 2
    LOW = 3
    BACKGROUND = 4


class TaskStatus(Enum):
    """Status of a planned task."""
    PENDING = "pending"
    READY = "ready"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"
    CANCELLED = "cancelled"


@dataclass
class PlannedTask:
    """A single task in a plan.
    
    Attributes:
        id: Unique task ID
        name: Short task name
        description: Detailed description
        priority: Task priority
        estimated_duration: Estimated time in seconds
        dependencies: List of task IDs that must complete first
        required_tools: List of tool names needed
        required_skills: List of skill names needed
        context: Additional context for execution
        verification: How to verify completion
        fallback: Fallback strategy on failure
        status: Current status
        result: Task execution result
        error: Error message if failed
        created_at: When task was created
    """
    id: str = ""
    name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.MEDIUM
    estimated_duration: float = 60.0
    dependencies: List[str] = field(default_factory=list)
    required_tools: List[str] = field(default_factory=list)
    required_skills: List[str] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    verification: Optional[str] = None
    fallback: Optional[str] = None
    status: TaskStatus = TaskStatus.PENDING
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: float = 0.0
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "priority": self.priority.name,
            "estimated_duration": self.estimated_duration,
            "dependencies": self.dependencies,
            "required_tools": self.required_tools,
            "required_skills": self.required_skills,
            "verification": self.verification,
            "fallback": self.fallback,
            "status": self.status.value,
            "error": self.error,
        }


@dataclass
class ExecutionLayer:
    """A layer of tasks that can execute in parallel.
    
    Attributes:
        layer_index: Layer number
        tasks: Tasks in this layer
        estimated_duration: Estimated time for this layer
        parallel: Whether tasks execute in parallel
    """
    layer_index: int = 0
    tasks: List[PlannedTask] = field(default_factory=list)
    estimated_duration: float = 0.0
    parallel: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "layer_index": self.layer_index,
            "tasks": [t.to_dict() for t in self.tasks],
            "estimated_duration": self.estimated_duration,
            "parallel": self.parallel,
        }


@dataclass
class Plan:
    """A complete execution plan.
    
    Attributes:
        id: Unique plan ID
        goal: Original goal description
        tasks: All tasks in the plan
        layers: Execution layers (parallel groups)
        total_estimated_duration: Total estimated time
        confidence: Plan confidence score (0-1)
        alternatives: Alternative plan strategies
        metadata: Additional plan metadata
        created_at: When plan was created
        status: Plan execution status
    """
    id: str = ""
    goal: str = ""
    tasks: Dict[str, PlannedTask] = field(default_factory=dict)
    layers: List[ExecutionLayer] = field(default_factory=list)
    total_estimated_duration: float = 0.0
    confidence: float = 0.0
    alternatives: List[Dict[str, Any]] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = 0.0
    status: str = "created"
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "goal": self.goal,
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "layers": [l.to_dict() for l in self.layers],
            "total_estimated_duration": self.total_estimated_duration,
            "confidence": self.confidence,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "status": self.status,
        }


class TaskPlanner:
    """Advanced task planner with goal decomposition and dependency resolution.
    
    Features:
    - Automatic goal decomposition
    - Dependency graph construction
    - Parallel execution layer identification
    - Resource-aware planning
    - Alternative plan generation
    - Plan scoring and selection
    - Dynamic plan revision
    """
    
    def __init__(self):
        self._plans: Dict[str, Plan] = {}
        self._decomposers: Dict[str, Callable] = {}
        self._stats = {
            "plans_created": 0,
            "plans_revised": 0,
            "total_tasks_planned": 0,
        }
    
    # ── Decomposer Registration ─────────────────────────────
    
    def register_decomposer(self, domain: str, decomposer_fn: Callable) -> None:
        """Register a domain-specific task decomposer.
        
        Args:
            domain: Domain name (e.g., "code", "research", "system")
            decomposer_fn: Async function (goal, context) -> List[PlannedTask]
        """
        self._decomposers[domain] = decomposer_fn
        logger.info("Registered decomposer for domain '%s'", domain)
    
    # ── Plan Creation ───────────────────────────────────────
    
    async def create_plan(self, goal: str, context: Optional[Dict[str, Any]] = None,
                           max_tasks: int = 15, generate_alternatives: bool = True) -> Plan:
        """Create a plan for a given goal.
        
        Args:
            goal: The goal to accomplish
            context: Optional context (memory, preferences, constraints)
            max_tasks: Maximum number of tasks
            generate_alternatives: Whether to generate alternative plans
            
        Returns:
            Plan with tasks and execution layers
        """
        context = context or {}
        
        # Decompose the goal into tasks
        tasks = await self._decompose_goal(goal, context, max_tasks)
        
        if not tasks:
            # Fallback: create a single task
            task = PlannedTask(
                name=goal[:100],
                description=goal,
                estimated_duration=300.0,
            )
            tasks = [task]
        
        # Create the plan
        plan = Plan(
            goal=goal,
            metadata=context,
        )
        
        for task in tasks:
            plan.tasks[task.id] = task
        
        # Resolve dependencies into execution layers
        plan.layers = self._resolve_layers(plan.tasks)
        
        # Calculate estimated duration
        plan.total_estimated_duration = sum(
            max(t.estimated_duration for t in layer.tasks) if layer.parallel
            else sum(t.estimated_duration for t in layer.tasks)
            for layer in plan.layers
        )
        
        # Calculate confidence
        plan.confidence = self._calculate_confidence(plan)
        
        # Generate alternative plans if requested
        if generate_alternatives:
            plan.alternatives = await self._generate_alternatives(goal, context, tasks, max_tasks)
        
        self._plans[plan.id] = plan
        self._stats["plans_created"] += 1
        self._stats["total_tasks_planned"] += len(tasks)
        
        logger.info("Created plan '%s' with %d tasks in %d layers (confidence=%.2f)",
                     plan.id[:8], len(tasks), len(plan.layers), plan.confidence)
        
        return plan
    
    async def _decompose_goal(self, goal: str, context: Dict[str, Any],
                                max_tasks: int) -> List[PlannedTask]:
        """Decompose a goal into structured tasks.
        
        Uses registered decomposers or LLM-based decomposition.
        
        Args:
            goal: The goal to decompose
            context: Execution context
            max_tasks: Maximum tasks
            
        Returns:
            List of PlannedTask
        """
        # Check for domain-specific decomposer
        domain = context.get("domain", "")
        if domain and domain in self._decomposers:
            try:
                return await self._decomposers[domain](goal, context)
            except Exception as exc:
                logger.warning("Domain decomposer '%s' failed: %s", domain, exc)
        
        # LLM-based decomposition via planner
        try:
            from dash_backend.executive.planner import Planner
            
            memory_context = context.get("memory_context")
            tasks_data = await Planner.decompose(
                goal_name=goal,
                goal_description=goal,
                max_tasks=max_tasks,
                memory_context=memory_context,
            )
            
            planned_tasks = []
            for i, td in enumerate(tasks_data):
                task = PlannedTask(
                    name=td.get("name", f"Step {i+1}"),
                    description=td.get("description", ""),
                    estimated_duration=float(td.get("est_minutes", 5) * 60),
                    dependencies=[],
                    required_tools=td.get("tools", []),
                    verification=td.get("verification"),
                )
                
                # Resolve dependency names to IDs
                dep_names = td.get("depends_on", [])
                for planned in planned_tasks:
                    if planned.name in dep_names:
                        task.dependencies.append(planned.id)
                
                planned_tasks.append(task)
            
            return planned_tasks
            
        except Exception as exc:
            logger.warning("LLM decomposition failed: %s", exc)
            return []
    
    def _resolve_layers(self, tasks: Dict[str, PlannedTask]) -> List[ExecutionLayer]:
        """Resolve task dependencies into parallel execution layers.
        
        Args:
            tasks: Dict of task_id -> PlannedTask
            
        Returns:
            List of ExecutionLayer (parallel groups)
        """
        task_map = {t.id: t for t in tasks.values()}
        layers: List[ExecutionLayer] = []
        executed: Set[str] = set()
        
        remaining = set(task_map.keys())
        
        while remaining:
            # Find tasks with all dependencies satisfied
            current_layer_tasks = []
            for task_id in list(remaining):
                task = task_map[task_id]
                deps = set(task.dependencies)
                if deps.issubset(executed):
                    current_layer_tasks.append(task)
            
            if not current_layer_tasks:
                # Circular dependency - break by adding remaining
                logger.warning("Circular dependency detected, breaking with %d tasks", len(remaining))
                current_layer_tasks = [task_map[tid] for tid in remaining]
                remaining.clear()
            else:
                for task in current_layer_tasks:
                    remaining.remove(task.id)
            
            # Create layer
            layer = ExecutionLayer(
                layer_index=len(layers),
                tasks=current_layer_tasks,
                estimated_duration=(
                    max(t.estimated_duration for t in current_layer_tasks)
                    if len(current_layer_tasks) > 1
                    else sum(t.estimated_duration for t in current_layer_tasks)
                ),
            )
            layers.append(layer)
            
            # Mark as executed
            for task in current_layer_tasks:
                executed.add(task.id)
        
        return layers
    
    def _calculate_confidence(self, plan: Plan) -> float:
        """Calculate confidence score for a plan.
        
        Factors:
        - Number of tasks (more tasks = lower confidence)
        - Dependency depth (deeper = lower confidence)
        - Tool availability
        - Resource constraints
        
        Args:
            plan: The plan to evaluate
            
        Returns:
            Confidence score 0-1
        """
        task_count = len(plan.tasks)
        if task_count == 0:
            return 0.0
        
        # Base confidence
        confidence = 0.9
        
        # Reduce for task count (more tasks = more uncertainty)
        if task_count > 10:
            confidence -= 0.1
        elif task_count > 5:
            confidence -= 0.05
        
        # Reduce for dependency depth
        max_depth = len(plan.layers)
        if max_depth > 5:
            confidence -= 0.1
        elif max_depth > 3:
            confidence -= 0.05
        
        # Reduce for missing tools
        for task in plan.tasks.values():
            if task.required_tools:
                try:
                    from dash_backend.tools.tool_registry import get_registry
                    registry = get_registry()
                    for tool_name in task.required_tools:
                        if not registry.get(tool_name):
                            confidence -= 0.05
                except Exception:
                    pass
        
        return max(0.1, min(1.0, confidence))
    
    async def _generate_alternatives(self, goal: str, context: Dict[str, Any],
                                       primary_tasks: List[PlannedTask],
                                       max_tasks: int) -> List[Dict[str, Any]]:
        """Generate alternative plan strategies.
        
        Args:
            goal: The goal
            context: Execution context
            primary_tasks: Primary plan tasks
            max_tasks: Maximum tasks
            
        Returns:
            List of alternative plan descriptions
        """
        alternatives = []
        
        try:
            from dash_backend.llm.service import collect_streamed_response, build_chat_messages
            
            prompt = (
                f"Given the goal: '{goal}'\n\n"
                f"Primary plan has {len(primary_tasks)} tasks.\n"
                "Provide 2-3 alternative approaches to accomplish this goal. "
                "For each alternative, provide a name and brief description. "
                "Return as JSON list of objects with keys 'name' and 'description'."
            )
            
            messages = build_chat_messages(
                system_prompt="You are a strategic planning assistant.",
                user_message=prompt,
            )
            
            text = await collect_streamed_response(messages)
            text = text.strip()
            if text.startswith("```"):
                parts = text.split("```")
                if len(parts) >= 2:
                    text = parts[1].strip()
            
            alternatives = json.loads(text)
            if isinstance(alternatives, list):
                alternatives = alternatives[:3]
            else:
                alternatives = []
                
        except Exception as exc:
            logger.debug("Alternative generation failed: %s", exc)
        
        return alternatives
    
    # ── Plan Revision ───────────────────────────────────────
    
    async def revise_plan(self, plan_id: str, failed_task_id: str,
                           failure_reason: str) -> Optional[Plan]:
        """Revise a plan after a task failure.
        
        Args:
            plan_id: Plan ID to revise
            failed_task_id: ID of the failed task
            failure_reason: Reason for failure
            
        Returns:
            Revised Plan or None
        """
        plan = self._plans.get(plan_id)
        if not plan:
            logger.warning("Plan %s not found for revision", plan_id)
            return None
        
        failed_task = plan.tasks.get(failed_task_id)
        if not failed_task:
            logger.warning("Task %s not found in plan %s", failed_task_id, plan_id)
            return None
        
        logger.info("Revising plan %s due to task '%s' failure: %s",
                     plan_id[:8], failed_task.name, failure_reason)
        
        # Try fallback strategy
        if failed_task.fallback:
            revised_task = PlannedTask(
                name=f"{failed_task.name} (fallback)",
                description=f"Fallback: {failed_task.fallback}",
                dependencies=failed_task.dependencies,
                estimated_duration=failed_task.estimated_duration * 1.5,
            )
            plan.tasks[revised_task.id] = revised_task
            
            # Update dependencies of downstream tasks
            for task in plan.tasks.values():
                if failed_task_id in task.dependencies:
                    task.dependencies.remove(failed_task_id)
                    task.dependencies.append(revised_task.id)
        
        # Re-resolve layers
        plan.layers = self._resolve_layers(plan.tasks)
        plan.total_estimated_duration = sum(
            max(t.estimated_duration for t in layer.tasks)
            for layer in plan.layers
        )
        plan.confidence = self._calculate_confidence(plan) * 0.9  # Reduced confidence
        plan.status = "revised"
        
        self._stats["plans_revised"] += 1
        
        return plan
    
    # ── Plan Access ─────────────────────────────────────────
    
    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID.
        
        Args:
            plan_id: Plan ID
            
        Returns:
            Plan or None
        """
        return self._plans.get(plan_id)
    
    def get_active_plans(self) -> List[Plan]:
        """Get all active (in-progress) plans.
        
        Returns:
            List of active plans
        """
        return [p for p in self._plans.values() if p.status in ("created", "revised")]
    
    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a plan.
        
        Args:
            plan_id: Plan ID to cancel
            
        Returns:
            True if cancelled
        """
        plan = self._plans.get(plan_id)
        if plan:
            plan.status = "cancelled"
            return True
        return False
    
    # ── Stats ───────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get planner statistics."""
        return {
            **self._stats,
            "active_plans": len(self.get_active_plans()),
            "total_plans": len(self._plans),
        }


# Global singleton
_task_planner: Optional[TaskPlanner] = None


def get_task_planner() -> TaskPlanner:
    """Get or create the global TaskPlanner singleton."""
    global _task_planner
    if _task_planner is None:
        _task_planner = TaskPlanner()
    return _task_planner
