"""Background Task Manager - Autonomous background task execution for DASH AI OS."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


class TaskPriority(Enum):
    LOW = 0
    NORMAL = 1
    HIGH = 2
    CRITICAL = 3


class TaskStatus(Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class BackgroundTask:
    id: str = ""
    name: str = ""
    description: str = ""
    priority: TaskPriority = TaskPriority.NORMAL
    status: TaskStatus = TaskStatus.PENDING
    progress: float = 0.0
    result: Any = None
    error: str = ""
    created_at: float = 0.0
    started_at: float = 0.0
    completed_at: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def __post_init__(self):
        if not self.id:
            self.id = str(uuid.uuid4())
        if not self.created_at:
            self.created_at = time.time()


class BackgroundTaskManager:
    def __init__(self, max_concurrent: int = 5):
        self._max_concurrent = max_concurrent
        self._tasks: Dict[str, BackgroundTask] = {}
        self._queue: asyncio.Queue = asyncio.Queue()
        self._running: Dict[str, asyncio.Task] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._worker_task: Optional[asyncio.Task] = None
        self._active = False
    
    async def start(self) -> None:
        self._active = True
        self._worker_task = asyncio.create_task(self._worker_loop())
        logger.info("BackgroundTaskManager started")
    
    async def stop(self) -> None:
        self._active = False
        if self._worker_task:
            self._worker_task.cancel()
            try:
                await self._worker_task
            except asyncio.CancelledError:
                pass
        # Cancel running tasks
        for task in self._running.values():
            task.cancel()
        logger.info("BackgroundTaskManager stopped")
    
    async def submit(self, name: str, coro, priority: TaskPriority = TaskPriority.NORMAL,
                     description: str = "") -> str:
        task = BackgroundTask(name=name, description=description, priority=priority)
        self._tasks[task.id] = task
        await self._queue.put((task, coro))
        return task.id
    
    async def _worker_loop(self) -> None:
        while self._active:
            try:
                task, coro = await asyncio.wait_for(self._queue.get(), timeout=1.0)
                
                while len(self._running) >= self._max_concurrent:
                    await asyncio.sleep(0.5)
                
                task.status = TaskStatus.RUNNING
                task.started_at = time.time()
                
                async def run_task(task_id: str, c):
                    bt = self._tasks[task_id]
                    try:
                        result = await c
                        bt.status = TaskStatus.COMPLETED
                        bt.result = result
                        bt.progress = 1.0
                        bt.completed_at = time.time()
                        self._notify(task_id, "completed", result)
                    except asyncio.CancelledError:
                        bt.status = TaskStatus.CANCELLED
                        bt.completed_at = time.time()
                    except Exception as exc:
                        bt.status = TaskStatus.FAILED
                        bt.error = str(exc)
                        bt.completed_at = time.time()
                        self._notify(task_id, "failed", str(exc))
                    finally:
                        self._running.pop(task_id, None)
                
                t = asyncio.create_task(run_task(task.id, coro))
                self._running[task.id] = t
                
            except asyncio.TimeoutError:
                continue
            except Exception as exc:
                logger.error("Worker error: %s", exc)
    
    def get_task(self, task_id: str) -> Optional[BackgroundTask]:
        return self._tasks.get(task_id)
    
    def list_tasks(self, status: Optional[TaskStatus] = None) -> List[BackgroundTask]:
        if status:
            return [t for t in self._tasks.values() if t.status == status]
        return list(self._tasks.values())
    
    async def cancel_task(self, task_id: str) -> bool:
        if task_id in self._running:
            self._running[task_id].cancel()
            return True
        return False
    
    def on_event(self, task_id: str, callback: Callable) -> None:
        if task_id not in self._callbacks:
            self._callbacks[task_id] = []
        self._callbacks[task_id].append(callback)
    
    def _notify(self, task_id: str, event: str, data: Any) -> None:
        for cb in self._callbacks.get(task_id, []):
            try:
                cb(event, data)
            except Exception:
                pass


_background_task_manager: Optional[BackgroundTaskManager] = None


def get_background_task_manager() -> BackgroundTaskManager:
    global _background_task_manager
    if _background_task_manager is None:
        _background_task_manager = BackgroundTaskManager()
    return _background_task_manager
