"""File Watcher - Monitor file and folder changes for intelligent automation."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FileWatcher:
    def __init__(self, poll_interval: float = 2.0):
        self._poll_interval = poll_interval
        self._watched: Dict[str, Set[str]] = {}
        self._callbacks: Dict[str, List[Callable]] = {}
        self._running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("FileWatcher started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def watch(self, path: str, callback: Callable) -> None:
        p = str(Path(path).resolve())
        if p not in self._callbacks:
            self._callbacks[p] = []
            self._watched[p] = set()
        self._callbacks[p].append(callback)

    def unwatch(self, path: str) -> None:
        p = str(Path(path).resolve())
        self._callbacks.pop(p, None)
        self._watched.pop(p, None)

    async def _watch_loop(self) -> None:
        while self._running:
            try:
                for path, callbacks in self._callbacks.items():
                    current = set()
                    p = Path(path)
                    if p.is_file():
                        current.add(str(p))
                    elif p.is_dir():
                        for f in p.rglob("*"):
                            if f.is_file():
                                current.add(str(f))
                    old = self._watched.get(path, set())
                    new_files = current - old
                    deleted = old - current
                    if new_files:
                        for cb in callbacks:
                            try:
                                cb({"type": "created", "files": list(new_files), "path": path})
                            except Exception:
                                pass
                    if deleted:
                        for cb in callbacks:
                            try:
                                cb({"type": "deleted", "files": list(deleted), "path": path})
                            except Exception:
                                pass
                    self._watched[path] = current
                await asyncio.sleep(self._poll_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(self._poll_interval)


_file_watcher: Optional[FileWatcher] = None


def get_file_watcher() -> FileWatcher:
    global _file_watcher
    if _file_watcher is None:
        _file_watcher = FileWatcher()
    return _file_watcher
