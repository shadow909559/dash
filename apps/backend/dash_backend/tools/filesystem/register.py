from __future__ import annotations

from typing import Any

from dash_backend.tools.tool_registry import get_registry

# Import tool classes from the file_tools module
from dash_backend.tools.file_tools import (
    ReadFileTool,
    WriteFileTool,
    ListDirectoryTool,
    SearchFilesTool,
)


def register_filesystem_tools() -> None:
    registry = get_registry()

    tool_classes = [ReadFileTool, WriteFileTool, ListDirectoryTool, SearchFilesTool]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        if registry.get(name) is None:
            try:
                registry.register(cls())
            except Exception:
                # If registration fails, skip — discovery may handle it
                continue


# Run registration on import (idempotent)
register_filesystem_tools()
