"""Download Manager service - monitor, classify, and auto-organize downloads.

Tracks the Downloads folder, classifies files by type, and can organize them
into categorized subfolders. Uses the Singleton pattern for a shared instance.
"""

from __future__ import annotations

import shutil
import time
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

# Category definitions: extension -> category
FILE_CATEGORIES: dict[str, str] = {
    # Documents
    ".pdf": "Documents", ".doc": "Documents", ".docx": "Documents",
    ".txt": "Documents", ".rtf": "Documents", ".odt": "Documents",
    ".xls": "Documents", ".xlsx": "Documents", ".csv": "Documents",
    ".ppt": "Documents", ".pptx": "Documents",
    # Images
    ".jpg": "Images", ".jpeg": "Images", ".png": "Images", ".gif": "Images",
    ".bmp": "Images", ".svg": "Images", ".webp": "Images", ".ico": "Images",
    ".tiff": "Images", ".heic": "Images",
    # Videos
    ".mp4": "Videos", ".mkv": "Videos", ".avi": "Videos", ".mov": "Videos",
    ".wmv": "Videos", ".flv": "Videos", ".webm": "Videos",
    # Audio
    ".mp3": "Audio", ".wav": "Audio", ".flac": "Audio", ".aac": "Audio",
    ".ogg": "Audio", ".m4a": "Audio", ".wma": "Audio",
    # Archives
    ".zip": "Archives", ".rar": "Archives", ".7z": "Archives", ".tar": "Archives",
    ".gz": "Archives", ".bz2": "Archives", ".xz": "Archives",
    # Installers
    ".exe": "Installers", ".msi": "Installers", ".dmg": "Installers",
    ".pkg": "Installers", ".deb": "Installers", ".rpm": "Installers",
    # Code
    ".py": "Code", ".js": "Code", ".ts": "Code", ".html": "Code", ".css": "Code",
    ".json": "Code", ".xml": "Code", ".java": "Code", ".c": "Code", ".cpp": "Code",
    ".cs": "Code", ".go": "Code", ".rs": "Code", ".rb": "Code", ".php": "Code",
    ".sh": "Code", ".bat": "Code", ".ps1": "Code",
}

# Common placeholder/partial download extensions to ignore
PARTIAL_EXTENSIONS = {".crdownload", ".part", ".tmp", ".download"}


def get_downloads_dir() -> Path:
    """Return the system Downloads folder."""
    return Path.home() / "Downloads"


def classify_file(filename: str) -> str:
    """Classify a file into a category based on its extension."""
    ext = Path(filename).suffix.lower()
    return FILE_CATEGORIES.get(ext, "Other")


class DownloadManager(Singleton):
    """Monitors and organizes the Downloads folder."""

    def __init__(self) -> None:
        self._downloads_dir = get_downloads_dir()
        self._organized: set[str] = set()

    def list_downloads(self, limit: int = 50) -> dict[str, Any]:
        """List recent files in the Downloads folder, newest first."""
        downloads = self._downloads_dir
        if not downloads.exists():
            return {"downloads": [], "count": 0, "path": str(downloads)}

        files = []
        for item in downloads.iterdir():
            try:
                if item.is_file() and item.suffix.lower() not in PARTIAL_EXTENSIONS:
                    files.append({
                        "name": item.name,
                        "path": str(item),
                        "size_bytes": item.stat().st_size,
                        "size_mb": round(item.stat().st_size / (1024 * 1024), 2),
                        "category": classify_file(item.name),
                        "modified": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(item.stat().st_mtime)),
                    })
            except (OSError, PermissionError):
                continue

        files.sort(key=lambda f: f["modified"], reverse=True)
        results = files[:limit]
        return {"downloads": results, "count": len(results), "path": str(downloads)}

    def auto_organize(self, dry_run: bool = False) -> dict[str, Any]:
        """Move downloads into categorized folders.

        Args:
            dry_run: If True, only report what would be moved without moving.

        Returns:
            Dict with organized/moved counts and details.
        """
        downloads = self._downloads_dir
        if not downloads.exists():
            return {"organized": 0, "dry_run": dry_run, "details": [], "message": "Downloads folder not found"}

        moved = []
        skipped = []
        for item in downloads.iterdir():
            try:
                if not item.is_file() or item.suffix.lower() in PARTIAL_EXTENSIONS:
                    continue
                category = classify_file(item.name)
                target_dir = downloads / category
                target = target_dir / item.name
                if target.exists():
                    skipped.append({"name": item.name, "reason": "target already exists"})
                    continue
                if not dry_run:
                    target_dir.mkdir(parents=True, exist_ok=True)
                    shutil.move(str(item), str(target))
                moved.append({
                    "name": item.name,
                    "from": str(item),
                    "to": str(target),
                    "category": category,
                })
            except (OSError, PermissionError, shutil.Error) as exc:
                skipped.append({"name": item.name, "reason": str(exc)})

        return {
            "organized": len(moved),
            "skipped": len(skipped),
            "dry_run": dry_run,
            "details": moved[:50],
            "skipped_items": skipped[:20],
        }

    def get_stats(self) -> dict[str, Any]:
        """Get download folder statistics."""
        downloads = self._downloads_dir
        if not downloads.exists():
            return {"total_files": 0, "total_size_mb": 0}
        total_size = 0
        file_count = 0
        for item in downloads.rglob("*"):
            try:
                if item.is_file() and item.suffix.lower() not in PARTIAL_EXTENSIONS:
                    total_size += item.stat().st_size
                    file_count += 1
            except (OSError, PermissionError):
                continue
        return {
            "total_files": file_count,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "downloads_dir": str(downloads),
        }


_download_manager: DownloadManager | None = None


def get_download_manager() -> DownloadManager:
    global _download_manager
    if _download_manager is None:
        _download_manager = DownloadManager()
    return _download_manager
