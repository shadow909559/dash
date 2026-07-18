"""Terminal command execution tool with safety checks."""

from __future__ import annotations

import asyncio
import subprocess
import sys
from typing import Any

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_executor import DANGEROUS_COMMANDS
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class RunTerminalCommandTool(BaseTool):
    """Execute a terminal command with output capture."""

    name = "run_terminal_command"
    description = "Execute a terminal command and capture its output. Requires user confirmation. Dangerous commands (rm, del, format, shutdown, reboot, git push, package installs, sudo) are blocked."
    category = "terminal"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="command",
            description="The command to execute.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="timeout",
            description="Maximum execution time in seconds.",
            type="number",
            required=False,
            default=30,
        ),
        ToolParameter(
            name="working_directory",
            description="Working directory for the command (defaults to project root).",
            type="string",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        command = kwargs.get("command", "").strip()
        timeout = min(float(kwargs.get("timeout", 30)), 120)
        working_dir = kwargs.get("working_directory") or context.working_directory or "."

        if not command:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No command provided.",
            )

        # Check for dangerous commands
        command_lower = command.lower().strip()
        for dangerous in DANGEROUS_COMMANDS:
            if command_lower.startswith(dangerous) or f" {dangerous}" in command_lower:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Command contains dangerous operation: '{dangerous}'. This command is blocked for safety.",
                    output={"command": command, "blocked_by": dangerous},
                )

        try:
            # Run command with timeout
            if sys.platform == "win32":
                # Use PowerShell on Windows for better compatibility
                cmd_parts = ["powershell", "-Command", command]
            else:
                cmd_parts = ["sh", "-c", command]

            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_dir,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                returncode = process.returncode or 0

            except asyncio.TimeoutError:
                process.kill()
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.TIMEOUT,
                    error_message=f"Command timed out after {timeout}s",
                    output={"command": command},
                )

            output = {
                "command": command,
                "returncode": returncode,
                "stdout": stdout[:5000],  # Limit output size
                "stderr": stderr[:2000],
                "truncated": len(stdout) > 5000 or len(stderr) > 2000,
            }

            if returncode == 0:
                summary = stdout.strip()[:200] if stdout.strip() else "Command completed successfully"
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output=output,
                    summary=summary,
                    raw_output=stdout[:10000],
                )
            else:
                error_msg = stderr.strip()[:200] if stderr.strip() else f"Command failed with code {returncode}"
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=error_msg,
                    output=output,
                    raw_output=stderr[:5000],
                )

        except FileNotFoundError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Shell not found. Cannot execute command.",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to execute command: {exc}",
            )