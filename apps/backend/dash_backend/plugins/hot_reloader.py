"""Plugin Hot Reloader - Watch and reload plugins on file changes."""

from __future__ import annotations

import asyncio
import logging
import os
import time
from pathlib import Path
from typing import Dict, Optional, Set

from dash_backend.plugins.loader import get_plugin_loader
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class PluginHotReloader:
    def __init__(self, watch_interval: float = 2.0):
        self._watch_interval = watch_interval
        self._running = False
        self._task: Optional[asyncio.Task] = None
        self._file_times: Dict[str, float] = {}
        self._plugin_dirs: Set[Path] = set()

    async def start(self) -> None:
        self._running = True
        self._scan_directories()
        self._task = asyncio.create_task(self._watch_loop())
        logger.info("PluginHotReloader started")

    async def stop(self) -> None:
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    def _scan_directories(self) -> None:
        from pathlib import Path
        cwd = Path.cwd()
        for d in [cwd / "plugins", cwd / "dash_backend" / "plugins" / "builtin"]:
            if d.exists():
                self._plugin_dirs.add(d)

    async def _watch_loop(self) -> None:
        while self._running:
            try:
                for directory in self._plugin_dirs:
                    if not directory.exists():
                        continue
                    for entry in directory.iterdir():
                        if entry.is_dir():
                            self._check_plugin_dir(entry)
                await asyncio.sleep(self._watch_interval)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)

    def _check_plugin_dir(self, directory: Path) -> None:
        for f in directory.rglob("*.py"):
            path_str = str(f)
            try:
                mtime = os.path.getmtime(path_str)
                if path_str in self._file_times:
                    if mtime > self._file_times[path_str]:
                        logger.info("Detected change in plugin file: %s", path_str)
                        plugin_id = directory.name
                        try:
                            loader = get_plugin_loader()
                            loader.unload(plugin_id)
                            loader.load(plugin_id)
                            logger.info("Hot-reloaded plugin: %s", plugin_id)
                        except Exception as exc:
                            logger.error("Hot-reload failed for %s: %s", plugin_id, exc)
                self._file_times[path_str] = mtime
            except OSError:
                continue


_plugin_hot_reloader: Optional[PluginHotReloader] = None


def get_plugin_hot_reloader() -> PluginHotReloader:
    global _plugin_hot_reloader
    if _plugin_hot_reloader is None:
        _plugin_hot_reloader = PluginHotReloader()
    return _plugin_hot_reloader
