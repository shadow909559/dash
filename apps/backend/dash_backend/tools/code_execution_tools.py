"""Code Execution Tools — let DASH write and run scripts.

This is the single biggest capability upgrade: instead of being limited
to pre-built tools, DASH can now create any solution by writing code.

Two tools:
1. code_execute: Run Python or Bash code in a sandboxed subprocess
2. code_read: Read a file's contents (so DASH can inspect what it wrote)
"""

from __future__ import annotations

import asyncio
import os
import tempfile
import traceback
from pathlib import Path
from typing import Any

from dash_backend.tools.base_tool import BaseTool, PermissionLevel, ToolContext, ToolParameter
from dash_backend.tools.tool_result import ToolResult, ToolStatus


EXECUTION_TIMEOUT = 30  # seconds
MAX_OUTPUT_CHARS = 10000  # truncate output beyond this
WORKSPACE = Path.home() / "Desktop" / "dash"


class CodeExecuteTool(BaseTool):
    """Execute Python or Bash code in a sandboxed subprocess.

    The agent writes code, this tool runs it and returns stdout/stderr.
    Supports both Python scripts and Bash/PowerShell commands.
    """

    name = "code_execute"
    description = (
        "Execute Python code or shell commands in a sandboxed subprocess. "
        "Returns stdout, stderr, and exit code. Use this to solve problems "
        "that no other tool handles — write any Python script or run any "
        "shell command. Working directory is the DASH workspace."
    )
    parameters = [
        ToolParameter(
            "code",
            "The Python code or shell command to execute. For Python, use "
            "asyncio.run() for async code. For shell, prefix with 'bash -c' "
            "or 'powershell -Command'.",
            type="string",
            required=True,
        ),
        ToolParameter(
            "language",
            "Language: 'python' (default), 'bash', or 'powershell'.",
            type="string",
            required=False,
            default="python",
            enum=["python", "bash", "powershell"],
        ),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "code"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        code = kwargs.get("code", "")
        language = kwargs.get("language", "python")

        if not code.strip():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No code provided",
            )

        # Truncate very long code
        if len(code) > 50000:
            code = code[:50000]
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="Code too long (max 50KB). Break into smaller scripts.",
            )

        try:
            if language == "python":
                result = await self._run_python(code)
            elif language == "bash":
                result = await self._run_shell(["bash", "-c", code])
            elif language == "powershell":
                result = await self._run_shell(["powershell", "-Command", code])
            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Unsupported language: {language}",
                )

            return result
        except asyncio.TimeoutError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.TIMEOUT,
                error_message=f"Code execution timed out after {EXECUTION_TIMEOUT}s",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Execution failed: {exc}",
                raw_output=traceback.format_exc(),
            )

    async def _run_python(self, code: str) -> ToolResult:
        """Run Python code in a subprocess."""
        # Write to a temp file and execute it
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".py", delete=False, dir=str(WORKSPACE),
            encoding="utf-8",
        ) as f:
            f.write(code)
            tmp_path = f.name

        try:
            proc = await asyncio.create_subprocess_exec(
                "python", tmp_path,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(WORKSPACE),
                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
            )
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(), timeout=EXECUTION_TIMEOUT,
            )

            stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
            stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
            exit_code = proc.returncode or 0

            if exit_code == 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.SUCCESS,
                    output={"stdout": stdout_str, "exit_code": exit_code},
                    summary=stdout_str[:200] if stdout_str else "Executed successfully (no output)",
                    raw_output=stdout_str,
                )
            else:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    output={"stdout": stdout_str, "stderr": stderr_str, "exit_code": exit_code},
                    summary=f"Script failed (exit code {exit_code}): {stderr_str[:200]}",
                    error_message=stderr_str[:500],
                    raw_output=stdout_str + "\n--- STDERR ---\n" + stderr_str,
                )
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

    async def _run_shell(self, cmd: list[str]) -> ToolResult:
        """Run a shell command."""
        proc = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=str(WORKSPACE),
        )
        stdout, stderr = await asyncio.wait_for(
            proc.communicate(), timeout=EXECUTION_TIMEOUT,
        )

        stdout_str = stdout.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
        stderr_str = stderr.decode("utf-8", errors="replace")[:MAX_OUTPUT_CHARS]
        exit_code = proc.returncode or 0

        if exit_code == 0:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"stdout": stdout_str, "exit_code": exit_code},
                summary=stdout_str[:200] if stdout_str else "Command executed successfully",
                raw_output=stdout_str,
            )
        else:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                output={"stdout": stdout_str, "stderr": stderr_str, "exit_code": exit_code},
                summary=f"Command failed (exit code {exit_code}): {stderr_str[:200]}",
                error_message=stderr_str[:500],
                raw_output=stdout_str + "\n--- STDERR ---\n" + stderr_str,
            )


class CodeReadTool(BaseTool):
    """Read a file's contents so DASH can inspect code it wrote or existing files."""

    name = "code_read"
    description = (
        "Read the contents of a file. Use this to inspect files you created, "
        "check configuration, or read source code. Returns the full file "
        "content (truncated at 50KB)."
    )
    parameters = [
        ToolParameter(
            "path",
            "File path to read. Relative paths are resolved from the DASH workspace.",
            type="string",
            required=True,
        ),
    ]
    permission_level = PermissionLevel.AUTO
    category = "code"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided",
            )

        # Resolve relative paths from workspace
        p = Path(path_str)
        if not p.is_absolute():
            p = WORKSPACE / p

        if not p.exists():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File not found: {p}",
            )

        if not p.is_file():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Not a file: {p}",
            )

        try:
            content = p.read_text(encoding="utf-8", errors="replace")[:50000]
            lines = content.count("\n") + 1
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"content": content, "path": str(p), "lines": lines},
                summary=f"Read {lines} lines from {p.name}",
                raw_output=content,
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to read {p}: {exc}",
            )


class CodeWriteTool(BaseTool):
    """Write code to a file so DASH can create scripts and solutions."""

    name = "code_write"
    description = (
        "Write content to a file. Use this to create Python scripts, "
        "configuration files, or any text file. Creates parent directories "
        "automatically. Returns the number of lines written."
    )
    parameters = [
        ToolParameter(
            "path",
            "File path to write. Relative paths are resolved from the DASH workspace.",
            type="string",
            required=True,
        ),
        ToolParameter(
            "content",
            "The content to write to the file.",
            type="string",
            required=True,
        ),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "code"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        content = kwargs.get("content", "")

        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided",
            )

        p = Path(path_str)
        if not p.is_absolute():
            p = WORKSPACE / p

        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            lines = content.count("\n") + 1
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"path": str(p), "lines": lines, "bytes": len(content.encode("utf-8"))},
                summary=f"Wrote {lines} lines to {p.name}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to write {p}: {exc}",
            )
