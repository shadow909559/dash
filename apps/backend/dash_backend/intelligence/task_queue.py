"""Task Queue - Task scheduling, execution, and retry logic.

Timezone policy (decisions.md #141): every datetime this module stores or
compares is **timezone-aware UTC**. ``enqueue``/``add_task`` normalize
whatever the caller supplies (aware datetime in any zone, naive datetime
assumed local, ISO 8601 string, epoch seconds/milliseconds) so an LLM- or
API-supplied payload can never crash the queue loop with a naive/aware
``TypeError`` — that class of bug previously dropped popped tasks
silently and made the scheduler agent report fabricated success.
"""

from __future__ import annotations

import uuid
import inspect
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta, timezone
import asyncio
from collections import deque

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


def _utcnow() -> datetime:
    """Aware-UTC now — replaces the deprecated ``datetime.utcnow()``."""
    return datetime.now(timezone.utc)


def normalize_to_utc(value: Any) -> Optional[datetime]:
    """Coerce arbitrary caller-supplied schedule input to aware UTC.

    Accepted: aware datetime (converted), naive datetime (assumed LOCAL
    time — converted), ISO 8601 string (with or without offset), epoch
    seconds or milliseconds. Returns None for None/empty input. Raises
    ValueError for garbage so callers can fail honestly at enqueue time
    instead of the queue loop crashing at pop time.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            # Naive: interpret as local wall time (the only sane reading of
            # a naive datetime from a human/LLM payload).
            return value.astimezone()
        return value.astimezone(timezone.utc)
    if isinstance(value, (int, float)):
        # Epoch; > 1e12 means milliseconds (JS-style timestamps).
        seconds = value / 1000.0 if abs(value) > 1e12 else float(value)
        return datetime.fromtimestamp(seconds, tz=timezone.utc)
    if isinstance(value, str):
        text = value.strip()
        if not text:
            return None
        if text.replace(".", "").replace("-", "").isdigit():
            return normalize_to_utc(float(text))
        if text.endswith("Z"):
            text = text[:-1] + "+00:00"
        try:
            parsed = datetime.fromisoformat(text)
        except ValueError:
            raise ValueError(f"unparseable schedule time: {value!r}") from None
        return normalize_to_utc(parsed)
    raise ValueError(f"unsupported schedule time type: {type(value).__name__}")



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
        self._runner_task: Optional[asyncio.Task] = None
    
    def register_handler(self, name: str, handler: Callable) -> None:
        """Register a task handler."""
        self.task_handlers[name] = handler
        logger.info(f"Registered task handler: {name}")
    
    def add_task(self, task: Task) -> str:
        """Add a task to the queue (schedule input normalized to UTC)."""
        task.scheduled_at = normalize_to_utc(task.scheduled_at)
        self.tasks[task.id] = task
        self.pending_queue.append(task.id)
        logger.info(f"Added task to queue: {task.name} ({task.id})")
        return task.id

    async def enqueue(
        self,
        task_spec: Dict[str, Any],
        *,
        priority: TaskPriority = TaskPriority.NORMAL,
        scheduled_at: Any = None,
        handler: Optional[Callable] = None,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Create and queue a task from a plain payload.

        ``scheduled_at`` accepts anything ``normalize_to_utc`` understands
        (datetime/ISO string/epoch). Invalid schedule input raises
        ``ValueError`` HERE — honest failure at the API boundary, never a
        silent drop or a fabricated success downstream.
        """
        when = normalize_to_utc(scheduled_at)
        if scheduled_at is not None and when is None:
            raise ValueError("empty schedule time")
        task = Task(
            name=str(task_spec.get("name") or task_spec.get("description") or "unnamed task"),
            description=str(task_spec.get("description") or ""),
            handler=handler,
            parameters=parameters if parameters is not None else dict(task_spec.get("parameters") or {}),
            priority=priority,
            scheduled_at=when,
        )
        return self.add_task(task)

    
    async def execute_task(self, task: Task) -> Any:
        """Execute a single task with retry logic."""
        task.status = TaskStatus.RUNNING
        task.started_at = _utcnow()
        
        logger.info(f"Executing task: {task.name} ({task.id})")
        
        retries = 0
        while retries <= task.max_retries:
            try:
                if task.handler:
                    # Execute handler directly
                    result = await self._invoke(task.handler, task)
                elif task.name in self.task_handlers:
                    # Execute registered handler
                    result = await self._invoke(
                        self.task_handlers[task.name], task
                    )
                else:
                    raise ValueError(f"No handler found for task: {task.name}")
                
                task.result = result
                task.status = TaskStatus.COMPLETED
                task.completed_at = _utcnow()
                logger.info(f"Task completed: {task.name} ({task.id})")
                return result
            
            except asyncio.TimeoutError:
                retries += 1
                if retries > task.max_retries:
                    task.status = TaskStatus.FAILED
                    task.error = f"Task timed out after {task.timeout}s"
                    task.completed_at = _utcnow()
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
                    task.completed_at = _utcnow()
                    logger.error(f"Task failed: {task.name} ({task.id}): {e}")
                    raise
                
                task.status = TaskStatus.RETRYING
                task.retry_count = retries
                logger.warning(f"Task retry {retries}/{task.max_retries}: {task.name}: {e}")
                await asyncio.sleep(task.retry_delay * retries)
    
    async def _invoke(self, handler: Callable[..., Any], task: Task) -> Any:
        """Call a handler that may be sync or async.

        ``Task.handler`` is declared as plain ``Callable``, so both forms are
        legal. Awaitable results get the task timeout via ``wait_for``; sync
        results are returned directly (a sync call cannot be interrupted
        without a thread — the timeout applies to async handlers only).
        """
        outcome = handler(**task.parameters)
        if inspect.isawaitable(outcome):
            return await asyncio.wait_for(outcome, timeout=task.timeout)
        return outcome

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
                    
                    if task.scheduled_at and task.scheduled_at > _utcnow():
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
        """Stop the task queue, cancel in-flight tasks, and join the runner."""
        self.is_running = False

        runner = self._runner_task
        if (
            runner is not None
            and runner is not asyncio.current_task()
            and not runner.done()
        ):
            runner.cancel()
            try:
                await runner
            except asyncio.CancelledError:
                pass

        # Cancel in-flight tasks; already-finished wrappers (done) must NOT
        # have their real completion status overwritten with CANCELLED.
        for task_id, async_task in self.running_tasks.items():
            if async_task.done():
                continue
            async_task.cancel()
            self.tasks[task_id].status = TaskStatus.CANCELLED

        self.running_tasks.clear()
        logger.info("Task queue stopped")

    async def ensure_started(self) -> None:
        """Idempotently start the queue loop on the current event loop.

        Safe to call repeatedly: a healthy runner makes this a no-op. If a
        previous runner died (its event loop was torn down), the stale
        ``is_running`` flag is detected via the dead task and a new runner
        starts — the queue can never silently stop processing.
        """
        if (
            self.is_running
            and self._runner_task is not None
            and not self._runner_task.done()
        ):
            return
        if self.is_running and self._runner_task is not None and self._runner_task.done():
            logger.warning("Task queue runner died; restarting it")
        self._runner_task = asyncio.create_task(
            self.start(), name="task_queue_runner"
 )
    
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


# ── Process-wide shared instances ────────────────────────────
# Both engines are stateful registries; constructing them per call (the old
# scheduler-agent behavior) guaranteed scheduled tasks and created workflows
# could never survive to execution time. These getters return one instance
# per process and rebind when the running event loop changes, because an
# asyncio Task (the queue runner) is bound to the loop that spawned it — a
# stale singleton after a loop restart would hold ``is_running=True`` while
# nothing processes anything.

_shared_queue: Optional["TaskQueue"] = None
_shared_queue_loop: Optional[asyncio.AbstractEventLoop] = None


def get_shared_task_queue() -> TaskQueue:
    """Return the process-wide TaskQueue, rebound on event-loop change.

    On a loop change the new instance inherits registered handlers and all
    tasks; tasks that were mid-flight under the dead loop are reset to
    PENDING and re-queued so they still run (at-least-once semantics).
    """
    global _shared_queue, _shared_queue_loop
    try:
        loop: Optional[asyncio.AbstractEventLoop] = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if _shared_queue is not None and loop is not None and _shared_queue_loop is not loop:
        old = _shared_queue
        fresh = TaskQueue(max_concurrent_tasks=old.max_concurrent_tasks)
        fresh.task_handlers.update(old.task_handlers)
        carried = 0
        for task in old.tasks.values():
            if task.status in (TaskStatus.RUNNING, TaskStatus.RETRYING):
                task.status = TaskStatus.PENDING
            fresh.tasks[task.id] = task
            if task.status == TaskStatus.PENDING:
                fresh.pending_queue.append(task.id)
                carried += 1
        logger.info(
            "Event loop changed: rebound shared task queue (%d tasks, %d re-queued)",
            len(fresh.tasks),
            carried,
        )
        _shared_queue = fresh
        _shared_queue_loop = loop

    if _shared_queue is None:
        _shared_queue = TaskQueue()
        _shared_queue_loop = loop
    return _shared_queue
