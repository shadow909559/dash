"""Workflow Engine - Task automation and workflow management."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import asyncio

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


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
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
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
        workflow.last_run = datetime.utcnow()
        
        logger.info(f"Starting workflow: {workflow.name} ({workflow_id})")
        
        try:
            for i, step in enumerate(workflow.steps):
                workflow.current_step_index = i
                step.state = WorkflowState.RUNNING
                step.started_at = datetime.utcnow()
                
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
                            result = await asyncio.wait_for(
                                handler(**step.parameters),
                                timeout=step.timeout
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
                
                step.completed_at = datetime.utcnow()
                
                if step.state == WorkflowState.FAILED:
                    workflow.state = WorkflowState.FAILED
                    workflow.error = f"Step {i} failed: {step.error}"
                    raise Exception(workflow.error)
            
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
        step.started_at = datetime.utcnow()
        
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
