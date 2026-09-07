"""FileService - file and directory operations: copy, move, rename, delete, create folder, read folder."""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class FileService(Singleton):
    """Manage files and directories."""

    async def copy(self, source: str, destination: str) -> dict[str, Any]:
        """Copy a file or directory."""
        src = Path(source)
        dst = Path(destination)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {source}")
        try:
            if src.is_dir():
                shutil.copytree(src, dst)
            else:
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src, dst)
            return {"summary": f"Copied {source} -> {destination}"}
        except Exception as exc:
            logger.exception("Failed to copy %s", source)
            raise RuntimeError(f"Failed to copy: {exc}") from exc

    async def move(self, source: str, destination: str) -> dict[str, Any]:
        """Move a file or directory."""
        src = Path(source)
        dst = Path(destination)
        if not src.exists():
            raise FileNotFoundError(f"Source not found: {source}")
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
            return {"summary": f"Moved {source} -> {destination}"}
        except Exception as exc:
            logger.exception("Failed to move %s", source)
            raise RuntimeError(f"Failed to move: {exc}") from exc

    async def rename(self, path: str, new_name: str) -> dict[str, Any]:
        """Rename a file or directory."""
        src = Path(path)
        if not src.exists():
            raise FileNotFoundError(f"Not found: {path}")
        try:
            dst = src.parent / new_name
            src.rename(dst)
            return {"summary": f"Renamed {src.name} -> {new_name}"}
        except Exception as exc:
            logger.exception("Failed to rename %s", path)
            raise RuntimeError(f"Failed to rename: {exc}") from exc

    async def delete(self, path: str) -> dict[str, Any]:
        """Delete a file or empty directory."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return {"summary": f"Deleted {path}"}
        except Exception as exc:
            logger.exception("Failed to delete %s", path)
            raise RuntimeError(f"Failed to delete: {exc}") from exc

    async def create_folder(self, path: str) -> dict[str, Any]:
        """Create a new directory."""
        try:
            Path(path).mkdir(parents=True, exist_ok=True)
            return {"summary": f"Created folder {path}"}
        except Exception as exc:
            logger.exception("Failed to create folder %s", path)
            raise RuntimeError(f"Failed to create folder: {exc}") from exc

    async def read_folder(self, path: str = ".") -> dict[str, Any]:
        """List contents of a directory."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")
        if not p.is_dir():
            raise NotADirectoryError(f"Not a directory: {path}")
        try:
            entries = []
            for entry in p.iterdir():
                entries.append({
                    "name": entry.name,
                    "type": "directory" if entry.is_dir() else "file",
                    "size": entry.stat().st_size if entry.is_file() else 0,
                    "modified": entry.stat().st_mtime,
                })
            entries.sort(key=lambda e: (e["type"] != "directory", e["name"]))
            return {
                "path": str(p.resolve()),
                "entries": entries,
                "count": len(entries),
                "summary": f"Listed {len(entries)} entries in {path}",
            }
        except Exception as exc:
            logger.exception("Failed to read folder %s", path)
            raise RuntimeError(f"Failed to read folder: {exc}") from exc

    async def search_files(
        self,
        pattern: str,
        path: str = ".",
        max_results: int = 50,
    ) -> dict[str, Any]:
        """Search for files matching a glob pattern."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")
        try:
            results = []
            for entry in p.rglob(pattern):
                if entry.is_file():
                    results.append({
                        "path": str(entry.resolve()),
                        "name": entry.name,
                        "size": entry.stat().st_size,
                        "modified": entry.stat().st_mtime,
                    })
                if len(results) >= max_results:
                    break
            return {
                "pattern": pattern,
                "path": str(p.resolve()),
                "results": results,
                "count": len(results),
                "summary": f"Found {len(results)} files matching '{pattern}'",
            }
        except Exception as exc:
            logger.exception("Failed to search files")
            raise RuntimeError(f"Failed to search files: {exc}") from exc

    async def zip(self, source_paths: list[str], zip_path: str) -> dict[str, Any]:
        """Zip files and directories."""
        zipf = zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED)
        try:
            for path_str in source_paths:
                path = Path(path_str)
                if not path.exists():
                    raise FileNotFoundError(f"Source not found: {path_str}")
                if path.is_dir():
                    for root, _, files in os.walk(path):
                        for file in files:
                            file_path = Path(root) / file
                            zipf.write(file_path, file_path.relative_to(path.parent))
                else:
                    zipf.write(path, path.name)
            return {"summary": f"Created zip file: {zip_path}"}
        except Exception as exc:
            logger.exception("Failed to zip files")
            raise RuntimeError(f"Failed to zip files: {exc}") from exc
        finally:
            zipf.close()

    async def unzip(self, zip_path: str, extract_to: str) -> dict[str, Any]:
        """Unzip a file."""
        if not Path(zip_path).exists():
            raise FileNotFoundError(f"Zip file not found: {zip_path}")
        try:
            with zipfile.ZipFile(zip_path, "r") as zipf:
                zipf.extractall(extract_to)
            return {"summary": f"Extracted {zip_path} to {extract_to}"}
        except Exception as exc:
            logger.exception("Failed to unzip file")
            raise RuntimeError(f"Failed to unzip file: {exc}") from exc

    async def get_metadata(self, path: str) -> dict[str, Any]:
        """Get metadata for a file or directory."""
        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"Not found: {path}")
        try:
            stat = p.stat()
            return {
                "name": p.name,
                "path": str(p.resolve()),
                "type": "directory" if p.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
                "summary": f"Metadata for {path}",
            }
        except Exception as exc:
            logger.exception("Failed to get metadata for %s", path)
            raise RuntimeError(f"Failed to get metadata: {exc}") from exc