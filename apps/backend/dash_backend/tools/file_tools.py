"""File system tools - read, write, list, search files and directories."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

from dash_backend.tools.base_tool import (
    BaseTool,
    PermissionLevel,
    ToolContext,
    ToolParameter,
)
from dash_backend.tools.tool_result import ToolResult, ToolStatus


class ReadFileTool(BaseTool):
    """Read the contents of a file."""

    name = "read_file"
    description = "Read the contents of a file at the specified path. Supports text files up to 100KB."
    category = "filesystem"
    parameters = [
        ToolParameter(
            name="path",
            description="Path to the file to read (absolute or relative to working directory).",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="start_line",
            description="Line number to start reading from (1-indexed).",
            type="number",
            required=False,
        ),
        ToolParameter(
            name="end_line",
            description="Line number to stop reading at (inclusive).",
            type="number",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        start_line = kwargs.get("start_line")
        end_line = kwargs.get("end_line")

        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided.",
            )

        # Resolve path
        base = Path(context.working_directory or ".").resolve()
        file_path = (base / path_str).resolve()

        # Security: prevent path traversal
        try:
            file_path.relative_to(base)
        except ValueError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Path traversal detected: '{path_str}' is outside the working directory.",
            )

        if not file_path.exists():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File not found: {file_path}",
            )

        if not file_path.is_file():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Not a file: {file_path}",
            )

        # Check file size (limit to 100KB)
        max_size = 100 * 1024
        if file_path.stat().st_size > max_size:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File too large ({file_path.stat().st_size / 1024:.1f}KB). Maximum is 100KB.",
            )

        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
            lines = content.splitlines()
            total_lines = len(lines)

            if start_line is not None or end_line is not None:
                s = max(0, (start_line or 1) - 1)
                e = min(total_lines, end_line or total_lines)
                lines = lines[s:e]
                content = "\n".join(lines)

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "path": str(file_path),
                    "size_bytes": file_path.stat().st_size,
                    "total_lines": total_lines,
                    "content": content,
                    "lines_returned": len(lines),
                },
                summary=f"Read {len(lines)} lines from {file_path.name}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to read file: {exc}",
            )


class WriteFileTool(BaseTool):
    """Write content to a file."""

    name = "write_file"
    description = "Write content to a file. Creates the file and any necessary directories."
    category = "filesystem"
    permission_level = PermissionLevel.CONFIRM
    parameters = [
        ToolParameter(
            name="path",
            description="Path to the file to write (absolute or relative to working directory).",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="content",
            description="Content to write to the file.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="overwrite",
            description="Whether to overwrite an existing file. Defaults to True.",
            type="boolean",
            required=False,
            default=True,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", True)

        if not path_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No path provided.",
            )

        base = Path(context.working_directory or ".").resolve()
        file_path = (base / path_str).resolve()

        # Security: prevent path traversal
        try:
            file_path.relative_to(base)
        except ValueError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Path traversal detected: '{path_str}' is outside the working directory.",
            )

        if file_path.exists() and not overwrite:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File already exists: {file_path}. Set overwrite=True to replace it.",
            )

        try:
            file_path.parent.mkdir(parents=True, exist_ok=True)
            file_path.write_text(content, encoding="utf-8")
            size = file_path.stat().st_size

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "path": str(file_path),
                    "size_bytes": size,
                    "overwrite": overwrite and file_path.exists(),
                },
                summary=f"Written {size} bytes to {file_path.name}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to write file: {exc}",
            )


class ListDirectoryTool(BaseTool):
    """List files and directories."""

    name = "list_directory"
    description = "List files and directories at the specified path."
    category = "filesystem"
    parameters = [
        ToolParameter(
            name="path",
            description="Directory path to list (defaults to working directory).",
            type="string",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="recursive",
            description="Whether to list recursively.",
            type="boolean",
            required=False,
            default=False,
        ),
        ToolParameter(
            name="pattern",
            description="Glob pattern to filter (e.g., '*.py', '*.txt').",
            type="string",
            required=False,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".")
        recursive = kwargs.get("recursive", False)
        pattern = kwargs.get("pattern")

        base = Path(context.working_directory or ".").resolve()
        dir_path = (base / path_str).resolve()

        try:
            dir_path.relative_to(base)
        except ValueError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Path traversal detected: '{path_str}' is outside the working directory.",
            )

        if not dir_path.exists():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Directory not found: {dir_path}",
            )

        if not dir_path.is_dir():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Not a directory: {dir_path}",
            )

        try:
            entries: list[dict[str, Any]] = []

            if recursive:
                for item in dir_path.rglob("*"):
                    if pattern and not item.match(pattern):
                        continue
                    try:
                        rel = item.relative_to(base)
                    except ValueError:
                        continue
                    entries.append({
                        "name": item.name,
                        "path": str(rel),
                        "type": "directory" if item.is_dir() else "file",
                        "size_bytes": item.stat().st_size if item.is_file() else 0,
                    })
            else:
                for item in dir_path.iterdir():
                    if pattern and not item.match(pattern):
                        continue
                    try:
                        rel = item.relative_to(base)
                    except ValueError:
                        continue
                    entries.append({
                        "name": item.name,
                        "path": str(rel),
                        "type": "directory" if item.is_dir() else "file",
                        "size_bytes": item.stat().st_size if item.is_file() else 0,
                    })

            # Sort: directories first, then by name
            entries.sort(key=lambda e: (0 if e["type"] == "directory" else 1, e["name"]))

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "path": str(dir_path),
                    "entries": entries,
                    "total_entries": len(entries),
                    "directories": sum(1 for e in entries if e["type"] == "directory"),
                    "files": sum(1 for e in entries if e["type"] == "file"),
                },
                summary=f"Listed {len(entries)} entries in {dir_path.name}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to list directory: {exc}",
            )


class SearchFilesTool(BaseTool):
    """Search files using regex patterns."""

    name = "search_files"
    description = "Search for text patterns in files using regular expressions."
    category = "filesystem"
    parameters = [
        ToolParameter(
            name="pattern",
            description="Regular expression pattern to search for.",
            type="string",
            required=True,
        ),
        ToolParameter(
            name="path",
            description="Directory to search in (defaults to working directory).",
            type="string",
            required=False,
            default=".",
        ),
        ToolParameter(
            name="file_pattern",
            description="Glob pattern to filter files (e.g., '*.py', '*.ts').",
            type="string",
            required=False,
        ),
        ToolParameter(
            name="max_results",
            description="Maximum number of results to return.",
            type="number",
            required=False,
            default=50,
        ),
    ]

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        pattern_str = kwargs.get("pattern", "")
        path_str = kwargs.get("path", ".")
        file_pattern = kwargs.get("file_pattern")
        max_results = kwargs.get("max_results", 50)

        if not pattern_str:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message="No search pattern provided.",
            )

        base = Path(context.working_directory or ".").resolve()
        search_dir = (base / path_str).resolve()

        try:
            search_dir.relative_to(base)
        except ValueError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Path traversal detected.",
            )

        if not search_dir.is_dir():
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Directory not found: {search_dir}",
            )

        try:
            regex = re.compile(pattern_str, re.IGNORECASE)
        except re.error as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Invalid regex pattern: {exc}",
            )

        results: list[dict[str, Any]] = []
        max_size = 1024 * 1024  # Skip files larger than 1MB

        try:
            for item in search_dir.rglob("*"):
                if not item.is_file():
                    continue
                if file_pattern and not item.match(file_pattern):
                    continue
                if item.stat().st_size > max_size:
                    continue

                if len(results) >= max_results:
                    break

                try:
                    rel_path = str(item.relative_to(base))
                    content = item.read_text(encoding="utf-8", errors="replace")
                    for match in regex.finditer(content):
                        if len(results) >= max_results:
                            break
                        line_num = content[: match.start()].count("\n") + 1
                        start = max(0, match.start() - 40)
                        end = min(len(content), match.end() + 40)
                        context_str = content[start:end].replace("\n", " ").strip()

                        results.append({
                            "file": rel_path,
                            "line": line_num,
                            "match": match.group(),
                            "context": context_str,
                        })
                except (OSError, UnicodeDecodeError):
                    continue

            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.SUCCESS,
                output={
                    "pattern": pattern_str,
                    "search_path": str(search_dir),
                    "results": results,
                    "total_matches": len(results),
                },
                summary=f"Found {len(results)} matches for '{pattern_str}'",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Search failed: {exc}",
            )