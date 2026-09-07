"""Power management tools for system operations."""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.services.power import PowerService

logger = get_logger(__name__)


class ShutdownTool(BaseTool):
    name = "shutdown"
    description = "Shutdown the computer system. Requires confirmation."
    parameters = [
        ToolParameter("force", "Force shutdown (skip waiting)", type="boolean", required=False, default=False),
        ToolParameter("timeout", "Seconds until shutdown", type="integer", required=False, default=30),
    ]
    permission_level = PermissionLevel.RESTRICTED
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.shutdown(force=kwargs.get("force", False), timeout=int(kwargs.get("timeout", 30)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RestartTool(BaseTool):
    name = "restart_system"
    description = "Restart the computer system. Requires confirmation."
    parameters = [
        ToolParameter("force", "Force restart", type="boolean", required=False, default=False),
        ToolParameter("timeout", "Seconds until restart", type="integer", required=False, default=30),
    ]
    permission_level = PermissionLevel.RESTRICTED
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.restart(force=kwargs.get("force", False), timeout=int(kwargs.get("timeout", 30)))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class LockWorkstationTool(BaseTool):
    name = "lock_workstation"
    description = "Lock the current workstation."
    parameters = []
    permission_level = PermissionLevel.CONFIRM
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.lock()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SleepTool(BaseTool):
    name = "sleep_system"
    description = "Put the system to sleep. Requires confirmation."
    parameters = []
    permission_level = PermissionLevel.RESTRICTED
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.sleep()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class HibernateTool(BaseTool):
    name = "hibernate_system"
    description = "Hibernate the system. Requires confirmation."
    parameters = []
    permission_level = PermissionLevel.RESTRICTED
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.hibernate()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class LogoffTool(BaseTool):
    name = "logoff_user"
    description = "Log off the current user. Requires confirmation."
    parameters = [
        ToolParameter("force", "Force logoff", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.RESTRICTED
    category = "power"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        svc = PowerService()
        try:
            result = await svc.logoff(force=kwargs.get("force", False))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=result.get("summary", ""))
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))

