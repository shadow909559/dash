"""Plugin Manager - Manage plugin lifecycle, health, and versioning."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.plugins.loader import PluginInstance, get_plugin_loader
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class PluginHealth:
    plugin_id: str = ""
    status: str = "unknown"
    uptime: float = 0.0
    memory_mb: float = 0.0
    cpu_percent: float = 0.0
    last_heartbeat: float = 0.0
    error_count: int = 0
    last_error: str = ""


@dataclass
class PluginInfo:
    id: str = ""
    name: str = ""
    version: str = ""
    description: str = ""
    author: str = ""
    is_loaded: bool = False
    is_enabled: bool = True
    permissions: List[str] = field(default_factory=list)
    health: PluginHealth = field(default_factory=PluginHealth)
    loaded_at: float = 0.0


class PluginManager:
    def __init__(self):
        self._loader = get_plugin_loader()
        self._plugins: Dict[str, PluginInfo] = {}
        self._health: Dict[str, PluginHealth] = {}
        self._running = False
        self._health_task: Optional[asyncio.Task] = None

    async def start(self) -> None:
        self._running = True
        self._health_task = asyncio.create_task(self._health_check_loop())
        await self.load_all()
        logger.info("PluginManager started")

    async def stop(self) -> None:
        self._running = False
        if self._health_task:
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass
        await self.unload_all()

    async def load_all(self) -> List[PluginInfo]:
        instances = self._loader.load_all()
        results = []
        for inst in instances:
            info = PluginInfo(
                id=inst.manifest.id, name=inst.manifest.name,
                version=inst.manifest.version, description=inst.manifest.description,
                author=inst.manifest.author, is_loaded=True,
                permissions=inst.manifest.permissions,
                loaded_at=time.time(),
                health=PluginHealth(plugin_id=inst.manifest.id, status="loaded", last_heartbeat=time.time()),
            )
            self._plugins[inst.manifest.id] = info
            self._health[inst.manifest.id] = info.health
            results.append(info)
        return results

    async def load(self, plugin_id: str) -> Optional[PluginInfo]:
        inst = self._loader.load(plugin_id)
        if not inst:
            return None
        info = PluginInfo(
            id=inst.manifest.id, name=inst.manifest.name,
            version=inst.manifest.version, description=inst.manifest.description,
            author=inst.manifest.author, is_loaded=True,
            permissions=inst.manifest.permissions, loaded_at=time.time(),
            health=PluginHealth(plugin_id=inst.manifest.id, status="loaded"),
        )
        self._plugins[plugin_id] = info
        self._health[plugin_id] = info.health
        return info

    async def unload(self, plugin_id: str) -> bool:
        result = self._loader.unload(plugin_id)
        if plugin_id in self._plugins:
            self._plugins[plugin_id].is_loaded = False
        return result

    async def unload_all(self) -> None:
        for pid in list(self._plugins.keys()):
            await self.unload(pid)

    async def reload(self, plugin_id: str) -> Optional[PluginInfo]:
        await self.unload(plugin_id)
        return await self.load(plugin_id)

    def list(self) -> List[PluginInfo]:
        return list(self._plugins.values())

    def get(self, plugin_id: str) -> Optional[PluginInfo]:
        return self._plugins.get(plugin_id)

    def get_health(self, plugin_id: str) -> Optional[PluginHealth]:
        return self._health.get(plugin_id)

    def all_health(self) -> Dict[str, PluginHealth]:
        return dict(self._health)

    async def enable(self, plugin_id: str) -> bool:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].is_enabled = True
            return True
        return False

    async def disable(self, plugin_id: str) -> bool:
        if plugin_id in self._plugins:
            self._plugins[plugin_id].is_enabled = False
            return True
        return False

    async def _health_check_loop(self) -> None:
        while self._running:
            try:
                for pid, info in self._plugins.items():
                    health = self._health.get(pid)
                    if health:
                        health.last_heartbeat = time.time()
                        if info.is_loaded:
                            health.status = "healthy"
                        else:
                            health.status = "unloaded"
                await asyncio.sleep(30.0)
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(30.0)


_plugin_manager: Optional[PluginManager] = None


def get_plugin_manager() -> PluginManager:
    global _plugin_manager
    if _plugin_manager is None:
        _plugin_manager = PluginManager()
    return _plugin_manager
