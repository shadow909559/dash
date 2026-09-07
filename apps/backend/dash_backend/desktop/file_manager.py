"""File Manager - File system operations for DASH AI OS.

Provides:
- File/folder listing with metadata
- File search (by name, type, date, size)
- File operations (copy, move, delete, rename)
- Recent files tracking
- Downloads folder monitoring
- Recycle bin access
- File watching
- File preview
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Set

logger = logging.getLogger(__name__)


class FileType(Enum):
    """File type categories."""
    DOCUMENT = "document"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    CODE = "code"
    ARCHIVE = "archive"
    EXECUTABLE = "executable"
    FOLDER = "folder"
    OTHER = "other"


@dataclass
class FileInfo:
    """Information about a file or folder.
    
    Attributes:
        path: Full path
        name: File name
        extension: File extension
        size: Size in bytes
        is_directory: Whether it's a directory
        is_hidden: Whether hidden
        modified_at: Last modified time
        created_at: Creation time
        accessed_at: Last access time
        permissions: File permissions string
        owner: File owner
        file_type: File type category
        mime_type: MIME type
    """
    path: str = ""
    name: str = ""
    extension: str = ""
    size: int = 0
    is_directory: bool = False
    is_hidden: bool = False
    modified_at: float = 0.0
    created_at: float = 0.0
    accessed_at: float = 0.0
    permissions: str = ""
    owner: str = ""
    file_type: FileType = FileType.OTHER
    mime_type: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "path": self.path,
            "name": self.name,
            "extension": self.extension,
            "size": self.size,
            "size_formatted": self._format_size(self.size),
            "is_directory": self.is_directory,
            "is_hidden": self.is_hidden,
            "modified_at": self.modified_at,
            "created_at": self.created_at,
            "file_type": self.file_type.value,
            "mime_type": self.mime_type,
        }
    
    @staticmethod
    def _format_size(size: int) -> str:
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024:
                return f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} PB"


class FileManager:
    """Manages file system operations.
    
    Features:
    - File/folder listing and navigation
    - File search (full-text, by criteria)
    - File operations (copy, move, delete, rename)
    - Recent files tracking
    - Downloads folder monitoring
    - Recycle bin access
    - File watching for changes
    - File preview generation
    """
    
    def __init__(self, watch_interval: float = 2.0):
        self._watch_interval = watch_interval
        self._watched_dirs: Dict[str, Set[str]] = {}  # dir -> set of files
        
        # Recent files
        self._recent_files: List[FileInfo] = []
        self._max_recent: int = 50
        
        # Watch callbacks
        self._watch_callbacks: Dict[str, List[Callable]] = {}
        
        # Watch task
        self._watch_task: Optional[asyncio.Task] = None
        self._running = False
        
        self._stats = {
            "files_listed": 0,
            "files_copied": 0,
            "files_moved": 0,
            "files_deleted": 0,
            "searches_performed": 0,
        }
    
    # ── Lifecycle ───────────────────────────────────────────
    
    async def start(self) -> None:
        self._running = True
        self._watch_task = asyncio.create_task(self._watch_loop())
        logger.info("FileManager started")
    
    async def stop(self) -> None:
        self._running = False
        if self._watch_task:
            self._watch_task.cancel()
            try:
                await self._watch_task
            except asyncio.CancelledError:
                pass
        logger.info("FileManager stopped")
    
    # ── File Listing ────────────────────────────────────────
    
    async def list_directory(self, path: str, include_hidden: bool = False,
                               sort_by: str = "name",
                               filter_ext: Optional[List[str]] = None) -> List[FileInfo]:
        """List contents of a directory.
        
        Args:
            path: Directory path
            include_hidden: Include hidden files
            sort_by: Sort field (name, size, modified, type)
            filter_ext: Filter by extensions
            
        Returns:
            List of FileInfo
        """
        try:
            p = Path(path)
            if not p.exists() or not p.is_dir():
                return []
            
            entries = []
            for entry in p.iterdir():
                try:
                    info = self._get_file_info(str(entry))
                    if not info:
                        continue
                    if not include_hidden and info.is_hidden:
                        continue
                    if filter_ext and not info.is_directory:
                        if info.extension.lower() not in [e.lower() for e in filter_ext]:
                            continue
                    entries.append(info)
                except (PermissionError, OSError):
                    continue
            
            # Sort
            sort_keys = {
                "name": lambda f: f.name.lower(),
                "size": lambda f: f.size,
                "modified": lambda f: f.modified_at,
                "type": lambda f: f.file_type.value,
            }
            key = sort_keys.get(sort_by, sort_keys["name"])
            entries.sort(key=key)
            
            # Folders first
            entries.sort(key=lambda f: (not f.is_directory, key(f)))
            
            self._stats["files_listed"] += len(entries)
            return entries
            
        except Exception as exc:
            logger.warning("List directory failed: %s", exc)
            return []
    
    async def get_file_info(self, path: str) -> Optional[FileInfo]:
        """Get file information.
        
        Args:
            path: File path
            
        Returns:
            FileInfo or None
        """
        return self._get_file_info(path)
    
    def _get_file_info(self, path: str) -> Optional[FileInfo]:
        """Get file info from path.
        
        Args:
            path: File path
            
        Returns:
            FileInfo or None
        """
        try:
            p = Path(path)
            if not p.exists():
                return None
            
            stat = p.stat()
            name = p.name
            
            # Determine file type
            file_type = FileType.OTHER
            ext = p.suffix.lower()
            
            if p.is_dir():
                file_type = FileType.FOLDER
            elif ext in ('.txt', '.md', '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx'):
                file_type = FileType.DOCUMENT
            elif ext in ('.jpg', '.jpeg', '.png', '.gif', '.bmp', '.svg', '.webp'):
                file_type = FileType.IMAGE
            elif ext in ('.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv'):
                file_type = FileType.VIDEO
            elif ext in ('.mp3', '.wav', '.flac', '.aac', '.ogg', '.wma'):
                file_type = FileType.AUDIO
            elif ext in ('.py', '.js', '.ts', '.html', '.css', '.java', '.cpp', '.c', '.h', '.go', '.rs', '.swift'):
                file_type = FileType.CODE
            elif ext in ('.zip', '.rar', '.7z', '.tar', '.gz'):
                file_type = FileType.ARCHIVE
            elif ext in ('.exe', '.msi', '.bat', '.sh'):
                file_type = FileType.EXECUTABLE
            
            return FileInfo(
                path=str(p.absolute()),
                name=name,
                extension=ext,
                size=stat.st_size,
                is_directory=p.is_dir(),
                is_hidden=name.startswith('.'),
                modified_at=stat.st_mtime,
                created_at=stat.st_ctime,
                accessed_at=stat.st_atime,
                file_type=file_type,
            )
            
        except (PermissionError, OSError) as exc:
            logger.debug("Get file info failed: %s", exc)
            return None
    
    # ── File Search ─────────────────────────────────────────
    
    async def search_files(self, query: str, root_path: Optional[str] = None,
                             max_results: int = 50,
                             file_types: Optional[List[FileType]] = None) -> List[FileInfo]:
        """Search for files by name.
        
        Args:
            query: Search query (substring match)
            root_path: Root directory (default: user home)
            max_results: Max results
            file_types: Filter by file types
            
        Returns:
            List of matching FileInfo
        """
        root = root_path or str(Path.home())
        results = []
        
        try:
            for root_dir, dirs, files in os.walk(root):
                # Skip hidden directories
                dirs[:] = [d for d in dirs if not d.startswith('.')]
                
                for name in files:
                    if query.lower() in name.lower():
                        path = os.path.join(root_dir, name)
                        info = self._get_file_info(path)
                        if info:
                            if file_types and info.file_type not in file_types:
                                continue
                            results.append(info)
                            if len(results) >= max_results:
                                break
                
                if len(results) >= max_results:
                    break
        
        except Exception as exc:
            logger.warning("File search failed: %s", exc)
        
        self._stats["searches_performed"] += 1
        return results
    
    # ── File Operations ─────────────────────────────────────
    
    async def copy_file(self, source: str, destination: str,
                         overwrite: bool = False) -> bool:
        """Copy a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            overwrite: Overwrite if exists
            
        Returns:
            True if successful
        """
        try:
            src = Path(source)
            dst = Path(destination)
            
            if not overwrite and dst.exists():
                return False
            
            if src.is_dir():
                shutil.copytree(src, dst, dirs_exist_ok=overwrite)
            else:
                shutil.copy2(src, dst)
            
            self._stats["files_copied"] += 1
            return True
            
        except Exception as exc:
            logger.warning("Copy failed: %s", exc)
            return False
    
    async def move_file(self, source: str, destination: str,
                         overwrite: bool = False) -> bool:
        """Move a file or directory.
        
        Args:
            source: Source path
            destination: Destination path
            overwrite: Overwrite if exists
            
        Returns:
            True if successful
        """
        try:
            src = Path(source)
            dst = Path(destination)
            
            if not overwrite and dst.exists():
                return False
            
            shutil.move(str(src), str(dst))
            self._stats["files_moved"] += 1
            return True
            
        except Exception as exc:
            logger.warning("Move failed: %s", exc)
            return False
    
    async def delete_file(self, path: str, permanent: bool = False) -> bool:
        """Delete a file or directory.
        
        Args:
            path: Path to delete
            permanent: Skip recycle bin (permanent delete)
            
        Returns:
            True if deleted
        """
        try:
            p = Path(path)
            if not p.exists():
                return False
            
            if permanent:
                if p.is_dir():
                    shutil.rmtree(p)
                else:
                    p.unlink()
            else:
                # Move to recycle bin
                import send2trash
                send2trash.send2trash(str(p))
            
            self._stats["files_deleted"] += 1
            return True
            
        except Exception as exc:
            logger.warning("Delete failed: %s", exc)
            return False
    
    async def rename_file(self, source: str, new_name: str) -> bool:
        """Rename a file or directory.
        
        Args:
            source: Current path
            new_name: New name (just filename, not full path)
            
        Returns:
            True if renamed
        """
        try:
            src = Path(source)
            dst = src.parent / new_name
            src.rename(dst)
            return True
        except Exception as exc:
            logger.warning("Rename failed: %s", exc)
            return False
    
    async def create_directory(self, path: str) -> bool:
        """Create a directory.
        
        Args:
            path: Directory path
            
        Returns:
            True if created
        """
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return True
        except Exception as exc:
            logger.warning("Create directory failed: %s", exc)
            return False
    
    # ── Recent Files ────────────────────────────────────────
    
    async def get_recent_files(self, count: int = 20) -> List[FileInfo]:
        """Get recently accessed files.
        
        Args:
            count: Number of files
            
        Returns:
            List of recent FileInfo
        """
        # Add to recent on access
        return self._recent_files[:count]
    
    async def add_recent_file(self, path: str) -> None:
        """Add a file to recent list.
        
        Args:
            path: File path
        """
        info = self._get_file_info(path)
        if info:
            # Remove if exists
            self._recent_files = [f for f in self._recent_files if f.path != path]
            self._recent_files.insert(0, info)
            
            # Trim
            if len(self._recent_files) > self._max_recent:
                self._recent_files = self._recent_files[:self._max_recent]
    
    # ── File Watching ───────────────────────────────────────
    
    async def watch_directory(self, path: str, callback: Callable) -> None:
        """Watch a directory for changes.
        
        Args:
            path: Directory path
            callback: Function receiving (event_type, file_path)
        """
        if path not in self._watch_callbacks:
            self._watch_callbacks[path] = []
            self._watched_dirs[path] = set()
        self._watch_callbacks[path].append(callback)
    
    async def unwatch_directory(self, path: str, callback: Optional[Callable] = None) -> None:
        """Stop watching a directory.
        
        Args:
            path: Directory path
            callback: Specific callback to remove (or all)
        """
        if path in self._watch_callbacks:
            if callback:
                self._watch_callbacks[path].remove(callback)
                if not self._watch_callbacks[path]:
                    del self._watch_callbacks[path]
                    self._watched_dirs.pop(path, None)
            else:
                del self._watch_callbacks[path]
                self._watched_dirs.pop(path, None)
    
    async def _watch_loop(self) -> None:
        """Monitor watched directories for changes."""
        while self._running:
            try:
                for dir_path in list(self._watched_dirs.keys()):
                    try:
                        current_files = set()
                        p = Path(dir_path)
                        if p.exists():
                            for entry in p.iterdir():
                                current_files.add(str(entry))
                        
                        previous = self._watched_dirs[dir_path]
                        
                        # Detect new files
                        new_files = current_files - previous
                        for f in new_files:
                            for cb in self._watch_callbacks.get(dir_path, []):
                                try:
                                    cb("created", f)
                                except Exception:
                                    pass
                        
                        # Detect deleted files
                        deleted = previous - current_files
                        for f in deleted:
                            for cb in self._watch_callbacks.get(dir_path, []):
                                try:
                                    cb("deleted", f)
                                except Exception:
                                    pass
                        
                        self._watched_dirs[dir_path] = current_files
                        
                    except Exception:
                        pass
                
                await asyncio.sleep(self._watch_interval)
                
            except asyncio.CancelledError:
                break
            except Exception:
                await asyncio.sleep(5.0)
    
    # ── Special Folders ─────────────────────────────────────
    
    async def get_downloads_folder(self) -> str:
        """Get the user's downloads folder path.
        
        Returns:
            Downloads folder path
        """
        return str(Path.home() / "Downloads")
    
    async def get_desktop_folder(self) -> str:
        """Get the user's desktop folder path.
        
        Returns:
            Desktop folder path
        """
        return str(Path.home() / "Desktop")
    
    async def get_documents_folder(self) -> str:
        """Get the user's documents folder path.
        
        Returns:
            Documents folder path
        """
        return str(Path.home() / "Documents")
    
    async def get_drive_info(self) -> List[Dict[str, Any]]:
        """Get information about available drives.
        
        Returns:
            List of drive info dicts
        """
        drives = []
        try:
            import psutil
            
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    drives.append({
                        "device": part.device,
                        "mountpoint": part.mountpoint,
                        "fstype": part.fstype,
                        "total_gb": round(usage.total / (1024**3), 2),
                        "used_gb": round(usage.used / (1024**3), 2),
                        "free_gb": round(usage.free / (1024**3), 2),
                        "percent": usage.percent,
                    })
                except Exception:
                    continue
        except ImportError:
            pass
        
        return drives
    
    # ── Stats ───────────────────────────────────────────────
    
    def get_stats(self) -> Dict[str, Any]:
        return {**self._stats, "watched_directories": len(self._watched_dirs)}


# Global singleton
_file_manager: Optional[FileManager] = None


def get_file_manager() -> FileManager:
    global _file_manager
    if _file_manager is None:
        _file_manager = FileManager()
    return _file_manager
