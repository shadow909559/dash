"""File tools - favorites, pinned folders, file preview, recent files, recycle bin."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.tools.base_tool import BaseTool, ToolParameter, ToolContext, PermissionLevel
from dash_backend.tools.tool_result import ToolResult, ToolStatus

logger = get_logger(__name__)
IS_WINDOWS = sys.platform == "win32"


class ListFavoritesTool(BaseTool):
    name = "list_favorites"
    description = "List favorite/pinned folders from Windows Quick Access or user favorites."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        try:
            favorites = []
            if IS_WINDOWS:
                # Quick Access pinned items
                quick_access = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Windows" / "Recent" / "AutomaticDestinations"
                if quick_access.exists():
                    for item in quick_access.iterdir():
                        favorites.append({"name": item.stem, "path": str(item)})
                # Start menu pinned
                start_menu = Path.home() / "AppData" / "Roaming" / "Microsoft" / "Internet Explorer" / "Quick Launch" / "User Pinned" / "TaskBar"
                if start_menu.exists():
                    for item in start_menu.iterdir():
                        if item.suffix.lower() == ".lnk":
                            favorites.append({"name": item.stem, "path": str(item), "type": "pinned"})
            # Standard special folders
            special = {
                "desktop": str(Path.home() / "Desktop"),
                "downloads": str(Path.home() / "Downloads"),
                "documents": str(Path.home() / "Documents"),
                "pictures": str(Path.home() / "Pictures"),
                "videos": str(Path.home() / "Videos"),
                "music": str(Path.home() / "Music"),
            }
            for name, path in special.items():
                if Path(path).exists():
                    favorites.insert(0, {"name": name.capitalize(), "path": path, "type": "system"})
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"favorites": favorites},
                              summary=f"Found {len(favorites)} favorites")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class PreviewFileTool(BaseTool):
    name = "preview_file"
    description = "Preview a file's content (text, image, PDF text, or metadata)."
    parameters = [
        ToolParameter("path", "File path to preview", required=True),
        ToolParameter("max_lines", "Maximum text lines to return", type="integer", required=False, default=50),
    ]
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        path_str = kwargs.get("path", "")
        max_lines = int(kwargs.get("max_lines", 50))
        if not path_str:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="path required")
        try:
            p = Path(path_str)
            if not p.exists():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=f"File not found: {path_str}")
            if p.is_dir():
                return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Cannot preview a directory")

            suffix = p.suffix.lower()
            stat = p.stat()
            info = {
                "name": p.name, "path": str(p.resolve()),
                "size_bytes": stat.st_size, "modified": stat.st_mtime,
                "type": suffix,
            }

            # Text files
            if suffix in (".txt", ".md", ".py", ".js", ".ts", ".html", ".css", ".json", ".xml", ".yaml", ".yml",
                          ".cfg", ".conf", ".ini", ".log", ".csv", ".sh", ".bat", ".ps1", ".env", ".gitignore",
                          ".toml", ".lock", ".sql", ".java", ".c", ".cpp", ".h", ".hpp", ".rs", ".go", ".rb"):
                try:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    lines = content.splitlines()
                    preview = "\n".join(lines[:max_lines])
                    truncated = len(lines) > max_lines
                    info["content"] = preview
                    info["total_lines"] = len(lines)
                    info["truncated"] = truncated
                except Exception:
                    info["content"] = "[Binary or unreadable file]"
                    info["encoding"] = "binary"

            # Images
            elif suffix in (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"):
                info["content"] = "[Image file]"
                try:
                    from PIL import Image
                    img = Image.open(p)
                    info["image_width"] = img.width
                    info["image_height"] = img.height
                    info["image_format"] = img.format
                except ImportError:
                    pass

            # PDF
            elif suffix == ".pdf":
                info["content"] = "[PDF document]"
                try:
                    import PyPDF2
                    with open(p, "rb") as f:
                        reader = PyPDF2.PdfReader(f)
                        info["pdf_pages"] = len(reader.pages)
                        if reader.pages:
                            info["content"] = reader.pages[0].extract_text()[:2000]
                except ImportError:
                    pass

            else:
                info["content"] = f"[{suffix.upper() or 'Unknown'} file, {stat.st_size} bytes]"

            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output=info,
                              summary=f"Previewed {p.name} ({info.get('total_lines', '?')} lines, {stat.st_size} bytes)")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class RecycleBinTool(BaseTool):
    name = "list_recycle_bin"
    description = "List items in the Windows Recycle Bin."
    parameters = []
    permission_level = PermissionLevel.AUTO
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            output = subprocess.check_output(
                ["cmd", "/c", "dir", "/s", "/b", "/a", "$Recycle.Bin"],
                shell=True, timeout=10, text=True
            )
            items = []
            for line in output.splitlines():
                if line.strip():
                    items.append({"path": line.strip()})
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, output={"items": items[:100]},
                              summary=f"Found {len(items)} items in Recycle Bin")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))


class EmptyRecycleBinTool(BaseTool):
    name = "empty_recycle_bin"
    description = "Empty the Windows Recycle Bin. Requires confirmation."
    parameters = []
    permission_level = PermissionLevel.RESTRICTED
    category = "filesystem"

    async def execute(self, context: ToolContext, **kwargs: Any) -> ToolResult:
        if not IS_WINDOWS:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message="Windows only")
        try:
            import subprocess
            subprocess.run(["cmd", "/c", "rd", "/s", "/q", "%systemdrive%\\$Recycle.Bin"],
                           shell=True, timeout=30, capture_output=True)
            return ToolResult(tool_name=self.name, status=ToolStatus.SUCCESS, summary="Recycle Bin emptied")
        except Exception as exc:
            return ToolResult(tool_name=self.name, status=ToolStatus.ERROR, error_message=str(exc))
