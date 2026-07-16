"""Tool Registry - auto-discovery and dynamic registration of tools.

Scans tool modules for subclasses of BaseTool and registers them
for use by the ToolManager and LLM function calling.
"""

from __future__ import annotations

import importlib
import inspect
import pkgutil
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool

logger = get_logger(__name__)


class ToolRegistry:
    """Central registry that discovers and manages all available tools.

    Tools are auto-discovered by scanning the `dash_backend.tools`
    package for subclasses of BaseTool. Tools can also be registered
    manually via `register()`.
    """

    def __init__(self) -> None:
        self._tools: dict[str, BaseTool] = {}

    # ──────────────────────────────────────────────
    # Registration
    # ──────────────────────────────────────────────

    def register(self, tool: BaseTool) -> None:
        """Register a single tool instance.

        Args:
            tool: An instantiated BaseTool subclass.

        Raises:
            ValueError: If a tool with the same name is already registered.
        """
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Expected BaseTool instance, got {type(tool)}")

        if tool.name in self._tools:
            raise ValueError(
                f"Tool '{tool.name}' is already registered. "
                f"Existing: {type(self._tools[tool.name]).__name__}, "
                f"New: {type(tool).__name__}"
            )

        self._tools[tool.name] = tool
        logger.debug("Registered tool: %s (category=%s)", tool.name, tool.category)

    def unregister(self, name: str) -> None:
        """Remove a tool by name."""
        self._tools.pop(name, None)

    # ──────────────────────────────────────────────
    # Discovery
    # ──────────────────────────────────────────────

    def discover(self, package: str = "dash_backend.tools") -> int:
        """Auto-discover tools by scanning a package for BaseTool subclasses.

        Scans all modules in the given package, finds classes that
        subclass BaseTool (but are not BaseTool itself), instantiates
        them, and registers them.

        Args:
            package: Dotted package path to scan (default: tools package).

        Returns:
            Number of tools discovered and registered.
        """
        count = 0
        try:
            pkg = importlib.import_module(package)
        except ModuleNotFoundError:
            logger.warning("Package '%s' not found, skipping discovery", package)
            return 0

        prefix = f"{package}."
        for _importer, modname, _ispkg in pkgutil.walk_packages(
            pkg.__path__, prefix=prefix
        ):
            try:
                module = importlib.import_module(modname)
                count += self._scan_module(module)
            except Exception as exc:
                logger.warning("Failed to scan module '%s': %s", modname, exc)

        logger.info(
            "Tool discovery complete: %d tools registered from package '%s'",
            count,
            package,
        )
        return count

    def _scan_module(self, module: object) -> int:
        """Scan a single module for BaseTool subclasses and register them."""
        count = 0
        for _name, obj in inspect.getmembers(module, inspect.isclass):
            if (
                issubclass(obj, BaseTool)
                and obj is not BaseTool
                and not inspect.isabstract(obj)
            ):
                try:
                    instance = obj()
                    self.register(instance)
                    count += 1
                except Exception as exc:
                    logger.warning(
                        "Failed to instantiate tool %s.%s: %s",
                        getattr(module, "__name__", "?"),
                        obj.__name__,
                        exc,
                    )
        return count

    # ──────────────────────────────────────────────
    # Lookup
    # ──────────────────────────────────────────────

    def get(self, name: str) -> BaseTool | None:
        """Get a registered tool by name."""
        return self._tools.get(name)

    def get_all(self) -> dict[str, BaseTool]:
        """Get all registered tools (name -> tool)."""
        return dict(self._tools)

    def get_by_category(self, category: str) -> list[BaseTool]:
        """Get all tools in a given category."""
        return [t for t in self._tools.values() if t.category == category]

    def get_openai_tools(self) -> list[dict[str, Any]]:
        """Return all tool definitions in OpenAI-compatible format.

        Use this to populate the `tools` parameter in LLM API calls.
        """
        return [tool.spec.to_openai_tool() for tool in self._tools.values()]

    @property
    def tool_count(self) -> int:
        return len(self._tools)

    @property
    def tool_names(self) -> list[str]:
        return sorted(self._tools.keys())

    def list_tools(self) -> list[dict[str, Any]]:
        """Return a human-readable summary of all registered tools."""
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "category": tool.category,
                "permission_level": tool.permission_level.name,
                "parameters": [
                    {
                        "name": p.name,
                        "type": p.type,
                        "required": p.required,
                        "description": p.description,
                    }
                    for p in tool.parameters
                ],
            }
            for tool in self._tools.values()
        ]


# Global singleton registry
_registry: ToolRegistry | None = None


def get_registry() -> ToolRegistry:
    """Return the global tool registry singleton."""
    global _registry
    if _registry is None:
        _registry = ToolRegistry()
        _registry.discover()
    return _registry