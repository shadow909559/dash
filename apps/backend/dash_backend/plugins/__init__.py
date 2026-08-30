"""Plugin SDK - Plugin system for DASH AI Operating System.

Provides plugin loading, lifecycle management, sandboxing, permissions,
and API access to memory, planner, RAG, and tool registration.
"""

from .loader import PluginLoader
from .manifest import PluginManifest
from .sandbox import PluginSandbox
from .permissions import PermissionRegistry
from .api import PluginAPI

__all__ = ["PluginLoader", "PluginManifest", "PluginSandbox", "PermissionRegistry", "PluginAPI"]

