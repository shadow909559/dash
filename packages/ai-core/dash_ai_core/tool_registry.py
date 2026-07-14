"""Tool registry.

Tools are identified by name and can be invoked by the executor.

This is an in-process registry with no tool execution by default.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True, slots=True)
class ToolRegistration:
    name: str
    description: str | None
    func: Callable[[Mapping[str, Any]], Any]


class ToolRegistry:
    """Registry mapping tool name -> tool implementation."""

    def __init__(self) -> None:
        self._tools: dict[str, ToolRegistration] = {}

    def register(
        self,
        *,
        name: str,
        func: Callable[[Mapping[str, Any]], Any],
        description: str | None = None,
    ) -> None:
        if not name:
            raise ValueError("Tool name must be non-empty")
        self._tools[name] = ToolRegistration(name=name, description=description, func=func)

    def get(self, name: str) -> ToolRegistration:
        try:
            return self._tools[name]
        except KeyError as e:
            raise KeyError(f"Unknown tool: {name}") from e

    def list_names(self) -> list[str]:
        return sorted(self._tools.keys())

