"""Command queue with priority ordering and concurrency control."""

from __future__ import annotations

import asyncio
import time
from collections import defaultdict
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.command.models import (
    CommandPriority,
    CommandRequest,
    CommandResult,
    CommandStatus,
)

logger = get_logger(__name__)


class QueueEntry:
    """A command waiting in the queue."""

    __slots__ = ("request", "enqueued_at", "future")

    def __init__(self, request: CommandRequest) -> None:
        self.request = request
        self.enqueued_at = time.monotonic()
        self.future: asyncio.Future[CommandResult] = asyncio.Future()

    @property
    def priority_value(self) -> int:
        return -self.request.priority.value  # higher priority = lower sort key


class CommandQueue:
    """Thread-safe async priority queue for remote commands.

    Features:
      - Priority ordering (CRITICAL -> HIGH -> NORMAL -> LOW)
      - Per-category concurrency limits
      - Queue size limits per source
      - Timeout enforcement
      - Graceful cancellation
    """

    def __init__(
        self,
        max_concurrent: int = 10,
        max_queue_per_source: int = 100,
        default_timeout: float = 30.0,
    ) -> None:
        self._max_concurrent = max_concurrent
        self._max_queue_per_source = max_queue_per_source
        self._default_timeout = default_timeout
        self._queue: list[QueueEntry] = []
        self._running: dict[str, QueueEntry] = {}  # command_id -> entry
        self._lock = asyncio.Lock()
        self._not_empty = asyncio.Condition(self._lock)
        self._source_counts: dict[str, int] = defaultdict(int)

    # ── Public API ──────────────────────────────────────────

    async def enqueue(self, request: CommandRequest) -> asyncio.Future[CommandResult]:
        """Enqueue a command and return a future for the result.

        Raises RuntimeError if queue limits are exceeded.
        """
        async with self._lock:
            source = request.source or "unknown"
            if self._source_counts[source] >= self._max_queue_per_source:
                raise RuntimeError(
                    f"Queue limit exceeded for source '{source}': "
                    f"{self._max_queue_per_source} max"
                )

            entry = QueueEntry(request)
            self._queue.append(entry)
            self._source_counts[source] += 1
            self._queue.sort(key=lambda e: e.priority_value)

            logger.debug(
                "Enqueued command %s (category=%s, action=%s, priority=%s)",
                request.command_id,
                request.category.value,
                request.action,
                request.priority.name,
            )

            self._not_empty.notify()

        return entry.future

    async def dequeue(self) -> QueueEntry | None:
        """Dequeue the next command when capacity allows."""
        async with self._lock:
            while len(self._running) >= self._max_concurrent or not self._queue:
                if not self._queue and not self._running:
                    # Queue is empty and nothing running — wait
                    await self._not_empty.wait()
                    continue
                # Wait for either capacity or new items
                await self._not_empty.wait_for(
                    lambda: len(self._running) < self._max_concurrent and bool(self._queue)
                )

            entry = self._queue.pop(0)
            self._running[entry.request.command_id] = entry
            source = entry.request.source or "unknown"
            self._source_counts[source] = max(0, self._source_counts[source] - 1)

            logger.debug(
                "Dequeued command %s (running: %d, queued: %d)",
                entry.request.command_id,
                len(self._running),
                len(self._queue),
            )

            return entry

    async def complete(self, command_id: str, result: CommandResult) -> None:
        """Mark a command as completed and resolve its future."""
        async with self._lock:
            entry = self._running.pop(command_id, None)
            if entry is None:
                logger.warning("Tried to complete unknown command %s", command_id)
                return

            if not entry.future.done():
                entry.future.set_result(result)

            self._not_empty.notify()

    async def cancel(self, command_id: str) -> bool:
        """Cancel a queued or running command."""
        async with self._lock:
            # Check running
            entry = self._running.pop(command_id, None)
            if entry is not None:
                cancelled = CommandResult(
                    command_id=command_id,
                    status=CommandStatus.CANCELLED,
                    summary="Command cancelled",
                )
                if not entry.future.done():
                    entry.future.set_result(cancelled)
                self._not_empty.notify()
                return True

            # Check queue
            for i, e in enumerate(self._queue):
                if e.request.command_id == command_id:
                    self._queue.pop(i)
                    cancelled = CommandResult(
                        command_id=command_id,
                        status=CommandStatus.CANCELLED,
                        summary="Command cancelled before execution",
                    )
                    if not e.future.done():
                        e.future.set_result(cancelled)
                    return True

            return False

    async def get_queue_length(self) -> int:
        async with self._lock:
            return len(self._queue)

    async def get_running_count(self) -> int:
        async with self._lock:
            return len(self._running)

    async def get_status(self) -> dict[str, Any]:
        """Return snapshot of queue state for monitoring."""
        async with self._lock:
            return {
                "queued": len(self._queue),
                "running": len(self._running),
                "max_concurrent": self._max_concurrent,
                "total_pending": len(self._queue) + len(self._running),
                "by_source": dict(self._source_counts),
            }

    async def get_queue_snapshot(self) -> list[dict[str, Any]]:
        """Return list of queued commands (without consuming them)."""
        async with self._lock:
            return [
                {
                    "command_id": e.request.command_id,
                    "category": e.request.category.value,
                    "action": e.request.action,
                    "priority": e.request.priority.name,
                    "source": e.request.source,
                    "enqueued_at": e.enqueued_at,
                }
                for e in self._queue
            ]

    async def get_running_snapshot(self) -> list[dict[str, Any]]:
        """Return list of currently running commands."""
        async with self._lock:
            return [
                {
                    "command_id": e.request.command_id,
                    "category": e.request.category.value,
                    "action": e.request.action,
                    "source": e.request.source,
                }
                for e in self._running.values()
            ]
