"""Terminal tools - CMD, PowerShell, script execution, cancel running task."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"

# Track running tasks for cancellation
_running_tasks: dict[str, asyncio.Task] = {}


class RunCmdTool(BaseTool):
    name = "run_cmd"
    description = "Execute a command in Windows Command Prompt (CMD) and return output."
    parameters = [
        ToolParameter("command", "Command to execute", required=True),
        ToolParameter("timeout", "Timeout in seconds", type="integer", required=False, default=30),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "terminal"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = int(kwargs.get("timeout", 30))
        if not command:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="command required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="CMD only available on Windows")
        try:
            process = await asyncio.create_subprocess_exec(
                "cmd", "/c", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                    "command": command, "stdout": stdout[:10000], "stderr": stderr[:5000],
                    "returncode": process.returncode or 0,
                }, summary=stdout.strip()[:200] or "Command executed")
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(tool_name=self.name, status=ToolStatus.TIMEOUT, error_message=f"Command timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RunPowerShellTool(BaseTool):
    name = "run_powershell"
    description = "Execute a PowerShell command or script and return output."
    parameters = [
        ToolParameter("command", "PowerShell command or script to execute", required=True),
        ToolParameter("timeout", "Timeout in seconds", type="integer", required=False, default=30),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "terminal"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "")
        timeout = int(kwargs.get("timeout", 30))
        if not command:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="command required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="PowerShell only available on Windows")
        try:
            process = await asyncio.create_subprocess_exec(
                "powershell", "-Command", command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                    "command": command, "stdout": stdout[:10000], "stderr": stderr[:5000],
                    "returncode": process.returncode or 0,
                }, summary=stdout.strip()[:200] or "PowerShell command executed")
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(tool_name=self.name, status=ToolStatus.TIMEOUT, error_message=f"Command timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RunScriptTool(BaseTool):
    name = "run_script"
    description = "Execute a multi-line script (PowerShell on Windows, bash on Linux/macOS) and return output."
    parameters = [
        ToolParameter("script", "Script content to execute", required=True),
        ToolParameter("timeout", "Timeout in seconds", type="integer", required=False, default=60),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "terminal"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        script = kwargs.get("script", "")
        timeout = int(kwargs.get("timeout", 60))
        if not script:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="script required")
        try:
            if IS_WINDOWS:
                process = await asyncio.create_subprocess_exec(
                    "powershell", "-Command", script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            else:
                process = await asyncio.create_subprocess_exec(
                    "bash", "-c", script,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                )
            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(process.communicate(), timeout=timeout)
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                    "stdout": stdout[:20000], "stderr": stderr[:5000],
                    "returncode": process.returncode or 0,
                }, summary=stdout.strip()[:200] or "Script executed")
            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(tool_name=self.name, status=ToolStatus.TIMEOUT, error_message=f"Script timed out after {timeout}s")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CancelTaskTool(BaseTool):
    name = "cancel_task"
    description = "Cancel a running terminal task by task ID. Use 'list_tasks' to see running tasks."
    parameters = [
        ToolParameter("task_id", "Task ID to cancel", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "terminal"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        task_id = kwargs.get("task_id", "")
        if not task_id:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="task_id required")
        task = _running_tasks.get(task_id)
        if task is None:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Task not found: {task_id}")
        if not task.done():
            task.cancel()
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Task {task_id} cancelled")
        return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Task {task_id} already completed")


class ListTasksTool(BaseTool):
    name = "list_tasks"
    description = "List all running terminal tasks with their IDs."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "terminal"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        tasks = []
        for task_id, task in _running_tasks.items():
            tasks.append({"task_id": task_id, "done": task.done(), "cancelled": task.cancelled()})
        return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"tasks": tasks},
                          summary=f"Found {len(tasks)} tasks")
