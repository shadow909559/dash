"""Folder management tools - create, copy, move, delete directories and projects."""

from __future__ import annotations

import shutil
from pathlib import Path
from typing import Any

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class CreateDirectoryTool(BaseTool):
    """Create a new directory."""

    name = "create_directory"
    description = "Create a new directory at the specified path. Creates parent directories if needed."
    category = "filesystem"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="path",
            description="Path to the directory to create.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="exist_ok",
            description="If True, no error if directory already exists.",
            type="boolean",
            required=False,
            default=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        exist_ok = kwargs.get("exist_ok", True)

        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided.",
            )

        try:
            base = Path(context.working_directory).resolve() if context.working_directory else Path.cwd()
            target = (base / path_str).resolve()

            # Security: prevent directory traversal
            if not str(target).startswith(str(base)):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Path traversal detected: {path_str}",
                )

            target.mkdir(parents=True, exist_ok=exist_ok)

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "path": str(target),
                    "created": not target.exists() or exist_ok,
                },
                summary=f"Created directory: {target}",
            )
        except PermissionError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Permission denied: {path_str}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to create directory: {exc}",
            )


class DeleteDirectoryTool(BaseTool):
    """Delete a directory and its contents."""

    name = "delete_directory"
    description = "Delete a directory and all its contents recursively."
    category = "filesystem"
    permission_level = PermissionLevel.RESTRICTED
    parameters = [
        ToolParameter(
            name="path",
            description="Path to the directory to delete.",
            type="string",
            required=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")

        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided.",
            )

        try:
            base = Path(context.working_directory).resolve() if context.working_directory else Path.cwd()
            target = (base / path_str).resolve()

            if not str(target).startswith(str(base)):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Path traversal detected: {path_str}",
                )

            if not target.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Directory not found: {path_str}",
                )

            shutil.rmtree(target)

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={"path": str(target)},
                summary=f"Deleted directory: {target}",
            )
        except PermissionError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Permission denied: {path_str}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to delete directory: {exc}",
            )


class CopyPathTool(BaseTool):
    """Copy a file or directory."""

    name = "copy_path"
    description = "Copy a file or directory from source to destination."
    category = "filesystem"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="source",
            description="Source path to copy from.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="destination",
            description="Destination path to copy to.",
            type="string",
            required=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        source = kwargs.get("source", "")
        destination = kwargs.get("destination", "")

        if not source or not destination:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="Both source and destination are required.",
            )

        try:
            base = Path(context.working_directory).resolve() if context.working_directory else Path.cwd()
            src = (base / source).resolve()
            dst = (base / destination).resolve()

            if not str(src).startswith(str(base)) or not str(dst).startswith(str(base)):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="Path traversal detected.",
                )

            if not src.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Source not found: {source}",
                )

            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=True)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "source": str(src),
                    "destination": str(dst),
                },
                summary=f"Copied {source} to {destination}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to copy: {exc}",
            )


class MovePathTool(BaseTool):
    """Move a file or directory."""

    name = "move_path"
    description = "Move a file or directory from source to destination."
    category = "filesystem"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="source",
            description="Source path to move from.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="destination",
            description="Destination path to move to.",
            type="string",
            required=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        source = kwargs.get("source", "")
        destination = kwargs.get("destination", "")

        if not source or not destination:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="Both source and destination are required.",
            )

        try:
            base = Path(context.working_directory).resolve() if context.working_directory else Path.cwd()
            src = (base / source).resolve()
            dst = (base / destination).resolve()

            if not str(src).startswith(str(base)) or not str(dst).startswith(str(base)):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="Path traversal detected.",
                )

            if not src.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Source not found: {source}",
                )

            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "source": str(src),
                    "destination": str(dst),
                },
                summary=f"Moved {source} to {destination}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to move: {exc}",
            )


class CreateProjectTool(BaseTool):
    """Create a new project directory with standard structure."""

    name = "create_project"
    description = "Create a new project directory with standard structure (src, tests, docs, etc.)."
    category = "development"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="name",
            description="Project name.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="path",
            description="Parent directory for the project (defaults to working directory).",
            type="string",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="project_type",
            description="Type of project to scaffold.",
            type="string",
            required=False,
            default="python",
            enum=["python", "node", "flutter", "generic"],
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name", "")
        path_str = kwargs.get("path", ".")
        project_type = kwargs.get("project_type", "python")

        if not name:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="Project name is required.",
            )

        try:
            base = Path(context.working_directory).resolve() if context.working_directory else Path.cwd()
            project_dir = (base / path_str / name).resolve()

            if not str(project_dir).startswith(str(base)):
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message="Path traversal detected.",
                )

            if project_dir.exists():
                return ToolResult(
                    tool_name=self.name,
                    status=ToolStatus.ERROR,
                    error_message=f"Project already exists: {project_dir}",
                )

            # Create standard structure
            dirs = ["src", "tests", "docs"]
            if project_type == "python":
                dirs.extend([f"src/{name}", "config"])
            elif project_type == "node":
                dirs.extend(["src", "public", "config"])
            elif project_type == "flutter":
                dirs.extend(["lib", "test", "android", "ios", "web"])

            for d in dirs:
                (project_dir / d).mkdir(parents=True, exist_ok=True)

            # Create README
            readme_path = project_dir / "README.md"
            readme_path.write_text(f"# {name}\n\nProject created by DASH.\n")

            # Create .gitignore
            gitignore_path = project_dir / ".gitignore"
            gitignore_content = {
                "python": "__pycache__/\n*.pyc\n.env\nvenv/\n.venv/\n",
                "node": "node_modules/\n.env\ndist/\n",
                "flutter": "build/\n.dart_tool/\n.packages\n",
                "generic": ".env\n*.log\ntmp/\n",
            }
            gitignore_path.write_text(gitignore_content.get(project_type, ""))

            created_dirs = [str(d) for d in project_dir.rglob("*") if d.is_dir()]

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "project_path": str(project_dir),
                    "project_type": project_type,
                    "directories_created": created_dirs,
                },
                summary=f"Created {project_type} project '{name}' at {project_dir}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to create project: {exc}",
            )