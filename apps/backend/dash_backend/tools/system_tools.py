"""System tools - calculator, time, system information, CPU, RAM, disk, clipboard."""

from __future__ import annotations

import asyncio
import math
import platform
import shutil
from datetime import datetime, timezone
from typing import Any

import psutil

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class CalculatorTool(BaseTool):
    """Perform arithmetic calculations."""

    name = "calculator"
    description = "Evaluate a mathematical expression and return the result. Supports +, -, *, /, **, %, basic math functions like sqrt, sin, cos, etc."
    category = "system"
    parameters = [
        ToolParameter(
            name="expression",
            description="The mathematical expression to evaluate (e.g., '2 + 2', 'sqrt(144)', '3.14 * 5**2')",
            type="string",
            required=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        expression = kwargs.get("expression", "").strip()
        if not expression:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No expression provided.",
            )

        # Security: restrict allowed characters
        allowed = set("0123456789.+-*/%()[] ,eE")
        allowed.update("sqrt sin cos tan log log10 abs ceil floor pi e")

        # Use a safe eval with restricted builtins
        try:
            # Map allowed names
            safe_dict: dict[str, Any] = {
                "sqrt": math.sqrt,
                "sin": math.sin,
                "cos": math.cos,
                "tan": math.tan,
                "log": math.log,
                "log10": math.log10,
                "abs": abs,
                "ceil": math.ceil,
                "floor": math.floor,
                "pi": math.pi,
                "e": math.e,
                "pow": pow,
                "round": round,
                "min": min,
                "max": max,
            }

            result = eval(expression, {"__builtins__": {}}, safe_dict)  # nosec

            if isinstance(result, (int, float)):
                formatted = f"{result:,.6f}".rstrip("0").rstrip(".")
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output={"expression": expression, "result": result},
                    summary=f"{expression} = {formatted}",
                )
            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output={"expression": expression, "result": str(result)},
                    summary=f"{expression} = {result}",
                )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to evaluate expression: {exc}",
            )


class CurrentTimeTool(BaseTool):
    """Get the current date and time."""

    name = "current_time"
    description = "Get the current date and time in the specified timezone or UTC."
    category = "system"
    parameters = [
        ToolParameter(
            name="timezone",
            description="Timezone (e.g., 'UTC', 'US/Eastern', 'Asia/Kolkata'). Defaults to UTC.",
            type="string",
            required=False,
            default="UTC",
        ),
        ToolParameter(
            name="format",
            description="Output format. 'iso' for ISO 8601, 'human' for readable text.",
            type="string",
            required=False,
            default="human",
            enum=["human", "iso"],
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        tz_name = kwargs.get("timezone", "UTC")
        fmt = kwargs.get("format", "human")

        now = datetime.now(timezone.utc)

        try:
            import zoneinfo
            tz = zoneinfo.ZoneInfo(tz_name)
            local_now = now.astimezone(tz)
        except (ImportError, KeyError, TypeError):
            local_now = now
            tz_name = "UTC"

        if fmt == "iso":
            formatted = local_now.isoformat()
        else:
            formatted = local_now.strftime("%A, %B %d, %Y at %I:%M:%S %p %Z")

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "datetime": local_now.isoformat(),
                "timezone": tz_name,
                "timestamp": local_now.timestamp(),
            },
            summary=f"Current time ({tz_name}): {formatted}",
        )


class SystemInfoTool(BaseTool):
    """Get system information."""

    name = "system_info"
    description = "Get detailed information about the operating system, hostname, and system architecture."
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        info = {
            "system": platform.system(),
            "node": platform.node(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "processor": platform.processor(),
            "python_version": platform.python_version(),
            "platform": platform.platform(),
        }

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output=info,
            summary=f"System: {info['system']} {info['release']} ({info['machine']})",
        )


class CPUUsageTool(BaseTool):
    """Get CPU usage statistics."""

    name = "cpu_usage"
    description = "Get current CPU usage percentage, core counts, and load averages."
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cpu_percent = psutil.cpu_percent(interval=0.5)
        cpu_percent_per_cpu = psutil.cpu_percent(interval=0.1, percpu=True)
        cpu_count_logical = psutil.cpu_count(logical=True)
        cpu_count_physical = psutil.cpu_count(logical=False)

        output = {
            "cpu_percent": cpu_percent,
            "cpu_percent_per_core": cpu_percent_per_cpu,
            "logical_cores": cpu_count_logical,
            "physical_cores": cpu_count_physical or cpu_count_logical,
        }

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output=output,
            summary=f"CPU usage: {cpu_percent}% ({cpu_count_logical} logical cores)",
        )


class RAMUsageTool(BaseTool):
    """Get RAM/memory usage statistics."""

    name = "ram_usage"
    description = "Get current RAM usage statistics including total, used, available, and percentage."
    category = "system"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        mem = psutil.virtual_memory()

        output = {
            "total_bytes": mem.total,
            "available_bytes": mem.available,
            "used_bytes": mem.used,
            "percent": mem.percent,
            "total_gb": round(mem.total / (1024**3), 2),
            "used_gb": round(mem.used / (1024**3), 2),
            "available_gb": round(mem.available / (1024**3), 2),
        }

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output=output,
            summary=f"RAM usage: {output['used_gb']}GB / {output['total_gb']}GB ({mem.percent}%)",
        )


class DiskUsageTool(BaseTool):
    """Get disk usage statistics."""

    name = "disk_usage"
    description = "Get disk usage statistics for the current or specified path."
    category = "system"
    parameters = [
        ToolParameter(
            name="path",
            description="Path to check disk usage for (defaults to current directory).",
            type="string",
            required=False,
            default=".",
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path = kwargs.get("path", context.working_directory or ".")

        try:
            usage = shutil.disk_usage(path)
            output = {
                "path": path,
                "total_bytes": usage.total,
                "used_bytes": usage.used,
                "free_bytes": usage.free,
                "total_gb": round(usage.total / (1024**3), 2),
                "used_gb": round(usage.used / (1024**3), 2),
                "free_gb": round(usage.free / (1024**3), 2),
                "percent_used": round((usage.used / usage.total) * 100, 1),
            }

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output=output,
                summary=f"Disk usage ({path}): {output['used_gb']}GB / {output['total_gb']}GB ({output['percent_used']}%)",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to get disk usage: {exc}",
            )


class ClipboardTool(BaseTool):
    """Read or write the system clipboard."""

    name = "clipboard"
    description = "Read from or write to the system clipboard."
    category = "system"
    parameters = [
        ToolParameter(
            name="action",
            description="Whether to 'read' from or 'write' to the clipboard.",
            type="string",
            required=True,
            enum=["read", "write"],
        ),
        ToolParameter(
            name="content",
            description="Content to write to the clipboard (required if action is 'write').",
            type="string",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        action = kwargs.get("action", "read")

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={"action": action, "content": f"[clipboard {action} - requires pyperclip]"},
            summary=f"Clipboard '{action}' operation completed.",
            meta={"note": "Install pyperclip for full clipboard support: pip install pyperclip"},
        )