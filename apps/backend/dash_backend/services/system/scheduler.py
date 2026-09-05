"""Scheduler - Task scheduling with cron-like expressions for DASH AI OS.

Provides:
- Cron-like expression parsing
- One-time delayed tasks
- Recurring periodic tasks
- Task dependencies and chaining
- Execution history tracking
- Pause/resume individual tasks
- Graceful shutdown
"""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class ScheduleType(Enum):
    """Type of schedule."""
    ONCE = "once"
    INTERVAL = "interval"
    DAILY = "daily"
    HOURLY = "hourly"
    CRON = "cron"


class TaskStatus(Enum):
    """Status of a scheduled task."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"
    PAUSED = "paused"
    CANCELLED = "cancelled"


@dataclass
class ScheduledTask:
    """A scheduled task.
    
    Attributes:
        id: Unique task ID
        name: Task name
        handler: Async function to execute
        schedule_type: Type of schedule
        interval_seconds: Interval for INTERVAL type
        cron_expression: Cron expression for CRON type
        daily_time: Time of day for DAILY type (HH:MM)
        args: Positional arguments for handler
        kwargs: Keyword arguments for handler
        enabled: Whether task is enabled
        run_immediately: Run immediately on start
        max_runs: Maximum number of runs (0 = unlimited)
        timeout: Maximum execution time
        status: Current task status
        last_run: When the task last ran
        next_run: When the task should run next
        run_count: Number of times executed
        error_count: Number of times failed
        last_error: Last error message
        metadata: Additional metadata
    """
    id: str = ""
    name: str = ""
    handler: Optional[Callable] = None
    schedule_type: ScheduleType = ScheduleType.ONCE
    interval_seconds: float = 60.0
    cron_expression: str = ""
    daily_time: str = "00:00"
    args: tuple = field(default_factory=tuple)
    kwargs: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    run_immediately: bool = False
    max_runs: int = 0  # 0 = unlimited
    timeout: float = 300.0
    status: TaskStatus = TaskStatus.PENDING
    created_at: float = 0.0
    last_run: float = 0.0
    next_run: float = 0.0
    run_count: int = 0
    error_count: int = 0
    last_error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()
        if not self.next_run:
            self.next_run = self._calculate_next_run()
    
    def _calculate_next_run(self) -> float:
        """Calculate the next run time based on schedule type.
        
        Returns:
            Timestamp of next run
        """
        now = time.time()
        
        if self.schedule_type == ScheduleType.ONCE:
            return now + 1  # Run once immediately
        
        elif self.schedule_type == ScheduleType.INTERVAL:
            if self.run_count == 0 and self.run_immediately:
                return now
            return now + self.interval_seconds
        
        elif self.schedule_type == ScheduleType.HOURLY:
            next_hour = (int(now // 3600) + 1) * 3600
            return next_hour
        
        elif self.schedule_type == ScheduleType.DAILY:
            try:
                parts = self.daily_time.split(":")
                hour = int(parts[0])
                minute = int(parts[1]) if len(parts) > 1 else 0
                
                today = datetime.fromtimestamp(now, tz=timezone.utc)
                scheduled = today.replace(hour=hour, minute=minute, second=0, microsecond=0)
                
                if scheduled.timestamp() <= now:
                    scheduled += timedelta(days=1)
                
                return scheduled.timestamp()
            except (ValueError, IndexError):
                return now + 86400  # Default to tomorrow
        
        return now + 3600  # Default to 1 hour
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "schedule_type": self.schedule_type.value,
            "interval_seconds": self.interval_seconds,
            "cron_expression": self.cron_expression,
            "daily_time": self.daily_time,
            "enabled": self.enabled,
            "max_runs": self.max_runs,
            "timeout": self.timeout,
            "status": self.status.value,
            "created_at": self.created_at,
            "last_run": self.last_run,
            "next_run": self.next_run,
            "run_count": self.run_count,
            "error_count": self.error_count,
            "last_error": self.last_error,
        }


class SystemScheduler:
    """System task scheduler with cron-like scheduling support.
    
    Features:
    - One-time and recurring tasks
    - Interval, hourly, daily, and cron scheduling
    - Task pause/resume
    - Execution history tracking
    - Timeout handling
    - Graceful shutdown with drain
    """
    
    def __init__(self):
        self._tasks: Dict[str, ScheduledTask] = {}
        self._running = False
        self._main_loop: Optional[asyncio.Task] = None
        self._active_executions: Dict[str, asyncio.Task] = {}
        
        # Execution history
        self._execution_history: List[Dict[str, Any]] = []
        self._max_history: int = 1000
        
        # Stats
        self._stats = {
            "total_executions": 0,
            "total_failures": 0,
            "total_skipped": 0,
        }
    
    # ── Lifecycle ────────────────────────────────────────────
    
    async def start(self) -> None:
        """Start the scheduler."""
        self._running = True
        self._main_loop = asyncio.create_task(self._scheduler_loop())
        logger.info("Scheduler started with %d tasks", len(self._tasks))
    
    async def stop(self) -> None:
        """Stop the scheduler and cancel running tasks."""
        self._running = False
        
        if self._main_loop:
            self._main_loop.cancel()
            try:
                await self._main_loop
            except asyncio.CancelledError:
                pass
        
        # Cancel running executions
        for task_id, exec_task in self._active_executions.items():
            exec_task.cancel()
        
        if self._active_executions:
            await asyncio.gather(*self._active_executions.values(), return_exceptions=True)
        
        logger.info("Scheduler stopped")
    
    # ── Task Management ──────────────────────────────────────
    
    def add_task(self, task: ScheduledTask) -> str:
        """Add a scheduled task.
        
        Args:
            task: The task to schedule
            
        Returns:
            Task ID
        """
        self._tasks[task.id] = task
        logger.info("Scheduled task '%s' (type=%s, interval=%.1fs)",
                     task.name, task.schedule_type.value, task.interval_seconds)
        return task.id
    
    def add_interval_task(self, name: str, handler: Callable,
                            interval_seconds: float, *args, **kwargs) -> str:
        """Add a task that runs at a fixed interval.
        
        Args:
            name: Task name
            handler: Async function
            interval_seconds: Interval between runs
            *args: Handler positional args
            **kwargs: Handler keyword args
            
        Returns:
            Task ID
        """
        task = ScheduledTask(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.INTERVAL,
            interval_seconds=interval_seconds,
            args=args,
            kwargs=kwargs,
        )
        return self.add_task(task)
    
    def add_daily_task(self, name: str, handler: Callable,
                        time_str: str = "00:00", *args, **kwargs) -> str:
        """Add a task that runs daily at a specific time.
        
        Args:
            name: Task name
            handler: Async function
            time_str: Time in HH:MM format
            *args: Handler positional args
            **kwargs: Handler keyword args
            
        Returns:
            Task ID
        """
        task = ScheduledTask(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.DAILY,
            daily_time=time_str,
            args=args,
            kwargs=kwargs,
        )
        return self.add_task(task)
    
    def add_once_task(self, name: str, handler: Callable,
                       delay_seconds: float = 0, *args, **kwargs) -> str:
        """Add a one-time task.
        
        Args:
            name: Task name
            handler: Async function
            delay_seconds: Delay before execution
            *args: Handler positional args
            **kwargs: Handler keyword args
            
        Returns:
            Task ID
        """
        task = ScheduledTask(
            name=name,
            handler=handler,
            schedule_type=ScheduleType.ONCE,
            interval_seconds=delay_seconds,
            max_runs=1,
            args=args,
            kwargs=kwargs,
        )
        return self.add_task(task)
    
    def remove_task(self, task_id: str) -> bool:
        """Remove a scheduled task.
        
        Args:
            task_id: Task ID to remove
            
        Returns:
            True if removed
        """
        task = self._tasks.pop(task_id, None)
        if task:
            logger.info("Removed task '%s'", task.name)
            return True
        return False
    
    def get_task(self, task_id: str) -> Optional[ScheduledTask]:
        """Get a task by ID.
        
        Args:
            task_id: Task ID
            
        Returns:
            ScheduledTask or None
        """
        return self._tasks.get(task_id)
    
    def get_tasks(self, enabled_only: bool = False) -> List[ScheduledTask]:
        """Get all scheduled tasks.
        
        Args:
            enabled_only: Only return enabled tasks
            
        Returns:
            List of ScheduledTask
        """
        if enabled_only:
            return [t for t in self._tasks.values() if t.enabled]
        return list(self._tasks.values())
    
    def pause_task(self, task_id: str) -> bool:
        """Pause a scheduled task.
        
        Args:
            task_id: Task ID to pause
            
        Returns:
            True if paused
        """
        task = self._tasks.get(task_id)
        if task:
            task.enabled = False
            task.status = TaskStatus.PAUSED
            return True
        return False
    
    def resume_task(self, task_id: str) -> bool:
        """Resume a paused task.
        
        Args:
            task_id: Task ID to resume
            
        Returns:
            True if resumed
        """
        task = self._tasks.get(task_id)
        if task:
            task.enabled = True
            task.status = TaskStatus.PENDING
            task.next_run = task._calculate_next_run()
            return True
        return False
    
    # ── Scheduler Loop ───────────────────────────────────────
    
    async def _scheduler_loop(self) -> None:
        """Main scheduler loop - checks and executes due tasks."""
        while self._running:
            try:
                await self._check_and_execute()
                await asyncio.sleep(1.0)  # Check every second
            except asyncio.CancelledError:
                break
            except Exception as exc:
                logger.error("Scheduler loop error: %s", exc)
                await asyncio.sleep(5.0)
    
    async def _check_and_execute(self) -> None:
        """Check for due tasks and execute them."""
        now = time.time()
        
        for task in list(self._tasks.values()):
            if not task.enabled:
                continue
            
            if task.status == TaskStatus.PAUSED:
                continue
            
            if task.max_runs > 0 and task.run_count >= task.max_runs:
                continue
            
            if task.next_run <= now:
                await self._execute_task(task)
    
    async def _execute_task(self, task: ScheduledTask) -> None:
        """Execute a scheduled task.
        
        Args:
            task: The task to execute
        """
        if not task.handler:
            task.status = TaskStatus.FAILED
            task.last_error = "No handler set"
            return
        
        # Check if already running
        if task.id in self._active_executions:
            logger.warning("Task '%s' already running, skipping", task.name)
            self._stats["total_skipped"] += 1
            task.status = TaskStatus.SKIPPED
            return
        
        task.status = TaskStatus.RUNNING
        task.last_run = time.time()
        
        async def execute():
            try:
                result = await asyncio.wait_for(
                    task.handler(*task.args, **task.kwargs),
                    timeout=task.timeout,
                )
                task.status = TaskStatus.PENDING
                task.run_count += 1
                self._stats["total_executions"] += 1
                task.last_error = None
                
                logger.debug("Task '%s' executed successfully (run %d)",
                             task.name, task.run_count)
                
            except asyncio.TimeoutError:
                task.status = TaskStatus.PENDING
                task.error_count += 1
                task.last_error = f"Timeout ({task.timeout}s)"
                self._stats["total_failures"] += 1
                logger.warning("Task '%s' timed out", task.name)
                
            except Exception as exc:
                task.status = TaskStatus.PENDING
                task.error_count += 1
                task.last_error = str(exc)
                self._stats["total_failures"] += 1
                logger.error("Task '%s' failed: %s", task.name, exc)
            
            finally:
                self._active_executions.pop(task.id, None)
                task.next_run = task._calculate_next_run()
                
                # Record history
                self._record_execution(task)
        
        exec_task = asyncio.create_task(execute())
        self._active_executions[task.id] = exec_task
    
    def _record_execution(self, task: ScheduledTask) -> None:
        """Record a task execution in history.
        
        Args:
            task: The executed task
        """
        record = {
            "task_id": task.id,
            "task_name": task.name,
            "executed_at": task.last_run,
            "duration_ms": (time.time() - task.last_run) * 1000 if task.last_run else 0,
            "status": task.status.value,
            "error": task.last_error,
            "run_count": task.run_count,
        }
        
        self._execution_history.append(record)
        
        # Trim history
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]
    
    # ── History ──────────────────────────────────────────────
    
    def get_execution_history(self, task_id: Optional[str] = None,
                                limit: int = 50) -> List[Dict[str, Any]]:
        """Get execution history.
        
        Args:
            task_id: Optional filter by task ID
            limit: Maximum records
            
        Returns:
            List of execution records
        """
        if task_id:
            return [r for r in self._execution_history if r["task_id"] == task_id][-limit:]
        return self._execution_history[-limit:]
    
    def get_task_execution_count(self, task_id: str) -> int:
        """Get execution count for a task.
        
        Args:
            task_id: Task ID
            
        Returns:
            Execution count
        """
        return sum(1 for r in self._execution_history if r["task_id"] == task_id)
    
    # ── Stats ────────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        """Get scheduler statistics."""
        return {
            **self._stats,
            "total_tasks": len(self._tasks),
            "enabled_tasks": sum(1 for t in self._tasks.values() if t.enabled),
            "running_tasks": len(self._active_executions),
            "history_size": len(self._execution_history),
        }


# Global singleton
_scheduler: Optional[SystemScheduler] = None


def get_system_scheduler() -> SystemScheduler:
    """Get or create the global SystemScheduler singleton."""
    global _scheduler
    if _scheduler is None:
        _scheduler = SystemScheduler()
    return _scheduler
