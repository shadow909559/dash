"""Unified Task Execution Pipeline - Every request goes through the same pipeline."""

from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import asyncio
from dash_backend.core.logging import get_logger
from dash_backend.core.global_context import get_global_context, TaskInfo
from dash_backend.core.event_bus import get_event_bus, EventType, Event

logger = get_logger(__name__)


class TaskPriority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class TaskStatus(str, Enum):
    PENDING = "pending"
    UNDERSTANDING = "understanding"
    PLANNING = "planning"
    TOOL_SELECTION = "tool_selection"
    EXECUTING = "executing"
    VERIFYING = "verifying"
    MEMORY_UPDATE = "memory_update"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class TaskRequest:
    id: str
    user_input: str
    priority: TaskPriority = TaskPriority.MEDIUM
    context: Dict[str, Any] = field(default_factory=dict)
    requires_verification: bool = True
    update_memory: bool = True


@dataclass
class TaskResult:
    success: bool
    result: Any
    reasoning: List[str]
    tools_used: List[str]
    execution_time: float
    error: Optional[str] = None


@dataclass
class PipelineStep:
    name: str
    status: TaskStatus
    started_at: datetime
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None


class UnifiedTaskExecutor:
    """Unified task execution pipeline for all requests."""
    
    def __init__(self):
        self._pipeline_steps: List[PipelineStep] = []
        self._current_task: Optional[TaskRequest] = None
        self._context = get_global_context()
        self._event_bus = get_event_bus()
        
        # Pipeline handlers
        self._handlers: Dict[str, Callable] = {
            "understanding": self._handle_understanding,
            "planning": self._handle_planning,
            "tool_selection": self._handle_tool_selection,
            "execution": self._handle_execution,
            "verification": self._handle_verification,
            "memory_update": self._handle_memory_update,
        }
        
        logger.info("Unified Task Executor initialized")
    
    async def execute_task(self, request: TaskRequest) -> TaskResult:
        """Execute a task through the unified pipeline."""
        self._current_task = request
        start_time = datetime.now()
        reasoning = []
        tools_used = []
        
        try:
            # Publish task started event
            await self._event_bus.publish_sync(
                EventType.TASK_STARTED,
                {"task_id": request.id, "user_input": request.user_input},
                "task_executor"
            )
            
            # Set in global context
            task_info = TaskInfo(
                id=request.id,
                description=request.user_input,
                status="pending",
                started_at=start_time,
            )
            await self._context.set_current_task(task_info)
            
            # Execute pipeline steps
            for step_name in self._handlers.keys():
                step = PipelineStep(
                    name=step_name,
                    status=TaskStatus.PENDING,
                    started_at=datetime.now(),
                )
                self._pipeline_steps.append(step)
                
                try:
                    # Update context state
                    if step_name == "planning":
                        await self._context.set_thinking_state("planning")
                    elif step_name == "tool_selection":
                        await self._context.set_thinking_state("tool_selection")
                    elif step_name == "execution":
                        await self._context.set_thinking_state("executing")
                    elif step_name == "verification":
                        await self._context.set_thinking_state("verifying")
                    
                    # Execute step
                    handler = self._handlers[step_name]
                    step_result = await handler(request, reasoning, tools_used)
                    
                    step.status = TaskStatus.COMPLETED
                    step.completed_at = datetime.now()
                    step.result = step_result
                    
                    reasoning.append(f"{step_name}: {step_result}")
                    
                    # Publish progress event
                    await self._event_bus.publish_sync(
                        EventType.TASK_PROGRESS,
                        {
                            "task_id": request.id,
                            "step": step_name,
                            "progress": len(self._pipeline_steps) / len(self._handlers),
                        },
                        "task_executor"
                    )
                    
                except Exception as e:
                    step.status = TaskStatus.FAILED
                    step.completed_at = datetime.now()
                    step.error = str(e)
                    logger.error(f"Pipeline step {step_name} failed: {e}")
                    raise
            
            # Mark task as complete
            execution_time = (datetime.now() - start_time).total_seconds()
            await self._context.complete_current_task()
            
            # Publish task finished event
            await self._event_bus.publish_sync(
                EventType.TASK_FINISHED,
                {"task_id": request.id, "execution_time": execution_time},
                "task_executor"
            )
            
            return TaskResult(
                success=True,
                result=self._pipeline_steps[-1].result,
                reasoning=reasoning,
                tools_used=tools_used,
                execution_time=execution_time,
            )
            
        except Exception as e:
            execution_time = (datetime.now() - start_time).total_seconds()
            await self._context.complete_current_task(error=str(e))
            
            # Publish task failed event
            await self._event_bus.publish_sync(
                EventType.TASK_FAILED,
                {"task_id": request.id, "error": str(e)},
                "task_executor"
            )
            
            return TaskResult(
                success=False,
                result=None,
                reasoning=reasoning,
                tools_used=tools_used,
                execution_time=execution_time,
                error=str(e),
            )
            
        finally:
            self._current_task = None
            self._pipeline_steps = []
            await self._context.set_thinking_state("idle")
    
    async def _handle_understanding(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 1: Understanding - Parse and understand user input."""
        await self._context.set_thinking_state("reasoning")
        await self._context.add_thinking_step("Understanding user input")
        
        # Get full context
        context = await self._context.get_full_context()
        
        # Understanding logic (placeholder - would use LLM)
        understanding = f"Understood: {request.user_input}"
        
        logger.info(f"Understanding: {understanding}")
        return understanding
    
    async def _handle_planning(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 2: Planning - Break down task into steps."""
        await self._context.set_thinking_state("planning")
        await self._context.add_thinking_step("Planning task execution")
        
        # Planning logic (placeholder - would use planner service)
        plan = "Task plan created"
        
        logger.info(f"Planning: {plan}")
        return plan
    
    async def _handle_tool_selection(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 3: Tool Selection - Select appropriate tools."""
        await self._context.set_thinking_state("tool_selection")
        await self._context.add_thinking_step("Selecting tools")
        
        # Tool selection logic (placeholder - would use tool selector)
        selected_tools = ["tool1", "tool2"]
        tools_used.extend(selected_tools)
        
        logger.info(f"Tool selection: {selected_tools}")
        return f"Selected tools: {selected_tools}"
    
    async def _handle_execution(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 4: Execution - Execute the task with selected tools."""
        await self._context.set_thinking_state("executing")
        await self._context.add_thinking_step("Executing task")
        
        # Execution logic (placeholder - would execute tools)
        result = "Task executed successfully"
        
        logger.info(f"Execution: {result}")
        return result
    
    async def _handle_verification(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 5: Verification - Verify the result."""
        await self._context.set_thinking_state("verifying")
        await self._context.add_thinking_step("Verifying result")
        
        if not request.requires_verification:
            return "Verification skipped"
        
        # Verification logic (placeholder)
        verified = True
        
        logger.info(f"Verification: {'passed' if verified else 'failed'}")
        return "Verification passed" if verified else "Verification failed"
    
    async def _handle_memory_update(
        self, 
        request: TaskRequest, 
        reasoning: List[str], 
        tools_used: List[str]
    ) -> str:
        """Step 6: Memory Update - Update memory with new information."""
        await self._context.set_thinking_state("reasoning")
        await self._context.add_thinking_step("Updating memory")
        
        if not request.update_memory:
            return "Memory update skipped"
        
        # Memory update logic (placeholder - would use memory service)
        memory_updated = True
        
        # Publish memory updated event
        if memory_updated:
            await self._event_bus.publish_sync(
                EventType.MEMORY_UPDATED,
                {"task_id": request.id},
                "task_executor"
            )
        
        logger.info(f"Memory update: {'success' if memory_updated else 'failed'}")
        return "Memory updated" if memory_updated else "Memory update failed"
    
    async def cancel_task(self, task_id: str) -> bool:
        """Cancel a running task."""
        # Placeholder - would implement cancellation
        await self._event_bus.publish_sync(
            EventType.TASK_FAILED,
            {"task_id": task_id, "error": "cancelled"},
            "task_executor"
        )
        return True
    
    def get_pipeline_status(self) -> List[Dict[str, Any]]:
        """Get current pipeline status."""
        return [
            {
                "name": step.name,
                "status": step.status,
                "started_at": step.started_at.isoformat(),
                "completed_at": step.completed_at.isoformat() if step.completed_at else None,
                "error": step.error,
            }
            for step in self._pipeline_steps
        ]


# Singleton instance
_task_executor: Optional[UnifiedTaskExecutor] = None


def get_task_executor() -> UnifiedTaskExecutor:
    """Get or create task executor singleton."""
    global _task_executor
    if _task_executor is None:
        _task_executor = UnifiedTaskExecutor()
    return _task_executor
