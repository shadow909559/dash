from __future__ import annotations

from dash_backend.tools.tool_registry import get_registry
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus
from dash_backend.tools.filesystem.filesystem_service import (
    read_file,
    write_file,
    list_directory,
    search_files,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ReadFileTool(BaseTool):
    name = "read_file"
    description = "Read the contents of a file within the sandbox."
    parameters = [
        ToolParameter("path", "Path to the file", required=True),
        ToolParameter("start_line", "Start line (1-indexed)", type="integer", required=False),
        ToolParameter("end_line", "End line (inclusive, 1-indexed)", type="integer", required=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs):
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            result = read_file(
                path_str,
                working_directory=context.working_directory or ".",
                start_line=kwargs.get("start_line"),
                end_line=kwargs.get("end_line"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=f"Read {result.get('total_lines', 0)} lines")
        except FileNotFoundError as e:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(e))
        except Exception as e:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(e))


class WriteFileTool(BaseTool):
    name = "write_file"
    description = "Write content to a file within the sandbox."
    parameters = [
        ToolParameter("path", "Path to the file", required=True),
        ToolParameter("content", "Content to write", required=True),
        ToolParameter("overwrite", "Overwrite if exists", type="boolean", required=False, default=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs):
        path_str = kwargs.get("path")
        content = kwargs.get("content")
        if not path_str or content is None:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path and content required")
        try:
            result = write_file(path_str, content, working_directory=context.working_directory or ".",
                                overwrite=kwargs.get("overwrite", True))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result, summary=f"Wrote {result.get('size_bytes', 0)} bytes")
        except Exception as e:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(e))


class ListDirectoryTool(BaseTool):
    name = "list_directory"
    description = "List contents of a directory within the sandbox."
    parameters = [
        ToolParameter("path", "Directory path", required=False, default="."),
        ToolParameter("recursive", "List recursively", type="boolean", required=False, default=False),
        ToolParameter("pattern", "Glob pattern to filter", required=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs):
        try:
            result = list_directory(
                path_str=kwargs.get("path", "."),
                working_directory=context.working_directory or ".",
                recursive=kwargs.get("recursive", False),
                pattern=kwargs.get("pattern"),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result,
                              summary=f"Listed {result.get('total_entries', 0)} entries")
        except Exception as e:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(e))


class SearchFilesTool(BaseTool):
    name = "search_files_content"
    description = "Search for text content within files using regex."
    parameters = [
        ToolParameter("pattern", "Regex pattern to search for", required=True),
        ToolParameter("path", "Directory to search in", required=False, default="."),
        ToolParameter("file_pattern", "Glob pattern to filter files", required=False),
        ToolParameter("max_results", "Maximum results", type="integer", required=False, default=50),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs):
        pattern = kwargs.get("pattern")
        if not pattern:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pattern required")
        try:
            result = search_files(
                pattern=pattern,
                path_str=kwargs.get("path", "."),
                working_directory=context.working_directory or ".",
                file_pattern=kwargs.get("file_pattern"),
                max_results=int(kwargs.get("max_results", 50)),
            )
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=result,
                              summary=f"Found {result.get('total_matches', 0)} matches")
        except Exception as e:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(e))


def register_filesystem_tools() -> None:
    registry = get_registry()
    tool_classes = [ReadFileTool, WriteFileTool, ListDirectoryTool, SearchFilesTool]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        if registry.get(name) is None:
            try:
                registry.register(cls())
            except Exception:
                continue


# Run registration on import (idempotent)
register_filesystem_tools()
