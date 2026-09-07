"""Explorer/file management tools: browse, open, rename, delete, move, copy, search, special folders, drives, recent files."""

from __future__ import annotations

import os
import shutil
import sys
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"

# Map of special folder names to known folder IDs
SPECIAL_FOLDERS = {
    "desktop": Path.home() / "Desktop",
    "downloads": Path.home() / "Downloads",
    "documents": Path.home() / "Documents",
    "pictures": Path.home() / "Pictures",
    "videos": Path.home() / "Videos",
    "music": Path.home() / "Music",
    "home": Path.home(),
}


def _resolve_special(path: str) -> Path:
    """Resolve a special folder name to actual path."""
    if path.lower() in SPECIAL_FOLDERS:
        return SPECIAL_FOLDERS[path.lower()]
    return Path(path)


class BrowseFoldersTool(BaseTool):
    name = "browse_folder"
    description = "List contents of a directory with file details."
    parameters = [
        ToolParameter("path", "Directory path to browse", required=False, default="."),
        ToolParameter("show_hidden", "Show hidden files", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".")
        show_hidden = kwargs.get("show_hidden", False)
        try:
            p = _resolve_special(path_str).resolve()
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Path not found: {p}")
            if not p.is_dir():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not a directory: {p}")
            entries = []
            for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
                if entry.name.startswith(".") and not show_hidden:
                    continue
                try:
                    stat = entry.stat()
                    entries.append({
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "path": str(entry.resolve()),
                    })
                except (OSError, PermissionError):
                    continue
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                "path": str(p), "entries": entries, "count": len(entries),
            }, summary=f"Browsed {p.name} ({len(entries)} items)")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class OpenFolderTool(BaseTool):
    name = "open_folder"
    description = "Open a folder in Windows Explorer."
    parameters = [ToolParameter("path", "Folder path to open", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = _resolve_special(path_str)
            if IS_WINDOWS:
                os.startfile(str(p))
            else:
                subprocess.run(["xdg-open", str(p)], capture_output=True, timeout=10)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Opened folder: {p}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class OpenFileTool(BaseTool):
    name = "open_file"
    description = "Open a file with its default application."
    parameters = [ToolParameter("path", "File path to open", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = _resolve_special(path_str)
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"File not found: {p}")
            if IS_WINDOWS:
                os.startfile(str(p))
            else:
                subprocess.run(["xdg-open", str(p)], capture_output=True, timeout=10)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Opened file: {p.name}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RenameFileTool(BaseTool):
    name = "rename_item"
    description = "Rename a file or folder."
    parameters = [
        ToolParameter("path", "Path to the file/folder", required=True),
        ToolParameter("new_name", "New name", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        new_name = kwargs.get("new_name")
        if not path_str or not new_name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path and new_name required")
        try:
            p = Path(path_str)
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not found: {p}")
            new_path = p.parent / new_name
            p.rename(new_path)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Renamed to {new_name}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class DeleteFileTool(BaseTool):
    name = "delete_item"
    description = "Delete a file or folder (to Recycle Bin on Windows, or permanently)."
    parameters = [
        ToolParameter("path", "Path to delete", required=True),
        ToolParameter("permanent", "Permanently delete", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        permanent = kwargs.get("permanent", False)
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = Path(path_str)
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not found: {p}")
            if permanent or not IS_WINDOWS:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Deleted {p.name}")
            else:
                import ctypes
                FO_DELETE = 3
                FOF_ALLOWUNDO = 0x40
                buf = ctypes.create_unicode_buffer(str(p) + "\0\0")
                ctypes.windll.shell32.SHFileOperationW(
                    ctypes.byref(ctypes.c_int(0)),
                    ctypes.byref(ctypes.c_int(FO_DELETE)),
                    buf, None,
                    ctypes.byref(ctypes.c_int(FOF_ALLOWUNDO)),
                    0,
                )
                return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Moved {p.name} to Recycle Bin")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class MoveFileTool(BaseTool):
    name = "move_item"
    description = "Move a file or folder to a new location."
    parameters = [
        ToolParameter("source", "Source path", required=True),
        ToolParameter("destination", "Destination path", required=True),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        src = kwargs.get("source")
        dst = kwargs.get("destination")
        if not src or not dst:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="source and destination required")
        try:
            src_path = Path(src)
            dst_path = Path(dst)
            if not src_path.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Source not found: {src}")
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src_path), str(dst_path))
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Moved to {dst_path.name}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CopyFileTool(BaseTool):
    name = "copy_item"
    description = "Copy a file or folder to a new location."
    parameters = [
        ToolParameter("source", "Source path", required=True),
        ToolParameter("destination", "Destination path", required=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        src = kwargs.get("source")
        dst = kwargs.get("destination")
        if not src or not dst:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="source and destination required")
        try:
            src_path = Path(src)
            dst_path = Path(dst)
            if not src_path.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Source not found: {src}")
            dst_path.parent.mkdir(parents=True, exist_ok=True)
            if src_path.is_dir():
                shutil.copytree(src_path, dst_path)
            else:
                shutil.copy2(src_path, dst_path)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Copied to {dst_path.name}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SearchExplorerTool(BaseTool):
    name = "search_explorer"
    description = "Search for files and folders by name pattern."
    parameters = [
        ToolParameter("pattern", "Filename pattern or glob", required=True),
        ToolParameter("path", "Starting directory", required=False, default="."),
        ToolParameter("max_results", "Maximum results", type="integer", required=False, default=50),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        pattern = kwargs.get("pattern")
        path_str = kwargs.get("path", ".")
        max_results = int(kwargs.get("max_results", 50))
        if not pattern:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="pattern required")
        try:
            p = _resolve_special(path_str).resolve()
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Path not found: {p}")
            results = []
            for entry in p.rglob(pattern):
                try:
                    results.append({
                        "name": entry.name, "path": str(entry.resolve()),
                        "type": "directory" if entry.is_dir() else "file",
                        "size": entry.stat().st_size if entry.is_file() else 0,
                    })
                except (OSError, PermissionError):
                    pass
                if len(results) >= max_results:
                    break
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={
                "pattern": pattern, "path": str(p), "results": results, "count": len(results),
            }, summary=f"Found {len(results)} items matching '{pattern}'")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SpecialFoldersTool(BaseTool):
    name = "list_special_folders"
    description = "List special system folders (Desktop, Downloads, Documents, etc.)."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        folders = {}
        for name, path in SPECIAL_FOLDERS.items():
            try:
                if path.exists():
                    folders[name] = str(path.resolve())
            except Exception:
                pass
        return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"folders": folders}, summary=f"Found {len(folders)} special folders")


class EnumerateDrivesTool(BaseTool):
    name = "enumerate_drives"
    description = "List all drives (local, USB, network, external)."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            drives = []
            if IS_WINDOWS:
                import ctypes
                import string
                bitmask = ctypes.windll.kernel32.GetLogicalDrives()
                for letter in string.ascii_uppercase:
                    if bitmask & 1:
                        drive = f"{letter}:\\"
                        try:
                            drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                            type_names = {0: "unknown", 1: "root_not_found", 2: "removable",
                                         3: "fixed", 4: "network", 5: "cdrom", 6: "ramdisk"}
                            drives.append({"letter": drive, "type": type_names.get(drive_type, "unknown")})
                        except Exception:
                            pass
                    bitmask >>= 1
            else:
                for mount in Path("/media").iterdir():
                    drives.append({"letter": str(mount), "type": "external"})
                for mount in Path("/mnt").iterdir():
                    drives.append({"letter": str(mount), "type": "external"})
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"drives": drives}, summary=f"Found {len(drives)} drives")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RecentFilesTool(BaseTool):
    name = "list_recent_files"
    description = "List recently accessed files from the system's recent items."
    parameters = [ToolParameter("limit", "Maximum files to return", type="integer", required=False, default=30)]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        limit = int(kwargs.get("limit", 30))
        try:
            recent_dir = Path.home() / "Recent" if IS_WINDOWS else Path.home() / ".local/share/recently-used.xbel"
            files = []
            if recent_dir.exists() and recent_dir.is_dir():
                entries = sorted(recent_dir.iterdir(), key=lambda e: e.stat().st_mtime, reverse=True)
                for entry in entries[:limit]:
                    try:
                        link = entry.resolve()
                        if link.exists():
                            files.append({"name": link.name, "path": str(link), "last_accessed": datetime.fromtimestamp(link.stat().st_atime).isoformat()})
                    except Exception:
                        pass
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"recent_files": files}, summary=f"Found {len(files)} recent files")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))
