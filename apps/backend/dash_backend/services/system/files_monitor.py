"""File system monitor - Desktop, Downloads, Documents, Recent files, Recycle Bin."""

from __future__ import annotations

import os
import platform
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def _get_special_folder(folder_id: int) -> str | None:
    """Get Windows special folder path by CSIDL."""
    if platform.system() != "Windows":
        return None
    try:
        import ctypes
        from ctypes import wintypes
        buf = ctypes.create_unicode_buffer(260)
        ctypes.windll.shell32.SHGetFolderPathW(None, folder_id, None, 0, buf)
        return buf.value
    except Exception:
        return None


# CSIDL constants
CSIDL_DESKTOP = 0x0000
CSIDL_PERSONAL = 0x0005  # Documents
CSIDL_MYDOCUMENTS = 0x000C
CSIDL_MYPICTURES = 0x0027
CSIDL_MYVIDEO = 0x000E
CSIDL_PROFILE = 0x0028


def get_file_system_info() -> dict[str, Any]:
    """Return file system info for common folders and recent files.

    Returns: desktop, downloads, documents, pictures, videos, recent_files, recycle_bin_size.
    """
    result: dict[str, Any] = {
        "desktop": {"path": None, "file_count": None, "size_bytes": None},
        "downloads": {"path": None, "file_count": None, "size_bytes": None},
        "documents": {"path": None, "file_count": None, "size_bytes": None},
        "pictures": {"path": None, "file_count": None, "size_bytes": None},
        "videos": {"path": None, "file_count": None, "size_bytes": None},
        "recent_files": [],
        "recycle_bin_size": None,
    }

    if platform.system() != "Windows":
        return result

    try:
        # Get user profile path
        user_profile = os.environ.get("USERPROFILE", "")

        # Desktop
        desktop_path = _get_special_folder(CSIDL_DESKTOP) or os.path.join(user_profile, "Desktop")
        if os.path.exists(desktop_path):
            result["desktop"]["path"] = desktop_path
            try:
                files = os.listdir(desktop_path)
                result["desktop"]["file_count"] = len(files)
                total_size = sum(
                    os.path.getsize(os.path.join(desktop_path, f))
                    for f in files
                    if os.path.isfile(os.path.join(desktop_path, f))
                )
                result["desktop"]["size_bytes"] = total_size
            except (OSError, PermissionError):
                pass

        # Downloads
        downloads_path = os.path.join(user_profile, "Downloads")
        if os.path.exists(downloads_path):
            result["downloads"]["path"] = downloads_path
            try:
                files = os.listdir(downloads_path)
                result["downloads"]["file_count"] = len(files)
                total_size = sum(
                    os.path.getsize(os.path.join(downloads_path, f))
                    for f in files
                    if os.path.isfile(os.path.join(downloads_path, f))
                )
                result["downloads"]["size_bytes"] = total_size
            except (OSError, PermissionError):
                pass

        # Documents
        docs_path = _get_special_folder(CSIDL_PERSONAL) or os.path.join(user_profile, "Documents")
        if os.path.exists(docs_path):
            result["documents"]["path"] = docs_path
            try:
                files = os.listdir(docs_path)
                result["documents"]["file_count"] = len(files)
                total_size = sum(
                    os.path.getsize(os.path.join(docs_path, f))
                    for f in files
                    if os.path.isfile(os.path.join(docs_path, f))
                )
                result["documents"]["size_bytes"] = total_size
            except (OSError, PermissionError):
                pass

        # Pictures
        pics_path = _get_special_folder(CSIDL_MYPICTURES) or os.path.join(user_profile, "Pictures")
        if os.path.exists(pics_path):
            result["pictures"]["path"] = pics_path
            try:
                files = os.listdir(pics_path)
                result["pictures"]["file_count"] = len(files)
                total_size = sum(
                    os.path.getsize(os.path.join(pics_path, f))
                    for f in files
                    if os.path.isfile(os.path.join(pics_path, f))
                )
                result["pictures"]["size_bytes"] = total_size
            except (OSError, PermissionError):
                pass

        # Videos
        videos_path = _get_special_folder(CSIDL_MYVIDEO) or os.path.join(user_profile, "Videos")
        if os.path.exists(videos_path):
            result["videos"]["path"] = videos_path
            try:
                files = os.listdir(videos_path)
                result["videos"]["file_count"] = len(files)
                total_size = sum(
                    os.path.getsize(os.path.join(videos_path, f))
                    for f in files
                    if os.path.isfile(os.path.join(videos_path, f))
                )
                result["videos"]["size_bytes"] = total_size
            except (OSError, PermissionError):
                pass

        # Recent files (from Windows Recent folder)
        try:
            recent_path = os.path.join(user_profile, "AppData", "Roaming", "Microsoft", "Windows", "Recent")
            if os.path.exists(recent_path):
                recent_files = []
                for f in os.listdir(recent_path)[:50]:  # Limit to 50
                    try:
                        full_path = os.path.join(recent_path, f)
                        stat = os.stat(full_path)
                        recent_files.append({
                            "name": f,
                            "path": full_path,
                            "modified": stat.st_mtime,
                            "size_bytes": stat.st_size,
                        })
                    except (OSError, PermissionError):
                        continue
                # Sort by modified time descending
                recent_files.sort(key=lambda x: x["modified"], reverse=True)
                result["recent_files"] = recent_files[:20]
        except Exception:
            pass

        # Recycle Bin size
        try:
            import subprocess
            output = subprocess.check_output(
                ["cmd", "/c", "dir", "/a", "/s", "C:\\$Recycle.Bin"],
                shell=True, timeout=10, text=True
            )
            for line in output.splitlines():
                if "File(s)" in line:
                    parts = line.strip().split()
                    if len(parts) >= 3:
                        try:
                            result["recycle_bin_size"] = int(parts[2].replace(",", ""))
                        except ValueError:
                            pass
                    break
        except Exception:
            pass

    except Exception:
        logger.exception("Failed to collect file system info")

    return result