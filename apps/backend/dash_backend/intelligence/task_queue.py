"""Task Queue - Task scheduling, execution, and retry logic."""

from __future__ import annotations

import uuid
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio
from collections import deque

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class TaskPriority(Enum):
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4


@dataclass
class Task:
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    name: str = ""
    description: str = ""
    handler: Optional[Callable] = None
    parameters: Dict[str, Any] = field(default_factory=dict)
    status: TaskStatus = TaskStatus.PENDING
    priority: TaskPriority = TaskPriority.NORMAL
    retry_count: int = 0
    max_retries: int = 3
    retry_delay: float = 1.0
    timeout: float = 30.0
    scheduled_at: Optional[datetime] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


class TaskQueue:
    """Manages task scheduling, execution, and retry logic."""
    
    def __init__(self, max_concurrent_tasks: int = 10):
        self.tasks: Dict[str, Task] = {}
        self.pending_queue: deque[str] = deque()
        self.running_tasks: Dict[str, asyncio.Task] = {}
        self.max_concurrent_tasks = max_concurrent_tasks
        self.is_running = False
        self.task_handlers: Dict[str, Callable] = {}
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a task handler."""
        self.task_handlers[name] = handler
        logger.info(f"Registered task handler: {name}")
    
    def add_task(self, task: Task) -> str:
        """Add a task to the queue."""
        self.tasks[task.id] = task
        self.pending_queue.append(task.id)
        logger.info(f"Added task to queue: {task.name} ({task.id})")
        return task.id
    
    async def execute_task(self, task: Task) -> Any:
        """Execute a single task with retry logic."""
        task.status = TaskStatus.RUNNING
        task.started_at = datetime.utcnow()
        
        logger.info(f"Executing task: {task.name} ({task.id})")
        
        retries = 0
        while retries <= task.max_retries:
            try:
                if task.handler:
                    # Execute handler directly
                    result = await asyncio.wait_for(
                        task.handler(**task.parameters),
                        timeout=task.timeout
                    )
                elif task.name in self.task_handlers:
                    # Execute registered handler
                    handler = self.task_handlers[task.name]
                    result = await asyncio.wait_for(
                        handler(**task.parameters),
                        timeout=task.timeout
                    )
                else:
                    raise ValueError(f"No handler found for task: {task.name}")
                
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = datetime.utcnow()
                logger.info(f"Task completed: {task.name} ({task.id})")
                return result
            
            except asyncio.TimeoutError:
                retries += 1
                if retries > task.max_retries:
                    task.status = TaskStatus.FAILED
                    task.error = f"Task timed out after {task.timeout}s"
                    task.completed_at = datetime.utcnow()
                    logger.error(f"Task failed (timeout): {task.name} ({task.id})")
                    raise Exception(task.error)
                
                task.status = TaskStatus.RETRYING
                task.retry_count = retries
                logger.warning(f"Task retry {retries}/{task.max_retries}: {task.name}")
                await asyncio.sleep(task.retry_delay * retries)
            
            except Exception as e:
                retries += 1
                if retries > task.max_retries:
                    task.status = TaskStatus.FAILED
                    task.error = str(e)
                    task.completed_at = datetime.utcnow()
                    logger.error(f"Task failed: {task.name} ({task.id}): {e}")
                    raise
                
                task.status = TaskStatus.RETRYING
                task.retry_count = retries
                logger.warning(f"Task retry {retries}/{task.max_retries}: {task.name}: {e}")
                await asyncio.sleep(task.retry_delay * retries)
    
    async def start(self) -> None:
        """Start the task queue processor."""
        self.is_running = True
        logger.info("Task queue started")
        
        while self.is_running:
            try:
                # Check if we can start more tasks
                if len(self.running_tasks) < self.max_concurrent_tasks and self.pending_queue:
                    task_id = self.pending_queue.popleft()
                    task = self.tasks[task_id]
                    
                    if task.scheduled_at and task.scheduled_at > datetime.utcnow():
                        # Re-queue if not yet scheduled
                        self.pending_queue.appendleft(task_id)
                        await asyncio.sleep(0.1)
                        continue
                    
                    # Start task execution
                    async_task = asyncio.create_task(
                        self._run_task(task),
                        name=f"task_{task_id}"
                    )
                    self.running_tasks[task_id] = async_task
                
                # Clean up completed tasks
                completed_tasks = []
                for task_id, async_task in self.running_tasks.items():
                    if async_task.done():
                        completed_tasks.append(task_id)
                
                for task_id in completed_tasks:
                    del self.running_tasks[task_id]
                
                await asyncio.sleep(0.1)
            
            except Exception as e:
                logger.error(f"Task queue error: {e}")
                await asyncio.sleep(1)
    
    async def _run_task(self, task: Task) -> None:
        """Run a task and handle completion."""
        try:
            await self.execute_task(task)
        except Exception as e:
            logger.error(f"Task execution failed: {task.name}: {e}")
    
    async def stop(self) -> None:
        """Stop the task queue."""
        self.is_running = False
        
        # Cancel all running tasks
        for task_id, async_task in self.running_tasks.items():
            async_task.cancel()
            self.tasks[task_id].status = TaskStatus.CANCELLED
        
        self.running_tasks.clear()
        logger.info("Task queue stopped")
    
    def cancel_task(self, task_id: str) -> bool:
        """Cancel a specific task."""
        if task_id not in self.tasks:
            return False
        
        task = self.tasks[task_id]
        
        if task.status == TaskStatus.RUNNING and task_id in self.running_tasks:
            self.running_tasks[task_id].cancel()
            del self.running_tasks[task_id]
        
        task.status = TaskStatus.CANCELLED
        logger.info(f"Cancelled task: {task.name} ({task_id})")
        return True
    
    def get_task(self, task_id: str) -> Optional[Task]:
        """Get a task by ID."""
        return self.tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[Task]:
        """List all tasks, optionally filtered by status."""
        if status:
            return [t for t in self.tasks.values() if t.status == status]
        return list(self.tasks.values())
    
    def get_queue_stats(self) -> Dict[str, int]:
        """Get queue statistics."""
        return {
            "pending": len(self.pending_queue),
            "running": len(self.running_tasks),
            "total": len(self.tasks),
            "completed": len([t for t in self.tasks.values() if t.status == TaskStatus.COMPLETED]),
            "failed": len([t for t in self.tasks.values() if t.status == TaskStatus.FAILED]),
        }
