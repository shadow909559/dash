"""File system intelligence tools: find large files, find duplicates, create items, zip/unzip, reveal, duplicate, restore.

Extends the existing sandboxed filesystem tools with higher-level "smart" operations
DASH needs for natural-language file management.
"""

from __future__ import annotations

import hashlib
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


def _resolve(path: str) -> Path:
    """Resolve a user-supplied path to an absolute path."""
    return Path(path).expanduser().resolve()


class FindLargeFilesTool(BaseTool):
    name = "find_large_files"
    description = "Find the largest files in a directory, sorted by size."
    parameters = [
        ToolParameter("path", "Directory to scan", required=False, default="."),
        ToolParameter("limit", "Maximum results", type="integer", required=False, default=20),
        ToolParameter("min_size_mb", "Minimum file size in MB to include", type="integer", required=False, default=50),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".")
        limit = int(kwargs.get("limit", 20))
        min_size_mb = int(kwargs.get("min_size_mb", 50))
        try:
            root = _resolve(path_str)
            if not root.exists() or not root.is_dir():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Directory not found: {root}")
            min_bytes = min_size_mb * 1024 * 1024
            large_files = []
            for item in root.rglob("*"):
                try:
                    if item.is_file() and item.stat().st_size >= min_bytes:
                        large_files.append({
                            "name": item.name,
                            "path": str(item),
                            "size_mb": round(item.stat().st_size / (1024 * 1024), 2),
                        })
                except (OSError, PermissionError):
                    continue
            large_files.sort(key=lambda f: f["size_mb"], reverse=True)
            results = large_files[:limit]
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"files": results, "count": len(results), "scanned": str(root)},
                summary=f"Found {len(results)} large files (>{min_size_mb}MB)",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class FindDuplicateFilesTool(BaseTool):
    name = "find_duplicate_files"
    description = "Find duplicate files in a directory using content hashing."
    parameters = [
        ToolParameter("path", "Directory to scan", required=False, default="."),
        ToolParameter("limit", "Maximum duplicate groups to return", type="integer", required=False, default=20),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", ".")
        limit = int(kwargs.get("limit", 20))
        try:
            root = _resolve(path_str)
            if not root.exists() or not root.is_dir():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Directory not found: {root}")

            size_map: dict[int, list[Path]] = {}
            for item in root.rglob("*"):
                try:
                    if item.is_file():
                        size_map.setdefault(item.stat().st_size, []).append(item)
                except (OSError, PermissionError):
                    continue

            duplicate_groups = []
            for size, files in size_map.items():
                if len(files) < 2:
                    continue
                hash_map: dict[str, list[Path]] = {}
                for f in files:
                    try:
                        digest = hashlib.md5(f.read_bytes()).hexdigest()
                        hash_map.setdefault(digest, []).append(f)
                    except (OSError, PermissionError):
                        continue
                for digest, group in hash_map.items():
                    if len(group) > 1:
                        duplicate_groups.append({
                            "size_bytes": size,
                            "files": [str(p) for p in group],
                        })
                        if len(duplicate_groups) >= limit:
                            return ToolResult(
                                tool_name=self.name, status=ToolStatus.SUCCESS,
                                output={"duplicates": duplicate_groups, "count": len(duplicate_groups)},
                                summary=f"Found {len(duplicate_groups)} duplicate groups",
                            )
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"duplicates": duplicate_groups, "count": len(duplicate_groups)},
                summary=f"Found {len(duplicate_groups)} duplicate groups",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CreateFileTool(BaseTool):
    name = "create_file"
    description = "Create a new empty file (or with content) at a path."
    parameters = [
        ToolParameter("path", "Path to the new file", required=True),
        ToolParameter("content", "Optional initial content", required=False, default=""),
        ToolParameter("overwrite", "Overwrite if exists", type="boolean", required=False, default=False),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        content = kwargs.get("content", "")
        overwrite = kwargs.get("overwrite", False)
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = _resolve(path_str)
            if p.exists() and not overwrite:
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"File already exists: {p}")
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(content, encoding="utf-8")
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"path": str(p), "size_bytes": len(content.encode("utf-8"))},
                summary=f"Created file: {p.name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class CreateFolderTool(BaseTool):
    name = "create_folder"
    description = "Create a new folder (directory) at a path."
    parameters = [ToolParameter("path", "Path to the new folder", required=True)]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = _resolve(path_str)
            p.mkdir(parents=True, exist_ok=True)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"path": str(p)}, summary=f"Created folder: {p.name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class ZipTool(BaseTool):
    name = "zip_items"
    description = "Compress a file or folder into a zip archive."
    parameters = [
        ToolParameter("source", "Source path (file or folder) to compress", required=True),
        ToolParameter("destination", "Destination zip path", required=False, default=""),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        src = kwargs.get("source")
        dst = kwargs.get("destination", "")
        if not src:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="source required")
        try:
            src_path = _resolve(src)
            if not src_path.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Source not found: {src}")
            if not dst:
                dst = str(src_path) + ".zip"
            dst_path = _resolve(dst)
            dst_path.parent.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(dst_path, "w", zipfile.ZIP_DEFLATED) as zf:
                if src_path.is_dir():
                    for item in src_path.rglob("*"):
                        if item.is_file():
                            zf.write(item, item.relative_to(src_path.parent))
                else:
                    zf.write(src_path, src_path.name)

            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"source": str(src_path), "archive": str(dst_path)},
                summary=f"Compressed to {dst_path.name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class UnzipTool(BaseTool):
    name = "unzip_items"
    description = "Extract a zip archive to a destination folder."
    parameters = [
        ToolParameter("archive", "Path to zip archive", required=True),
        ToolParameter("destination", "Destination folder", required=False, default=""),
    ]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        archive = kwargs.get("archive")
        dst = kwargs.get("destination", "")
        if not archive:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="archive required")
        try:
            archive_path = _resolve(archive)
            if not archive_path.exists() or not zipfile.is_zipfile(archive_path):
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not a valid zip: {archive}")
            if not dst:
                dst = str(archive_path.parent / archive_path.stem)
            dst_path = _resolve(dst)
            dst_path.mkdir(parents=True, exist_ok=True)

            with zipfile.ZipFile(archive_path, "r") as zf:
                zf.extractall(dst_path)

            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"archive": str(archive_path), "destination": str(dst_path)},
                summary=f"Extracted to {dst_path.name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RevealInExplorerTool(BaseTool):
    name = "reveal_in_explorer"
    description = "Reveal a file or folder in the system file explorer (with it selected)."
    parameters = [ToolParameter("path", "Path to reveal", required=True)]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = _resolve(path_str)
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not found: {p}")
            if IS_WINDOWS:
                import subprocess
                subprocess.Popen(["explorer", "/select,", str(p)])
            else:
                import subprocess
                subprocess.Popen(["xdg-open", str(p if p.is_dir() else p.parent)])
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary=f"Revealed in explorer: {p.name}")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class DuplicateItemTool(BaseTool):
    name = "duplicate_item"
    description = "Create a copy of a file or folder with a ' copy' suffix in the same location."
    parameters = [ToolParameter("path", "Path to duplicate", required=True)]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path")
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            src = _resolve(path_str)
            if not src.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Not found: {src}")
            base = src.stem + " copy" + src.suffix
            dst = src.parent / base
            counter = 1
            while dst.exists():
                dst = src.parent / f"{src.stem} copy {counter}{src.suffix}"
                counter += 1
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"source": str(src), "duplicate": str(dst)},
                summary=f"Duplicated to {dst.name}",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RestoreItemTool(BaseTool):
    name = "restore_from_recycle_bin"
    description = "Restore a file from the Recycle Bin by filename (Windows only)."
    parameters = [ToolParameter("name", "Filename to restore from Recycle Bin", required=True)]
    permission_level = PermissionLevel.CONFIRM
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        name = kwargs.get("name")
        if not name:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="name required")
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import ctypes
            shell32 = ctypes.windll.shell32
            # SHFileOperation with FO_RESTORE is not universally supported; use audible approach.
            # Use the recycle bin via the shell's IFileOperation through explorer is complex.
            # Fallback: use the FOLDERID 'Recycle Bin' shell namespace via 'explorer.exe' restore is not scriptable simply.
            # We provide a best-effort using SHFileOperationW with FO_DELETE undo is not restorable.
            # Instead, expose the recycle bin location and let the user confirm.
            recycle_bin = Path.home() / "AppData" / "Local" / "RecycleBin"
            return ToolResult(
                tool_name=self.name, status=ToolStatus.ERROR,
                error_message="Automated restore from Recycle Bin is not supported. Please restore manually from the Recycle Bin.",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class SearchFilesTool(BaseTool):
    name = "search_files"
    description = "Smart search for files by name/pattern across a directory tree."
    parameters = [
        ToolParameter("query", "Filename keyword or pattern to search for", required=True),
        ToolParameter("path", "Directory to search in", required=False, default="."),
        ToolParameter("limit", "Maximum results", type="integer", required=False, default=25),
        ToolParameter("recursive", "Search subdirectories", type="boolean", required=False, default=True),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        query = kwargs.get("query")
        path_str = kwargs.get("path", ".")
        limit = int(kwargs.get("limit", 25))
        recursive = bool(kwargs.get("recursive", True))
        if not query:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="query required")
        try:
            root = _resolve(path_str)
            if not root.exists() or not root.is_dir():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"Directory not found: {root}")

            q = query.lower()
            matches = []
            iterator = root.rglob("*") if recursive else root.glob("*")
            for item in iterator:
                try:
                    if item.is_file() and q in item.name.lower():
                        matches.append({
                            "name": item.name,
                            "path": str(item),
                            "size_kb": round(item.stat().st_size / 1024, 1),
                        })
                        if len(matches) >= limit:
                            break
                except (OSError, PermissionError):
                    continue

            matches.sort(key=lambda f: f["name"].lower())
            return ToolResult(
                tool_name=self.name, status=ToolStatus.SUCCESS,
                output={"query": query, "results": matches, "count": len(matches), "scanned": str(root)},
                summary=f"Found {len(matches)} matching files",
            )
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


def register_intelligence_tools() -> None:
    """Register file system intelligence tools with the tool registry."""
    from dash_backend.tools.tool_registry import get_registry

    registry = get_registry()
    tool_classes = [
        FindLargeFilesTool,
        FindDuplicateFilesTool,
        CreateFileTool,
        CreateFolderTool,
        ZipTool,
        UnzipTool,
        RevealInExplorerTool,
        DuplicateItemTool,
        RestoreItemTool,
        SearchFilesTool,
    ]
    for cls in tool_classes:
        name = getattr(cls, "name", cls.__name__)
        try:
            if registry.get(name) is None:
                registry.register(cls())
                logger.info("Registered filesystem intelligence tool: %s", name)
        except Exception:
            logger.exception("Failed to register tool %s", name)


# Run on import (idempotent)
register_intelligence_tools()
