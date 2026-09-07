"""Plugin Manager - Dynamic plugin loading and management."""

from __future__ import annotations

import importlib
import inspect
import json
from pathlib import Path
from typing import Dict, List, Optional, Any, Callable
from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class PluginState(Enum):
    LOADED = "loaded"
    UNLOADED = "unloaded"
    ERROR = "error"
    DISABLED = "disabled"


@dataclass
class PluginInfo:
    name: str
    version: str
    description: str
    author: str
    dependencies: List[str]
    permissions: List[str]
    state: PluginState = PluginState.UNLOADED
    error: Optional[str] = None


class Plugin(ABC):
    """Base class for all plugins."""
    
    @property
    @abstractmethod
    def info(self) -> PluginInfo:
        """Return plugin metadata."""
        pass
    
    @abstractmethod
    async def initialize(self) -> None:
        """Initialize the plugin."""
        pass
    
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the plugin."""
        pass
    
    @abstractmethod
    async def execute(self, method: str, **kwargs) -> Any:
        """Execute a plugin method."""
        pass


class PluginManager:
    """Manages plugin lifecycle, discovery, and execution."""
    
    def __init__(self, plugin_dir: str = "plugins"):
        self.plugin_dir = Path(plugin_dir)
        self.plugins: Dict[str, Plugin] = {}
        self.plugin_info: Dict[str, PluginInfo] = {}
        self.hooks: Dict[str, List[Callable]] = {}
        
    async def discover_plugins(self) -> List[PluginInfo]:
        """Discover all available plugins in the plugin directory."""
        discovered = []
        
        if not self.plugin_dir.exists():
            logger.warning(f"Plugin directory {self.plugin_dir} does not exist")
            return discovered
        
        for plugin_path in self.plugin_dir.glob("*.py"):
            if plugin_path.name.startswith("_"):
                continue
            
            try:
                module = importlib.import_module(f"plugins.{plugin_path.stem}")
                
                for name, obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                        plugin = obj()
                        info = plugin.info
                        self.plugin_info[info.name] = info
                        discovered.append(info)
                        logger.info(f"Discovered plugin: {info.name} v{info.version}")
            except Exception as e:
                logger.error(f"Failed to load plugin from {plugin_path}: {e}")
        
        return discovered
    
    async def load_plugin(self, name: str) -> bool:
        """Load a specific plugin."""
        if name not in self.plugin_info:
            logger.error(f"Plugin {name} not found")
            return False
        
        info = self.plugin_info[name]
        
        if info.state == PluginState.LOADED:
            logger.warning(f"Plugin {name} already loaded")
            return True
        
        try:
            # Re-discover to get the plugin instance
            await self.discover_plugins()
            
            # Find the plugin in discovered modules
            for plugin_path in self.plugin_dir.glob("*.py"):
                if plugin_path.name.startswith("_"):
                    continue
                
                module = importlib.import_module(f"plugins.{plugin_path.stem}")
                for obj in inspect.getmembers(module):
                    if inspect.isclass(obj) and issubclass(obj, Plugin) and obj != Plugin:
                        plugin = obj()
                        if plugin.info.name == name:
                            await plugin.initialize()
                            self.plugins[name] = plugin
                            info.state = PluginState.LOADED
                            logger.info(f"Loaded plugin: {name}")
                            return True
        except Exception as e:
            info.state = PluginState.ERROR
            info.error = str(e)
            logger.error(f"Failed to load plugin {name}: {e}")
            return False
        
        return False
    
    async def unload_plugin(self, name: str) -> bool:
        """Unload a specific plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} not loaded")
            return False
        
        try:
            plugin = self.plugins[name]
            await plugin.shutdown()
            del self.plugins[name]
            self.plugin_info[name].state = PluginState.UNLOADED
            logger.info(f"Unloaded plugin: {name}")
            return True
        except Exception as e:
            logger.error(f"Failed to unload plugin {name}: {e}")
            return False
    
    async def execute_plugin(self, name: str, method: str, **kwargs) -> Any:
        """Execute a method on a plugin."""
        if name not in self.plugins:
            logger.error(f"Plugin {name} not loaded")
            raise ValueError(f"Plugin {name} not loaded")
        
        plugin = self.plugins[name]
        
        if plugin.plugin_info.state != PluginState.LOADED:
            logger.error(f"Plugin {name} is not loaded")
            raise ValueError(f"Plugin {name} is not loaded")
        
        try:
            return await plugin.execute(method, **kwargs)
        except Exception as e:
            logger.error(f"Failed to execute {method} on plugin {name}: {e}")
            raise
    
    def register_hook(self, hook_name: str, callback: Callable) -> None:
        """Register a callback for a specific hook."""
        if hook_name not in self.hooks:
            self.hooks[hook_name] = []
        self.hooks[hook_name].append(callback)
        logger.info(f"Registered hook: {hook_name}")
    
    async def trigger_hook(self, hook_name: str, **kwargs) -> List[Any]:
        """Trigger all callbacks for a specific hook."""
        results = []
        
        if hook_name not in self.hooks:
            return results
        
        for callback in self.hooks[hook_name]:
            try:
                if inspect.iscoroutinefunction(callback):
                    result = await callback(**kwargs)
                else:
                    result = callback(**kwargs)
                results.append(result)
            except Exception as e:
                logger.error(f"Hook callback failed for {hook_name}: {e}")
        
        return results
    
    def get_loaded_plugins(self) -> List[PluginInfo]:
        """Get all loaded plugins."""
        return [info for info in self.plugin_info.values() if info.state == PluginState.LOADED]
    
    def get_plugin_info(self, name: str) -> Optional[PluginInfo]:
        """Get information about a specific plugin."""
        return self.plugin_info.get(name)
