"""Application management tools - search, launch, bring to foreground, close."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.applications import ApplicationService
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


class SearchApplicationsTool(BaseTool):
    name = "search_applications"
    description = "Search for installed applications by name on the system."
    parameters = [
        ToolParameter("query", "Search query for application name", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "applications"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query", "")
        if not query:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="query required")
        
        try:
            service = ApplicationService()
            results = await service.search_applications(query)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"query": query, "results": results, "count": len(results)},
                summary=f"Found {len(results)} applications matching '{query}'",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class LaunchApplicationTool(BaseTool):
    name = "launch_application"
    description = "Launch an application by friendly name. If already running, brings it to foreground."
    parameters = [
        ToolParameter("name", "Application name to launch", required=True),
        ToolParameter("bring_to_foreground", "Bring to foreground if already running", required=False, default=True, type="boolean"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "applications"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        bring_to_foreground = kwargs.get("bring_to_foreground", True)
        
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        
        try:
            service = ApplicationService()
            result = await service.launch_by_name(name, bring_to_foreground=bring_to_foreground)
            
            status = ToolStatus.SUCCESS
            if result.get("status") == "already_running":
                status = ToolStatus.SUCCESS  # Still success, just already running
            
            return ToolResult(
                tool_name=self.name,
                status=status,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class BringToForegroundTool(BaseTool):
    name = "bring_to_foreground"
    description = "Bring a running application window to the foreground by process ID."
    parameters = [
        ToolParameter("pid", "Process ID of the application", required=True, type="integer"),
    ]
    permission_level = PermissionLevel.AUTO
    category = "applications"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        pid = kwargs.get("pid")
        if pid is None:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pid required")
        
        try:
            service = ApplicationService()
            result = await service.bring_to_foreground(int(pid))
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CloseApplicationTool(BaseTool):
    name = "close_application"
    description = "Close an application by name."
    parameters = [
        ToolParameter("name", "Application name to close", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "applications"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        
        try:
            service = ApplicationService()
            result = await service.close(name)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RestartApplicationTool(BaseTool):
    name = "restart_application"
    description = "Restart an application by name."
    parameters = [
        ToolParameter("name", "Application name to restart", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "applications"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        
        try:
            service = ApplicationService()
            result = await service.restart(name)
            
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))
