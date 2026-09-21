"""Workflow Engine - Task automation and workflow management."""

from __future__ import annotations

import uuid
import inspect
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timezone
import asyncio

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Aware-UTC now — replaces the deprecated ``datetime.utcnow()``."""
    return datetime.now(timezone.utc)


class WorkflowState(Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class StepType(Enum):
    ACTION = "action"
    CONDITION = "condition"
    PARALLEL = "parallel"
    DELAY = "delay"
    SUB_WORKFLOW = "sub_workflow"


@dataclass
class WorkflowStep:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: StepType = StepType.ACTION
    name: str = ""
    action: Optional[str] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    condition: Optional[str] = None
    steps: List["WorkflowStep"] = field(default_factory=list)
    delay: float = 0
    timeout: float = 30
    retry_count: int = 0
    max_retries: int = 3
    state: WorkflowState = WorkflowState.PENDING
    result: Optional[Any] = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None


@dataclass
class Workflow:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    trigger: str = ""  # cron, event, manual
    enabled: bool = True
    steps: List[WorkflowStep] = field(default_factory=list)
    state: WorkflowState = WorkflowState.PENDING
    current_step_index: int = 0
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)
    last_run: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class WorkflowEngine:
    """Manages workflow execution, scheduling, and monitoring."""
    
    def __init__(self):
        self.workflows: Dict[str, Workflow] = {}
        self.active_executions: Dict[str, asyncio.Task] = {}
        self.action_handlers: Dict[str, Callable] = {}
        self.condition_evaluators: Dict[str, Callable] = None
    
    def register_action(self, name: str, handler: Callable) -> None:
        """Register an action handler."""
        self.action_handlers[name] = handler
        logger.info(f"Registered action handler: {name}")
    
    def register_condition(self, name: str, evaluator: Callable) -> None:
        """Register a condition evaluator."""
        self.condition_evaluators[name] = evaluator
        logger.info(f"Registered condition evaluator: {name}")
    
    def create_workflow(self, name: str, description: str, trigger: str, steps: List[WorkflowStep]) -> Workflow:
        """Create a new workflow."""
        workflow = Workflow(
            name=name,
            description=description,
            trigger=trigger,
            steps=steps,
        )
        self.workflows[workflow.id] = workflow
        logger.info(f"Created workflow: {name} ({workflow.id})")
        return workflow
    
    async def execute_workflow(self, workflow_id: str) -> Any:
        """Execute a workflow step by step."""
        if workflow_id not in self.workflows:
            raise ValueError(f"Workflow {workflow_id} not found")
        
        workflow = self.workflows[workflow_id]
        workflow.state = WorkflowState.RUNNING
        workflow.current_step_index = 0
        workflow.last_run = _utcnow()
        
        logger.info(f"Starting workflow: {workflow.name} ({workflow_id})")
        
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step_index = i
                step.state = WorkflowState.RUNNING
                step.started_at = _utcnow()
                
                logger.info(f"Executing step {i+1}/{len(workflow.steps)}: {step.name or step.type.value}")
                
                if step.type == StepType.ACTION:
                    if not step.action:
                        raise ValueError(f"Step {i} has no action specified")
                    
                    if step.action not in self.action_handlers:
                        raise ValueError(f"Action handler not found: {step.action}")
                    
                    handler = self.action_handlers[step.action]
                    
                    retries = 0
                    while retries <= step.max_retries:
                        try:
                            result = await self._invoke_handler(
                                handler, step.parameters, step.timeout
                            )
                            step.result = result
                            step.state = WorkflowState.COMPLETED
                            break
                        except asyncio.TimeoutError:
                            retries += 1
                            if retries > step.max_retries:
                                raise
                            logger.warning(f"Step {i} timed out, retry {retries}/{step.max_retries}")
                            await asyncio.sleep(1)
                        except Exception as e:
                            retries += 1
                            if retries > step.max_retries:
                                raise
                            logger.warning(f"Step {i} failed, retry {retries}/{step.max_retries}: {e}")
                            await asyncio.sleep(1)
                
                elif step.type == StepType.CONDITION:
                    if not step.condition:
                        raise ValueError(f"Step {i} has no condition specified")
                    
                    if step.condition not in self.condition_evaluators:
                        raise ValueError(f"Condition evaluator not found: {step.condition}")
                    
                    evaluator = self.condition_evaluators[step.condition]
                    result = await evaluator(**step.parameters)
                    step.result = result
                    step.state = WorkflowState.COMPLETED
                    
                    if not result:
                        logger.info(f"Condition {i} evaluated to False, stopping workflow")
                        workflow.state = WorkflowState.COMPLETED
                        return result
                
                elif step.type == StepType.PARALLEL:
                    tasks = []
                    for sub_step in step.steps:
                        task = asyncio.create_task(self._execute_step(sub_step))
                        tasks.append(task)
                    
                    results = await asyncio.gather(*tasks, return_exceptions=True)
                    step.result = results
                    step.state = WorkflowState.COMPLETED
                
                elif step.type == StepType.DELAY:
                    await asyncio.sleep(step.delay)
                    step.result = f"Delayed for {step.delay}s"
                    step.state = WorkflowState.COMPLETED
                
                elif step.type == StepType.SUB_WORKFLOW:
                    result = await self.execute_workflow(step.action or "")
                    step.result = result
                    step.state = WorkflowState.COMPLETED
                
                step.completed_at = _utcnow()
                
                if step.state == WorkflowState.FAILED:
                    workflow.state = WorkflowState.FAILED
                    workflow.error = f"Step {i} failed: {step.error}"
                    raise Exception(workflow.error)
            
            workflow.result = [step.result for step in workflow.steps]
            workflow.state = WorkflowState.COMPLETED
            logger.info(f"Workflow completed: {workflow.name} ({workflow.id})")
            return workflow.result
        
        except Exception as e:
            workflow.state = WorkflowState.FAILED
            workflow.error = str(e)
            logger.error(f"Workflow failed: {workflow.name} ({workflow.id}): {e}")
            raise
    
    async def _execute_step(self, step: WorkflowStep) -> Any:
        """Execute a single step (for parallel execution)."""
        step.state = WorkflowState.RUNNING
        step.started_at = _utcnow()
        
        try:
            if step.type == StepType.ACTION:
                if not step.action:
                    raise ValueError("Step has no action specified")
                
                if step.action not in self.action_handlers:
                    raise ValueError(f"Action handler not found: {step.action}")
                
                handler = self.action_handlers[step.action]
                result = await asyncio.wait_for(
                    handler(**step.parameters),
                    timeout=step.timeout
                )
                step.result = result
                step.state = WorkflowState.COMPLETED
                return result
            
            elif step.type == StepType.CONDITION:
                if not step.condition:
                    raise ValueError("Step has no condition specified")
                
                if step.condition not in self.condition_evaluators:
                    raise ValueError(f"Condition evaluator not found: {step.condition}")
                
                evaluator = self.condition_evaluators[step.condition]
                result = await evaluator(**step.parameters)
                step.result = result
                step.state = WorkflowState.COMPLETED
                return result
            
            elif step.type == StepType.DELAY:
                await asyncio.sleep(step.delay)
                step.result = f"Delayed for {step.delay}s"
                step.state = WorkflowState.COMPLETED
                return step.result
            
            else:
                raise ValueError(f"Unsupported step type for parallel execution: {step.type}")
        
        except Exception as e:
            step.state = WorkflowState.FAILED
            step.error = str(e)
            raise
    
    async def _invoke_handler(
        self, handler: Callable, parameters: Dict[str, Any], timeout: float
    ) -> Any:
        """Call an action handler that may be sync or async.

        Mirrors ``TaskQueue._invoke``: awaitable results get the step
        timeout, sync results return directly (the dataclass contract only
        promises ``Callable``).
        """
        outcome = handler(**parameters)
        if inspect.isawaitable(outcome):
            return await asyncio.wait_for(outcome, timeout=timeout)
        return outcome

    async def cancel_workflow(self, workflow_id: str) -> bool:
        """Cancel a running workflow."""
        if workflow_id not in self.workflows:
            return False
        
        if workflow_id in self.active_executions:
            task = self.active_executions[workflow_id]
            task.cancel()
            del self.active_executions[workflow_id]
            
            workflow = self.workflows[workflow_id]
            workflow.state = WorkflowState.CANCELLED
            logger.info(f"Cancelled workflow: {workflow.name} ({workflow_id})")
            return True
        
        return False
    
    def get_workflow(self, workflow_id: str) -> Optional[Workflow]:
        """Get a workflow by ID."""
        return self.workflows.get(workflow_id)
    
    def list_workflows(self) -> List[Workflow]:
        """List all workflows."""
        return list(self.workflows.values())
    
    def get_active_workflows(self) -> List[Workflow]:
        """Get all currently running workflows."""
        return [wf for wf in self.workflows.values() if wf.state == WorkflowState.RUNNING]


# ── Process-wide shared instance ─────────────────────────────
# Same rationale as TaskQueue.get_shared_task_queue: engines constructed
# per call lose every created workflow before execution time. The shared
# instance survives and rebinds when the event loop changes (dead-loop
# executions are marked CANCELLED; workflow definitions and handler
# registrations carry forward).

_shared_workflow_engine: Optional["WorkflowEngine"] = None
_shared_workflow_engine_loop: Optional[asyncio.AbstractEventLoop] = None


def get_shared_workflow_engine() -> WorkflowEngine:
    """Return the process-wide WorkflowEngine, rebound on event-loop change."""
    global _shared_workflow_engine, _shared_workflow_engine_loop
    try:
        loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if (
        _shared_workflow_engine is not None
        and loop is not None
        and _shared_workflow_engine_loop is not loop
    ):
        old = _shared_workflow_engine
        fresh = WorkflowEngine()
        fresh.workflows.update(old.workflows)
        fresh.action_handlers.update(old.action_handlers)
        if old.condition_evaluators:
            if fresh.condition_evaluators is None:
                fresh.condition_evaluators = {}
            fresh.condition_evaluators.update(old.condition_evaluators)
        for wf in fresh.workflows.values():
            if wf.state == WorkflowState.RUNNING:
                wf.state = WorkflowState.CANCELLED
                wf.error = "interrupted by event-loop restart"
        logger.info(
            "Event loop changed: rebound shared workflow engine (%d workflows)",
            len(fresh.workflows),
        )
        _shared_workflow_engine = fresh
        _shared_workflow_engine_loop = loop

    if _shared_workflow_engine is None:
        _shared_workflow_engine = WorkflowEngine()
        _shared_workflow_engine_loop = loop
    return _shared_workflow_engine
