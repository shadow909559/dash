"""REST API routes for file operations: search, preview, copy, move, rename, delete, recycle bin, browse.

Provides HTTP endpoints for all file system operations.

Security model:
- Every endpoint requires an authenticated DASH local client (device token).
- All paths are validated against the explicit allowed-roots list in
  ``dash_backend.security.path_guard`` (canonical resolution + ancestry
  containment). Arbitrary absolute filesystem access is denied.
- Protected secret files (.env, keys, credentials) cannot be read or mutated.
"""

from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
from pathlib import Path
from typing import Any
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from dash_backend.auth.dependencies import get_current_user
from dash_backend.logging_config import get_logger
from dash_backend.security.path_guard import PathDenied, is_secret_file, resolve_allowed

logger = get_logger(__name__)

router = APIRouter(prefix="/files", tags=["files"], dependencies=[Depends(get_current_user)])


# ── Request / Response Models ────────────────────────────────


class FileOperationResponse(BaseModel):
    status: str = "ok"
    summary: str = ""
    details: dict[str, Any] = Field(default_factory=dict)


class FileCopyMoveRequest(BaseModel):
    source: str = Field(..., description="Source path")
    destination: str = Field(..., description="Destination path")


class FileRenameRequest(BaseModel):
    path: str = Field(..., description="Path to the file/folder")
    new_name: str = Field(..., description="New name")


class FileDeleteRequest(BaseModel):
    path: str = Field(..., description="Path to delete")
    permanent: bool = False


class FileSearchResponse(BaseModel):
    pattern: str = ""
    path: str = ""
    results: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


class FilePreviewResponse(BaseModel):
    name: str = ""
    path: str = ""
    size_bytes: int = 0
    content: str = ""
    type: str = ""
    total_lines: int | None = None
    truncated: bool = False
    image_width: int | None = None
    image_height: int | None = None


class BrowseResponse(BaseModel):
    path: str = ""
    entries: list[dict[str, Any]] = Field(default_factory=list)
    count: int = 0


# ── Helper ────────────────────────────────────────────────────

SPECIAL_FOLDERS = {
    "desktop": str(Path.home() / "Desktop"),
    "downloads": str(Path.home() / "Downloads"),
    "documents": str(Path.home() / "Documents"),
    "pictures": str(Path.home() / "Pictures"),
    "videos": str(Path.home() / "Videos"),
    "music": str(Path.home() / "Music"),
    "home": str(Path.home()),
}


def _resolve_path(path: str) -> Path:
    """Resolve a special folder alias or a path inside an allowed root.

    Raises PathDenied for anything outside the allow-list (including
    traversal and sibling tricks). HTTP-mapped by callers via _denied().
    """
    return resolve_allowed(path)


def _denied(exc: PathDenied) -> HTTPException:
    return HTTPException(status_code=403, detail=str(exc))


# ── Endpoints ────────────────────────────────────────────────


@router.get("/browse", response_model=BrowseResponse)
async def browse_folder(
    path: str = Query(".", description="Directory path to browse"),
    show_hidden: bool = Query(False, description="Show hidden files"),
) -> BrowseResponse:
    """List contents of a directory with file details."""
    try:
        p = _resolve_path(path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {p}")
        if not p.is_dir():
            raise HTTPException(status_code=400, detail=f"Not a directory: {p}")
        entries = []
        for entry in sorted(p.iterdir(), key=lambda e: (not e.is_dir(), e.name.lower())):
            if entry.name.startswith(".") and not show_hidden:
                continue
            try:
                stat = entry.stat()
                entries.append(
                    {
                        "name": entry.name,
                        "type": "directory" if entry.is_dir() else "file",
                        "size": stat.st_size if entry.is_file() else 0,
                        "modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
                        "path": str(entry.resolve()),
                    }
                )
            except (OSError, PermissionError):
                continue
        return BrowseResponse(path=str(p), entries=entries, count=len(entries))
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("browse failed")
        raise HTTPException(status_code=500, detail="Internal error during browse") from exc


@router.get("/search", response_model=FileSearchResponse)
async def search_files(
    pattern: str = Query(..., description="Filename pattern or glob"),
    path: str = Query(".", description="Starting directory"),
    max_results: int = Query(50, ge=1, le=200, description="Maximum results"),
) -> FileSearchResponse:
    """Search for files and folders by name pattern."""
    try:
        p = _resolve_path(path)
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Path not found: {p}")

        def _search() -> list[dict[str, Any]]:
            results = []
            for entry in p.rglob(pattern):
                try:
                    results.append(
                        {
                            "name": entry.name,
                            "path": str(entry.resolve()),
                            "type": "directory" if entry.is_dir() else "file",
                            "size": entry.stat().st_size if entry.is_file() else 0,
                        }
                    )
                except (OSError, PermissionError):
                    pass
                if len(results) >= max_results:
                    break
            return results

        results = await asyncio.to_thread(_search)
        return FileSearchResponse(pattern=pattern, path=str(p), results=results, count=len(results))
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("search failed")
        raise HTTPException(status_code=500, detail="Internal error during search") from exc


@router.get("/preview", response_model=FilePreviewResponse)
async def preview_file(
    path: str = Query(..., description="File path to preview"),
    max_lines: int = Query(50, ge=1, le=500, description="Maximum text lines"),
) -> FilePreviewResponse:
    """Preview a file's content (protected secret files are never readable)."""
    try:
        p = _resolve_path(path)  # allowlist check
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {path}")
        if p.is_dir():
            raise HTTPException(status_code=400, detail="Cannot preview a directory")
        if is_secret_file(p):
            raise HTTPException(status_code=403, detail="Refusing to preview protected file")

        suffix = p.suffix.lower()
        stat = p.stat()
        response = FilePreviewResponse(
            name=p.name,
            path=str(p.resolve()),
            size_bytes=stat.st_size,
            type=suffix,
        )

        text_extensions = {
            ".txt",
            ".md",
            ".py",
            ".js",
            ".ts",
            ".html",
            ".css",
            ".json",
            ".xml",
            ".yaml",
            ".yml",
            ".cfg",
            ".conf",
            ".ini",
            ".log",
            ".csv",
            ".sh",
            ".bat",
            ".ps1",
            ".env",
            ".gitignore",
            ".toml",
            ".lock",
            ".sql",
            ".java",
            ".c",
            ".cpp",
            ".h",
            ".hpp",
            ".rs",
            ".go",
            ".rb",
            ".php",
            ".swift",
            ".kt",
            ".scala",
            ".clj",
            ".ex",
            ".exs",
        }
        image_extensions = {".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".svg"}

        if suffix in text_extensions:
            try:
                def _read() -> tuple[str, int]:
                    content = p.read_text(encoding="utf-8", errors="replace")
                    return content, len(content.splitlines())

                content, total = await asyncio.to_thread(_read)
                lines = content.splitlines()
                preview = "\n".join(lines[:max_lines])
                response.content = preview
                response.total_lines = total
                response.truncated = total > max_lines
            except Exception:
                response.content = "[Binary or unreadable file]"
        elif suffix in image_extensions:
            response.content = "[Image file]"
            try:
                from PIL import Image

                img = Image.open(p)
                response.image_width = img.width
                response.image_height = img.height
            except ImportError:
                pass
        elif suffix == ".pdf":
            response.content = "[PDF document]"
            try:
                import PyPDF2

                with open(p, "rb") as f:
                    reader = PyPDF2.PdfReader(f)
                    if reader.pages:
                        response.content = reader.pages[0].extract_text()[:2000]
            except ImportError:
                pass
        else:
            response.content = f"[{suffix.upper() or 'Unknown'} file, {stat.st_size} bytes]"

        return response
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("preview failed")
        raise HTTPException(status_code=500, detail="Internal error during preview") from exc


@router.post("/copy", response_model=FileOperationResponse)
async def copy_file(req: FileCopyMoveRequest) -> FileOperationResponse:
    """Copy a file or directory to a new location."""
    try:
        src = _resolve_path(req.source)
        dst = _resolve_path(req.destination)
        if is_secret_file(src):
            raise HTTPException(status_code=403, detail="Refusing to copy protected file")
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Source not found: {req.source}")
        dst.parent.mkdir(parents=True, exist_ok=True)

        def _copy() -> None:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

        await asyncio.to_thread(_copy)
        return FileOperationResponse(summary=f"Copied {req.source} -> {req.destination}")
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("copy failed")
        raise HTTPException(status_code=500, detail="Internal error during copy") from exc


@router.post("/move", response_model=FileOperationResponse)
async def move_file(req: FileCopyMoveRequest) -> FileOperationResponse:
    """Move a file or directory to a new location."""
    try:
        src = _resolve_path(req.source)
        dst = _resolve_path(req.destination)
        if is_secret_file(src):
            raise HTTPException(status_code=403, detail="Refusing to move protected file")
        if not src.exists():
            raise HTTPException(status_code=404, detail=f"Source not found: {req.source}")
        dst.parent.mkdir(parents=True, exist_ok=True)
        await asyncio.to_thread(shutil.move, str(src), str(dst))
        return FileOperationResponse(summary=f"Moved {req.source} -> {req.destination}")
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("move failed")
        raise HTTPException(status_code=500, detail="Internal error during move") from exc


@router.post("/rename", response_model=FileOperationResponse)
async def rename_file(req: FileRenameRequest) -> FileOperationResponse:
    """Rename a file or folder."""
    try:
        p = _resolve_path(req.path)
        if is_secret_file(p):
            raise HTTPException(status_code=403, detail="Refusing to rename protected file")
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Not found: {req.path}")
        new_path = p.parent / req.new_name
        _resolve_path(str(new_path))  # destination must stay inside allowed roots
        await asyncio.to_thread(p.rename, new_path)
        return FileOperationResponse(summary=f"Renamed to {req.new_name}")
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("rename failed")
        raise HTTPException(status_code=500, detail="Internal error during rename") from exc


@router.post("/delete", response_model=FileOperationResponse)
async def delete_file(req: FileDeleteRequest) -> FileOperationResponse:
    """Delete a file or folder (to Recycle Bin on Windows, or permanently)."""
    try:
        p = _resolve_path(req.path)
        if is_secret_file(p):
            raise HTTPException(status_code=403, detail="Refusing to delete protected file")
        if not p.exists():
            raise HTTPException(status_code=404, detail=f"Not found: {req.path}")

        def _delete() -> str:
            if req.permanent or os.name != "nt":
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
                return f"Deleted {p.name}"
            import ctypes

            FO_DELETE = 3
            FOF_ALLOWUNDO = 0x40
            buf = ctypes.create_unicode_buffer(str(p) + "\0\0")
            ctypes.windll.shell32.SHFileOperationW(
                ctypes.byref(ctypes.c_int(0)),
                ctypes.byref(ctypes.c_int(FO_DELETE)),
                buf,
                None,
                ctypes.byref(ctypes.c_int(FOF_ALLOWUNDO)),
                0,
            )
            return f"Moved {p.name} to Recycle Bin"

        summary = await asyncio.to_thread(_delete)
        return FileOperationResponse(summary=summary)
    except HTTPException:
        raise
    except PathDenied as exc:
        raise _denied(exc)
    except Exception as exc:
        logger.exception("delete failed")
        raise HTTPException(status_code=500, detail="Internal error during delete") from exc


@router.get("/recycle-bin", response_model=FileSearchResponse)
async def list_recycle_bin() -> FileSearchResponse:
    """List items in the Windows Recycle Bin."""
    if os.name != "nt":
        raise HTTPException(status_code=400, detail="Recycle Bin only available on Windows")

    def _list() -> list[dict[str, Any]]:
        # PowerShell via Shell.Application COM is the reliable way to read
        # the Recycle Bin (dir on $Recycle.Bin misses per-SID subfolders and
        # returns internal names instead of original file names).
        import json as _json

        ps = (
            "$sh = New-Object -ComObject Shell.Application; "
            "$rb = $sh.Namespace(0xA); "
            "$items = @($rb.Items()); "
            "(@($items | ForEach-Object { [pscustomobject]@{ name = $_.Name; path = $_.Path } }) | Convert-ToJson) "
            "-replace '\\\\\"','\"'"
        )
        # Simpler: emit JSON directly
        ps = (
            "$sh = New-Object -ComObject Shell.Application; "
            "$rb = $sh.Namespace(0xA); "
            "$out = foreach($i in @($rb.Items())) { [pscustomobject]@{ name = $i.Name; path = $i.Path } }; "
            "$out | ConvertTo-Json -Compress"
        )
        output = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            text=True,
            timeout=20,
        ).stdout.strip()

        items: list[dict[str, Any]] = []
        if output:
            try:
                parsed = _json.loads(output)
            except _json.JSONDecodeError:
                parsed = []
            if isinstance(parsed, dict):
                parsed = [parsed]
            for entry in parsed or []:
                items.append({"name": entry.get("name", ""), "path": entry.get("path", "")})
        return items[:100]

    try:
        items = await asyncio.to_thread(_list)
        return FileSearchResponse(
            pattern="*",
            path="$Recycle.Bin",
            results=items,
            count=len(items),
        )
    except Exception as exc:
        logger.exception("recycle-bin listing failed")
        raise HTTPException(status_code=500, detail="Internal error listing Recycle Bin") from exc


@router.post("/recycle-bin/empty", response_model=FileOperationResponse)
async def empty_recycle_bin() -> FileOperationResponse:
    """Empty the Windows Recycle Bin."""
    if os.name != "nt":
        raise HTTPException(status_code=400, detail="Recycle Bin only available on Windows")

    def _empty() -> None:
        # Clear Recycle Bin through the Shell COM API — safer and more
        # reliable than rd /s /q on %systemdrive%\$Recycle.Bin.
        import subprocess

        ps = (
            "$sh = New-Object -ComObject Shell.Application; "
            "$rb = $sh.Namespace(0xA); "
            "@($rb.Items()) | ForEach-Object { Remove-Item -LiteralPath $_.Path -Recurse -Force -ErrorAction SilentlyContinue }"
        )
        subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True,
            timeout=60,
        )

    try:
        await asyncio.to_thread(_empty)
        return FileOperationResponse(summary="Recycle Bin emptied")
    except Exception as exc:
        logger.exception("recycle-bin empty failed")
        raise HTTPException(status_code=500, detail="Internal error emptying Recycle Bin") from exc


@router.get("/special-folders", response_model=dict[str, str])
async def list_special_folders() -> dict[str, str]:
    """List special system folders."""
    folders = {}
    for name, path_str in SPECIAL_FOLDERS.items():
        try:
            if Path(path_str).exists():
                folders[name] = str(Path(path_str).resolve())
        except Exception:
            pass
    return folders


@router.get("/drives", response_model=FileSearchResponse)
async def list_drives() -> FileSearchResponse:
    """List all drives."""
    try:
        drives = []
        if os.name == "nt":
            import ctypes
            import string

            bitmask = ctypes.windll.kernel32.GetLogicalDrives()
            for letter in string.ascii_uppercase:
                if bitmask & 1:
                    drive = f"{letter}:\\"
                    try:
                        drive_type = ctypes.windll.kernel32.GetDriveTypeW(drive)
                        type_names = {
                            0: "unknown",
                            1: "root_not_found",
                            2: "removable",
                            3: "fixed",
                            4: "network",
                            5: "cdrom",
                            6: "ramdisk",
                        }
                        drives.append({"letter": drive, "type": type_names.get(drive_type, "unknown")})
                    except Exception:
                        pass
                bitmask >>= 1
        else:
            for mount in Path("/media").iterdir():
                drives.append({"letter": str(mount), "type": "external"})
            for mount in Path("/mnt").iterdir():
                drives.append({"letter": str(mount), "type": "external"})
        return FileSearchResponse(results=drives, count=len(drives))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))

