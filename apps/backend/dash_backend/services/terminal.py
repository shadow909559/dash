"""TerminalService - execute terminal commands and return output."""

from __future__ import annotations

import asyncio
import sys
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

# Commands that are always blocked for safety
BLOCKED_COMMANDS = [
    "rm -rf /", "format", "sudo rm", "> /dev/sda",
    "dd if=", "mkfs", "mkswap",
]


class TerminalService(Singleton):
    """Execute terminal commands with safety checks."""

    async def execute(
        self,
        command: str,
        timeout: int = 30,
        working_directory: str | None = None,
    ) -> dict[str, Any]:
        """Execute a command and return its output."""
        if not command:
            raise ValueError("command is required")

        # Check blocked commands
        cmd_lower = command.lower().strip()
        for blocked in BLOCKED_COMMANDS:
            if blocked in cmd_lower:
                raise PermissionError(f"Command blocked for safety: {blocked}")

        try:
            if sys.platform == "win32":
                cmd_parts = ["powershell", "-Command", command]
            else:
                cmd_parts = ["sh", "-c", command]

            process = await asyncio.create_subprocess_exec(
                *cmd_parts,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=working_directory,
            )

            try:
                stdout_bytes, stderr_bytes = await asyncio.wait_for(
                    process.communicate(), timeout=timeout
                )
                stdout = stdout_bytes.decode("utf-8", errors="replace")
                stderr = stderr_bytes.decode("utf-8", errors="replace")
                returncode = process.returncode or 0

                return {
                    "command": command,
                    "returncode": returncode,
                    "stdout": stdout[:10000],
                    "stderr": stderr[:5000],
                    "truncated": len(stdout) > 10000 or len(stderr) > 5000,
                    "summary": stdout.strip()[:200] if stdout.strip() else "Command executed",
                }

            except asyncio.TimeoutError:
                process.kill()
                raise RuntimeError(f"Command timed out after {timeout}s")

        except FileNotFoundError:
            raise RuntimeError("Shell not found")
        except Exception as exc:
            logger.exception("Command execution failed")
            raise RuntimeError(f"Failed to execute command: {exc}") from exc

    async def execute_script(
        self,
        script: str,
        shell: str = "powershell" if sys.platform == "win32" else "bash",
    ) -> dict[str, Any]:
        """Execute a multi-line script."""
        return await self.execute(script, timeout=60)
