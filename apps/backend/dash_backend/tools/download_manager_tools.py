"""Download Manager tools: list, organize, stats for the Downloads folder.

Exposes the DownloadManager service as callable DASH tools.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.download_manager import get_download_manager
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


class ListDownloadsTool(BaseTool):
    name = "list_downloads"
    description = "List recent files in the Downloads folder, newest first."
    parameters = [ToolParameter("limit", "Maximum results", type="integer", required=False, default=50)]
    permission_level = PermissionLevel.AUTO
    category = "downloads"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 50))
        try:
            result = get_download_manager().list_downloads(limit=limit)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result, summary=f"Found {result.get('count', 0)} downloads",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class OrganizeDownloadsTool(BaseTool):
    name = "organize_downloads"
    description = "Auto-organize the Downloads folder into categorized subfolders by file type."
    parameters = [ToolParameter("dry_run", "Preview without moving files", type="boolean", required=False, default=False)]
    permission_level = PermissionLevel.CONFIRM
    category = "downloads"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        dry_run = bool(kwargs.get("dry_run", False))
        try:
            result = get_download_manager().auto_organize(dry_run=dry_run)
            action = "Would organize" if dry_run else "Organized"
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result, summary=f"{action} {result.get('organized', 0)} files",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class DownloadStatsTool(BaseTool):
    name = "download_stats"
    description = "Get statistics about the Downloads folder (total files, size)."
    parameters: list[ToolParameter] = []
    permission_level = PermissionLevel.AUTO
    category = "downloads"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            result = get_download_manager().get_stats()
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output=result, summary=f"{result.get('total_files', 0)} files, {result.get('total_size_mb', 0)} MB",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


def register_download_manager_tools() -> None:
    """Register download manager tools with the tool registry."""
    from dash_backend.tools.tool_registry import get_registry

    registry = get_registry()
    tool_classes = [ListDownloadsTool, OrganizeDownloadsTool, DownloadStatsTool]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
                logger.info("Registered download manager tool: %s", name)
        except Exception:
            logger.exception("Failed to register tool %s", name)


# Run on import (idempotent)
register_download_manager_tools()
