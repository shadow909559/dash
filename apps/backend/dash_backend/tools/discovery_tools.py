"""Discovery tools: application discovery and phone/ADB control.

Registers tools that expose the ApplicationDiscoveryService and the
AdbService to the LLM so DASH can resolve apps and control phones via
natural language.
"""

from __future__ import annotations

from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)


class DiscoverApplicationsTool(BaseTool):
    name = "discover_applications"
    description = "Discover all installed applications on the system."
    parameters = [
        ToolParameter("refresh", "Force re-scan", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            from dash_backend.services.application_discovery import get_application_discovery
            service = get_application_discovery()
            apps = service.discover_all(refresh=bool(kwargs.get("refresh", False)))
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"count": len(apps), "applications": apps[:100]},
                summary=f"Discovered {len(apps)} installed applications",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ResolveApplicationTool(BaseTool):
    name = "resolve_application"
    description = "Resolve a friendly application name to its discovered path/executable."
    parameters = [
        ToolParameter("name", "Application name (e.g., Chrome, VS Code, Word)", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "desktop"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        try:
            from dash_backend.services.application_discovery import get_application_discovery
            service = get_application_discovery()
            app = service.resolve(name)
            if not app:
                return ToolResult(
                    tool_name=self.name, status=ToolStatus.SUCCESS,
                    output={"resolved": False, "query": name},
                    summary=f"Could not find application '{name}'",
                )
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"resolved": True, "app": app},
                summary=f"Resolved '{name}' to {app.get('path') or app.get('name')}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ListPhoneDevicesTool(BaseTool):
    name = "list_phone_devices"
    description = "Discover connected Android devices via ADB (USB + wireless)."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "phone"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            from dash_backend.phone.adb_service import get_adb_service
            service = get_adb_service()
            devices = await service.discover_devices()
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"devices": devices},
                summary=f"Found {len(devices)} Android device(s)",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PhoneBatteryTool(BaseTool):
    name = "phone_battery"
    description = "Get battery info from an Android device via ADB."
    parameters = [
        ToolParameter("serial", "Device serial (optional)", required=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "phone"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            from dash_backend.phone.adb_service import get_adb_service
            service = get_adb_service()
            result = await service.get_battery(kwargs.get("serial"))
            if not result.get("ok"):
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=result.get("error", "No device"))
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"battery": result.get("battery", {})},
                summary=f"Battery level {result.get('level', 'unknown')}%",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PhoneOpenAppTool(BaseTool):
    name = "phone_open_app"
    description = "Launch an app on an Android device via ADB by package name."
    parameters = [
        ToolParameter("package", "Android package name", required=True),
        ToolParameter("serial", "Device serial (optional)", required=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "phone"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        package = kwargs.get("package", "")
        if not package:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="package required")
        try:
            from dash_backend.phone.adb_service import get_adb_service
            service = get_adb_service()
            result = await service.open_app(package, kwargs.get("serial"))
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS if result.get("ok") else ToolStatus.ERROR,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PhoneScreenshotTool(BaseTool):
    name = "phone_screenshot"
    description = "Capture a screenshot from an Android device via ADB."
    parameters = [
        ToolParameter("local_path", "Local save path", required=False, default="phone_screen.png"),
        ToolParameter("serial", "Device serial (optional)", required=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "phone"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            from dash_backend.phone.adb_service import get_adb_service
            service = get_adb_service()
            result = await service.screenshot(kwargs.get("local_path", "phone_screen.png"), kwargs.get("serial"))
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS if result.get("ok") else ToolStatus.ERROR,
                output=result,
                summary=result.get("summary", ""),
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


def register_discovery_tools() -> None:
    """Register discovery/phone tools with the tool registry."""
    from dash_backend.tools.tool_registry import get_registry
    registry = get_registry()
    tool_classes = [
        DiscoverApplicationsTool,
        ResolveApplicationTool,
        ListPhoneDevicesTool,
        PhoneBatteryTool,
        PhoneOpenAppTool,
        PhoneScreenshotTool,
    ]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
                logger.info("Registered discovery tool: %s", name)
        except Exception:
            logger.exception("Failed to register tool %s", name)


# Run on import
register_discovery_tools()
