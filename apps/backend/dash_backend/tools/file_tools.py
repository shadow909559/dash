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
# Lazy imports to avoid circular dependency during tool discovery.
# These are resolved at call time rather than at module load time.
def _get_fs_service():
    from dash_backend.tools.filesystem.filesystem_service import (
        read_file as _fs_read_file,
        write_file as _fs_write_file,
        list_directory as _fs_list_directory,
        search_files as _fs_search_files,
    )
    return _fs_read_file, _fs_write_file, _fs_list_directory, _fs_search_files


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

        try:
            fs_read_file, _fs_write, _fs_list, _fs_search = _get_fs_service()
            res = fs_read_file(path_str, working_directory=context.working_directory, start_line=start_line, end_line=end_line)
        except FileNotFoundError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File not found: {path_str}",
            )
        except IsADirectoryError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Not a file: {path_str}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to read file: {exc}",
            )

        content = res.get("content", "")
        total_lines = len(content.splitlines())

        if start_line is not None or end_line is not None:
            s = max(0, (start_line or 1) - 1)
            e = min(total_lines, end_line or total_lines)
            lines = content.splitlines()[s:e]
            content = "\n".join(lines)
        else:
            lines = content.splitlines()

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "path": res.get("path"),
                "size_bytes": res.get("size_bytes"),
                "total_lines": total_lines,
                "content": content,
                "lines_returned": len(lines),
            },
            summary=f"Read {len(lines)} lines from {path_str}",
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

        try:
            _fs_read, fs_write_file, _fs_list, _fs_search = _get_fs_service()
            res = fs_write_file(path_str, content, working_directory=context.working_directory, overwrite=overwrite)
        except FileExistsError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"File already exists: {path_str}. Set overwrite=True to replace it.",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Failed to write file: {exc}",
            )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "path": res.get("path"),
                "size_bytes": res.get("size_bytes"),
                "overwrite": overwrite,
            },
            summary=f"Written {res.get('size_bytes', 0)} bytes to {path_str}",
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

        try:
            _fs_read, _fs_write, fs_list_directory, _fs_search = _get_fs_service()
            res = fs_list_directory(path_str, working_directory=context.working_directory, recursive=recursive, pattern=pattern)
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=str(exc),
            )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "path": res.get("path"),
                "entries": res.get("entries"),
                "total_entries": res.get("total_entries"),
                "directories": sum(1 for e in res.get("entries", []) if e["type"] == "directory"),
                "files": sum(1 for e in res.get("entries", []) if e["type"] == "file"),
            },
            summary=f"Listed {res.get('total_entries', 0)} entries in {path_str}",
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

        try:
            _fs_read, _fs_write, _fs_list, fs_search_files = _get_fs_service()
            res = fs_search_files(pattern_str, path_str=path_str, working_directory=context.working_directory, file_pattern=file_pattern, max_results=max_results)
        except FileNotFoundError:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Directory not found: {path_str}",
            )
        except ValueError as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Invalid regex pattern: {exc}",
            )
        except Exception as exc:
            return ToolResult(
                tool_name=self.name,
                status=ToolStatus.ERROR,
                error_message=f"Search failed: {exc}",
            )

        return ToolResult(
            tool_name=self.name,
            status=ToolStatus.SUCCESS,
            output={
                "pattern": res.get("pattern"),
                "search_path": res.get("search_path"),
                "results": res.get("results"),
                "total_matches": res.get("total_matches", 0),
            },
            summary=f"Found {res.get('total_matches', 0)} matches for '{pattern_str}'",
        )