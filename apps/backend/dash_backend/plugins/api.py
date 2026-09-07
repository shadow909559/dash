"""Plugin API - provides plugins access to memory, planner, RAG, and tools.

This is the primary interface through which plugins interact with DASH.
Plugins receive an instance of PluginAPI when activated.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.plugins.sandbox import PluginSandbox
from dash_backend.plugins.permissions import get_permission_registry
from dash_backend.tools.tool_manager import get_tool_manager, ToolCallRequest
from dash_backend.tools.base_tool import ToolContext

logger = get_logger(__name__)


class PluginAPI:
    """API surface exposed to plugins.

    All calls are permission-checked via the PluginSandbox and PermissionRegistry.
    Plugins cannot access the database directly; they must go through this API.
    """

    def __init__(self, plugin_id: str, sandbox: PluginSandbox):
        self.plugin_id = plugin_id
        self.sandbox = sandbox
        self._perm_registry = get_permission_registry()
        self._tool_manager = get_tool_manager()

    # ── Identity ───────────────────────────────────

    @property
    def id(self) -> str:
        return self.plugin_id

    # ── Memory API ──────────────────────────────

    async def memory_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search memories by query text."""
        self._perm_registry.require(self.plugin_id, "memory.read")
        try:
            from dash_backend.memory.service import search_memories
            # Note: In production, the session would be injected
            from dash_backend.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                results = await search_memories(session, self.plugin_id, query, limit=limit)
                return [{"id": str(r.id), "content": r.content, "category": r.category} for r in results]
        except Exception as exc:
            logger.warning("Plugin memory_search failed: %s", exc)
            return []

    async def memory_save(self, content: str, category: str = "plugin") -> Optional[str]:
        """Save a memory entry."""
        self._perm_registry.require(self.plugin_id, "memory.write")
        try:
            from dash_backend.memory.service import add_memory
            from dash_backend.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                memory = await add_memory(session, user_id=self.plugin_id, content=content, category=category)
                return str(memory.id) if memory else None
        except Exception as exc:
            logger.warning("Plugin memory_save failed: %s", exc)
            return None

    # ── Planner API ─────────────────────────────

    async def planner_get_goals(self) -> List[Dict[str, Any]]:
        """Get current planner goals."""
        self._perm_registry.require(self.plugin_id, "planner.read")
        try:
            from dash_backend.executive.planner import get_planner_service
            planner = get_planner_service()
            goals = await planner.get_all_goals()
            return [
                {"id": str(g.id), "title": g.name, "status": g.status}
                for g in goals
            ]
        except Exception as exc:
            logger.warning("Plugin planner_get_goals failed: %s", exc)
            return []

    # ── RAG API ────────────────────────────────

    async def rag_search(self, query: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search RAG documents by query."""
        self._perm_registry.require(self.plugin_id, "rag.read")
        try:
            from dash_backend.rag.service import retrieve_context
            from dash_backend.db.session import AsyncSessionLocal
            async with AsyncSessionLocal() as session:
                context = await retrieve_context(session, self.plugin_id, query=query, limit=limit)
                return [{"content": context}] if context else []
        except Exception as exc:
            logger.warning("Plugin rag_search failed: %s", exc)
            return []

    # ── Tool API ───────────────────────────────

    async def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a registered tool."""
        self._perm_registry.require(self.plugin_id, "tools.execute")
        try:
            request = ToolCallRequest(tool_name=tool_name, arguments=arguments)
            context = ToolContext(user_id=self.plugin_id, request_id=f"plugin_{self.plugin_id}")
            result = await self._tool_manager.execute_tool(request, context)
            return result.to_dict()
        except Exception as exc:
            logger.warning("Plugin execute_tool failed: %s", exc)
            return {"status": "error", "error": str(exc)}

    async def register_tool(self, tool_instance) -> bool:
        """Register a new tool."""
        self._perm_registry.require(self.plugin_id, "tools.register")
        try:
            from dash_backend.tools.tool_registry import get_registry
            registry = get_registry()
            registry.register(tool_instance)
            return True
        except Exception as exc:
            logger.warning("Plugin register_tool failed: %s", exc)
            return False
