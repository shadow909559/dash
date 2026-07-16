"""Git tools - status, diff, commit, branch operations."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_result import ToolResult, ToolStatus


def _run_git(
    args: list[str],
    cwd: str | None = None,
    timeout: float = 30.0,
) -> tuple[str, str, int]:
    """Run a git command and return (stdout, stderr, returncode)."""
    try:
        result = subprocess.run(
            ["git"] + args,
            capture_output=True,
            text=True,
            cwd=cwd or ".",
            timeout=timeout,
        )
        return result.stdout.strip(), result.stderr.strip(), result.returncode
    except subprocess.TimeoutExpired:
        return "", "Command timed out", -1
    except FileNotFoundError:
        return "", "Git not found. Is git installed?", -1
    except Exception as exc:
        return "", str(exc), -1


class GitStatusTool(BaseTool):
    """Show git status."""

    name = "git_status"
    description = "Show the working tree status, including staged, unstaged, and untracked files."
    category = "git"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cwd = context.working_directory or "."
        stdout, stderr, rc = _run_git(["status", "--porcelain"], cwd=cwd)

        if rc != 0:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Git status failed: {stderr}",
            )

        lines = [line for line in stdout.split("\n") if line.strip()]
        staged = [l[3:] for l in lines if l.startswith(("M ", "A ", "D ", "R ", "C "))]
        unstaged = [l[3:] for l in lines if l.startswith((" M", " D", " R", " C", "??"))]
        untracked = [l[3:] for l in lines if l.startswith("??")]

        # Get branch name
        branch_out, _, _ = _run_git(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "branch": branch_out or "unknown",
                "total_changes": len(lines),
                "staged": staged,
                "unstaged": unstaged,
                "untracked": untracked,
                "raw": stdout,
            },
            summary=f"Git status: {len(staged)} staged, {len(unstaged)} unstaged, {len(untracked)} untracked (branch: {branch_out})",
        )


class GitDiffTool(BaseTool):
    """Show git diff."""

    name = "git_diff"
    description = "Show changes between commits, commit and working tree, etc."
    category = "git"
    parameters = [
        ToolParameter(
            name="staged",
            description="Show staged changes (--cached).",
            type="boolean",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="path",
            description="Limit diff to a specific file path.",
            type="string",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cwd = context.working_directory or "."
        staged = kwargs.get("staged", False)

        args = ["diff"]
        if staged:
            args.append("--cached")

        path = kwargs.get("path")
        if path:
            args.append("--")
            args.append(path)

        stdout, stderr, rc = _run_git(args, cwd=cwd)

        if rc != 0:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Git diff failed: {stderr}",
            )

        lines = stdout.split("\n")
        added = sum(1 for l in lines if l.startswith("+") and not l.startswith("+++"))
        removed = sum(1 for l in lines if l.startswith("-") and not l.startswith("---"))

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "diff": stdout,
                "lines_added": added,
                "lines_removed": removed,
                "total_lines": len(lines),
                "staged": staged,
            },
            summary=f"Git diff: +{added} -{removed} lines",
        )


class GitCommitTool(BaseTool):
    """Create a git commit."""

    name = "git_commit"
    description = "Create a git commit with the given message. Stages all changes first."
    category = "git"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="message",
            description="Commit message.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="add_all",
            description="Stage all changes before committing (-a flag).",
            type="boolean",
            required=False,
            default=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cwd = context.working_directory or "."
        message = kwargs.get("message", "")
        add_all = kwargs.get("add_all", True)

        if not message:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="Commit message is required.",
            )

        if add_all:
            stdout, stderr, rc = _run_git(["add", "-A"], cwd=cwd)
            if rc != 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Git add failed: {stderr}",
                )

        stdout, stderr, rc = _run_git(["commit", "-m", message], cwd=cwd)

        if rc != 0:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Git commit failed: {stderr}",
            )

        # Get commit hash
        hash_out, _, _ = _run_git(["rev-parse", "--short", "HEAD"], cwd=cwd)

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "hash": hash_out,
                "message": message,
                "output": stdout,
            },
            summary=f"Committed {hash_out}: {message}",
        )


class GitBranchTool(BaseTool):
    """List and manage git branches."""

    name = "git_branch"
    description = "List git branches, optionally creating or switching branches."
    category = "git"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="action",
            description="Branch operation to perform.",
            type="string",
            required=False,
            default="list",
            enum=["list", "create", "switch", "delete"],
        ),
        ToolParameter(
            name="branch_name",
            description="Branch name (required for create, switch, delete).",
            type="string",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        cwd = context.working_directory or "."
        action = kwargs.get("action", "list")
        branch_name = kwargs.get("branch_name", "")

        if action == "list":
            stdout, stderr, rc = _run_git(["branch", "-a"], cwd=cwd)
            if rc != 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Git branch failed: {stderr}",
                )
            branches = [b.strip().replace("* ", "") for b in stdout.split("\n") if b.strip()]
            current = ""
            for b in stdout.split("\n"):
                if b.strip().startswith("*"):
                    current = b.strip()[2:]

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "branches": branches,
                    "current": current,
                    "total": len(branches),
                },
                summary=f"Git branches: {len(branches)} total (current: {current})",
            )

        elif action == "create":
            if not branch_name:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="branch_name is required for 'create'.",
                )
            stdout, stderr, rc = _run_git(["branch", branch_name], cwd=cwd)
            if rc != 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Failed to create branch: {stderr}",
                )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"branch": branch_name},
                summary=f"Created branch '{branch_name}'",
            )

        elif action == "switch":
            if not branch_name:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="branch_name is required for 'switch'.",
                )
            stdout, stderr, rc = _run_git(["checkout", branch_name], cwd=cwd)
            if rc != 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Failed to switch branch: {stderr}",
                )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"branch": branch_name},
                summary=f"Switched to branch '{branch_name}'",
            )

        elif action == "delete":
            if not branch_name:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="branch_name is required for 'delete'.",
                )
            stdout, stderr, rc = _run_git(["branch", "-d", branch_name], cwd=cwd)
            if rc != 0:
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Failed to delete branch: {stderr}",
                )
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"branch": branch_name},
                summary=f"Deleted branch '{branch_name}'",
            )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.ERROR,
            error_message=f"Unknown action: {action}",
        )