"""Planner - Task decomposition and goal-oriented planning.

Implements intelligent planning capabilities:
- Task decomposition into subtasks
- Goal-oriented planning with dependencies
- Plan execution and monitoring
- Plan adaptation based on execution results

Features:
- Hierarchical task decomposition
- Dependency management between tasks
- Plan execution tracking
- Dynamic plan adaptation
- Progress monitoring and reporting
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class TaskStatus(str, Enum):
    """Status of a task in a plan."""
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    BLOCKED = "blocked"


class PlanStatus(str, Enum):
    """Status of a plan."""
    DRAFT = "draft"
    ACTIVE = "active"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Task:
    """A single task in a plan."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    status: TaskStatus = TaskStatus.PENDING
    dependencies: List[str] = field(default_factory=list)  # Task IDs this depends on
    dependents: List[str] = field(default_factory=list)  # Task IDs that depend on this
    estimated_duration: Optional[float] = None  # in seconds
    actual_duration: Optional[float] = None
    priority: int = 0  # Higher = more important
    required_tools: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "status": self.status.value,
            "dependencies": self.dependencies,
            "dependents": self.dependents,
            "estimated_duration": self.estimated_duration,
            "actual_duration": self.actual_duration,
            "priority": self.priority,
            "required_tools": self.required_tools,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "result": self.result,
            "error": self.error,
        }


@dataclass
class Plan:
    """A plan consisting of multiple tasks."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    goal: str = ""
    status: PlanStatus = PlanStatus.DRAFT
    tasks: List[Task] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    current_task_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "goal": self.goal,
            "status": self.status.value,
            "tasks": [task.to_dict() for task in self.tasks],
            "created_at": self.created_at.isoformat(),
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "metadata": self.metadata,
            "current_task_id": self.current_task_id,
        }


@dataclass
class PlanExecutionResult:
    """Result of plan execution."""
    plan_id: str
    success: bool
    completed_tasks: int
    total_tasks: int
    execution_time: float
    results: Dict[str, Any] = field(default_factory=dict)
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_id": self.plan_id,
            "success": self.success,
            "completed_tasks": self.completed_tasks,
            "total_tasks": self.total_tasks,
            "execution_time": self.execution_time,
            "results": self.results,
            "errors": self.errors,
        }


class Planner:
    """Task decomposition and goal-oriented planning engine.

    Creates and executes plans to achieve goals by decomposing
    them into manageable tasks with dependencies.
    """

    def __init__(self):
        self._plans: Dict[str, Plan] = {}
        self._task_executor: Optional[Callable] = None
        self._max_parallel_tasks = 3

    def set_task_executor(self, executor: Callable) -> None:
        """Set the task executor function."""
        self._task_executor = executor

    async def create_plan(
        self,
        goal: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Plan:
        """Create a new plan for a goal.

        Args:
            goal: The goal to achieve
            name: Optional plan name
            description: Optional plan description
            metadata: Additional metadata

        Returns:
            The created plan
        """
        plan = Plan(
            name=name or f"Plan for: {goal[:50]}",
            description=description or "",
            goal=goal,
            metadata=metadata or {},
        )

        self._plans[plan.id] = plan
        logger.info("Created plan: %s for goal: %s", plan.id, goal[:100])
        return plan

    async def decompose_task(
        self,
        plan: Plan,
        task_description: str,
        use_llm: bool = True,
    ) -> List[Task]:
        """Decompose a task into subtasks.

        Args:
            plan: The plan to add tasks to
            task_description: The task to decompose
            use_llm: Whether to use LLM for decomposition

        Returns:
            List of decomposed tasks
        """
        if use_llm and self._task_executor:
            # Use LLM to decompose
            try:
                subtasks = await self._llm_decompose(task_description)
                tasks = []
                for i, subtask_desc in enumerate(subtasks):
                    task = Task(
                        name=f"Task {i+1}",
                        description=subtask_desc,
                        priority=len(subtasks) - i,  # Earlier tasks higher priority
                    )
                    tasks.append(task)
                    plan.tasks.append(task)

                logger.info("Decomposed task into %d subtasks using LLM", len(tasks))
                return tasks
            except Exception as exc:
                logger.warning("LLM decomposition failed: %s", exc)

        # Fallback: create a single task
        task = Task(
            name="Main Task",
            description=task_description,
            priority=10,
        )
        plan.tasks.append(task)
        logger.info("Created single task as fallback decomposition")
        return [task]

    async def _llm_decompose(self, task_description: str) -> List[str]:
        """Use the configured LLM to decompose a task into ordered subtasks."""
        from dash_backend.llm.service import build_chat_messages, collect_streamed_response

        messages = build_chat_messages(
            system_prompt=(
                "You are a task planner. Decompose the user's task into 2-6 concise, "
                "ordered subtasks. Reply with ONLY the subtasks, one per line, "
                "numbered like '1. ...'. No extra prose."
            ),
            user_message=task_description,
        )
        raw = await collect_streamed_response(messages)
        subtasks: List[str] = []
        for line in raw.splitlines():
            line = line.strip()
            if not line:
                continue
            # Strip leading enumeration ("1.", "2)", "-", "*").
            stripped = line.lstrip("0123456789.-*) ").strip()
            if stripped:
                subtasks.append(stripped)
        if not subtasks:
            raise ValueError("LLM returned no parseable subtasks")
        return subtasks

    def add_task(
        self,
        plan: Plan,
        name: str,
        description: str,
        dependencies: Optional[List[str]] = None,
        priority: int = 0,
        required_tools: Optional[List[str]] = None,
        estimated_duration: Optional[float] = None,
    ) -> Task:
        """Add a task to a plan."""
        task = Task(
            name=name,
            description=description,
            dependencies=dependencies or [],
            priority=priority,
            required_tools=required_tools or [],
            estimated_duration=estimated_duration,
        )

        plan.tasks.append(task)

        # Update dependency links
        for dep_id in task.dependencies:
            dep_task = self._get_task_by_id(plan, dep_id)
            if dep_task:
                dep_task.dependents.append(task.id)

        logger.debug("Added task %s to plan %s", task.name, plan.id)
        return task

    def _get_task_by_id(self, plan: Plan, task_id: str) -> Optional[Task]:
        """Get a task by ID within a plan."""
        for task in plan.tasks:
            if task.id == task_id:
                return task
        return None

    def get_plan(self, plan_id: str) -> Optional[Plan]:
        """Get a plan by ID."""
        return self._plans.get(plan_id)

    def get_all_plans(self) -> List[Plan]:
        """Get all plans."""
        return list(self._plans.values())

    async def execute_plan(
        self,
        plan_id: str,
        adapt: bool = True,
    ) -> PlanExecutionResult:
        """Execute a plan.

        Args:
            plan_id: ID of the plan to execute
            adapt: Whether to adapt the plan during execution

        Returns:
            Execution result
        """
        plan = self._plans.get(plan_id)
        if not plan:
            return PlanExecutionResult(
                plan_id=plan_id,
                success=False,
                completed_tasks=0,
                total_tasks=0,
                execution_time=0.0,
                errors=["Plan not found"],
            )

        plan.status = PlanStatus.ACTIVE
        plan.started_at = datetime.now(timezone.utc)

        logger.info("Starting execution of plan: %s", plan.id)

        start_time = asyncio.get_event_loop().time()
        completed_tasks = 0
        errors = []
        results = {}

        try:
            # Execute tasks in dependency order
            while True:
                # Find next executable tasks
                executable = self._find_executable_tasks(plan)

                if not executable:
                    # Check if all tasks are done
                    if all(t.status in (TaskStatus.COMPLETED, TaskStatus.SKIPPED) for t in plan.tasks):
                        break
                    # Check if blocked
                    if any(t.status == TaskStatus.BLOCKED for t in plan.tasks):
                        break
                    # No executable tasks but not done - likely circular dependency
                    logger.error("No executable tasks found, possible circular dependency")
                    errors.append("Circular dependency detected")
                    break

                # Execute up to max_parallel_tasks in parallel
                batch = executable[:self._max_parallel_tasks]
                task_results = await asyncio.gather(
                    *[self._execute_task(plan, task) for task in batch],
                    return_exceptions=True,
                )

                for task, result in zip(batch, task_results):
                    if isinstance(result, Exception):
                        logger.error("Task %s failed: %s", task.name, result)
                        task.status = TaskStatus.FAILED
                        task.error = str(result)
                        errors.append(f"Task {task.name} failed: {result}")
                    else:
                        task.status = TaskStatus.COMPLETED
                        task.completed_at = datetime.now(timezone.utc)
                        task.result = result
                        completed_tasks += 1
                        results[task.id] = result

                        # Adapt plan if enabled
                        if adapt:
                            await self._adapt_plan(plan, task, result)

                # Check if we should stop on failure
                if errors and not adapt:
                    break

        except Exception as exc:
            logger.error("Plan execution failed: %s", exc)
            errors.append(str(exc))

        execution_time = (asyncio.get_event_loop().time() - start_time)

        # Update plan status
        plan.completed_at = datetime.now(timezone.utc)
        if completed_tasks == len(plan.tasks):
            plan.status = PlanStatus.COMPLETED
        elif errors:
            plan.status = PlanStatus.FAILED
        else:
            plan.status = PlanStatus.CANCELLED

        logger.info(
            "Plan execution completed: %d/%d tasks in %.2fs",
            completed_tasks,
            len(plan.tasks),
            execution_time,
        )

        return PlanExecutionResult(
            plan_id=plan_id,
            success=plan.status == PlanStatus.COMPLETED,
            completed_tasks=completed_tasks,
            total_tasks=len(plan.tasks),
            execution_time=execution_time,
            results=results,
            errors=errors,
        )

    def _find_executable_tasks(self, plan: Plan) -> List[Task]:
        """Find tasks that can be executed (dependencies satisfied)."""
        executable = []
        for task in plan.tasks:
            if task.status != TaskStatus.PENDING:
                continue

            # Check if all dependencies are completed
            dependencies_satisfied = True
            for dep_id in task.dependencies:
                dep_task = self._get_task_by_id(plan, dep_id)
                if not dep_task or dep_task.status != TaskStatus.COMPLETED:
                    dependencies_satisfied = False
                    break

            if dependencies_satisfied:
                executable.append(task)

        # Sort by priority (higher first)
        executable.sort(key=lambda t: t.priority, reverse=True)
        return executable

    async def _execute_task(self, plan: Plan, task: Task) -> Any:
        """Execute a single task."""
        task.status = TaskStatus.IN_PROGRESS
        task.started_at = datetime.now(timezone.utc)
        plan.current_task_id = task.id

        logger.info("Executing task: %s", task.name)

        if self._task_executor:
            try:
                result = await self._task_executor(task, plan)
                task.actual_duration = (
                    datetime.now(timezone.utc) - task.started_at
                ).total_seconds()
                return result
            except Exception as exc:
                task.actual_duration = (
                    datetime.now(timezone.utc) - task.started_at
                ).total_seconds()
                raise
        else:
            # Mock execution
            await asyncio.sleep(0.1)
            task.actual_duration = 0.1
            return f"Executed: {task.name}"

    async def _adapt_plan(
        self,
        plan: Plan,
        completed_task: Task,
        result: Any,
    ) -> None:
        """Adapt the plan based on task execution result."""
        # This is a placeholder for plan adaptation logic
        # In production, this would analyze the result and potentially:
        # - Add new tasks
        # - Modify existing tasks
        # - Skip dependent tasks
        # - Re-prioritize tasks
        pass

    def cancel_plan(self, plan_id: str) -> bool:
        """Cancel a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return False

        plan.status = PlanStatus.CANCELLED

        # Mark in-progress tasks as skipped
        for task in plan.tasks:
            if task.status == TaskStatus.IN_PROGRESS:
                task.status = TaskStatus.SKIPPED

        logger.info("Cancelled plan: %s", plan_id)
        return True

    def delete_plan(self, plan_id: str) -> bool:
        """Delete a plan."""
        if plan_id in self._plans:
            del self._plans[plan_id]
            logger.info("Deleted plan: %s", plan_id)
            return True
        return False

    def get_plan_progress(self, plan_id: str) -> Dict[str, Any]:
        """Get progress information for a plan."""
        plan = self._plans.get(plan_id)
        if not plan:
            return {}

        total = len(plan.tasks)
        completed = sum(1 for t in plan.tasks if t.status == TaskStatus.COMPLETED)
        failed = sum(1 for t in plan.tasks if t.status == TaskStatus.FAILED)
        in_progress = sum(1 for t in plan.tasks if t.status == TaskStatus.IN_PROGRESS)
        pending = sum(1 for t in plan.tasks if t.status == TaskStatus.PENDING)

        return {
            "plan_id": plan_id,
            "status": plan.status.value,
            "total_tasks": total,
            "completed": completed,
            "failed": failed,
            "in_progress": in_progress,
            "pending": pending,
            "progress_percent": (completed / total * 100) if total > 0 else 0,
        }

    def get_statistics(self) -> Dict[str, Any]:
        """Get planner statistics."""
        return {
            "total_plans": len(self._plans),
            "by_status": {
                status.value: len([p for p in self._plans.values() if p.status == status])
                for status in PlanStatus
            },
            "total_tasks": sum(len(p.tasks) for p in self._plans.values()),
        }



