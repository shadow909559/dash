"""Task queue abstraction.

In-process queue abstraction used by the executor.
"""

from __future__ import annotations

import queue
from typing import Optional

from .models import Task


class TaskQueue:
    def __init__(self) -> None:
        self._q: queue.Queue[Task] = queue.Queue()

    def enqueue(self, task: Task) -> None:
        self._q.put(task)

    def dequeue(self, timeout_s: float | None = None) -> Optional[Task]:
        try:
            return self._q.get(timeout=timeout_s)
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._q.qsize()

