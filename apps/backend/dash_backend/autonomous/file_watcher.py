"""File Watcher — react to filesystem changes in real-time.

Monitors directories for:
- New files (auto-organize downloads)
- Modified files (trigger backups)
- Deleted files (log activity)
- Large files (alert on disk usage)

Uses polling (no external dependency) for cross-platform compatibility.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Any, Callable

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

# Directories to watch by default
DEFAULT_WATCH_PATHS = [
    ("downloads", Path.home() / "Downloads"),
    ("desktop", Path.home() / "Desktop"),
]

POLL_INTERVAL = 5.0  # seconds between checks


class FileWatcher:
    """Monitors directories for changes and triggers callbacks."""

    def __init__(self):
        self._watchers: dict[str, dict[str, Any]] = {}
        self._callbacks: dict[str, list[Callable]] = {}
        self._snapshots: dict[str, dict[str, float]] = {}  # path -> {name: mtime}
        self._running = False

    def watch(
        self,
        name: str,
        path: str | Path,
        callback: Callable | None = None,
        patterns: list[str] | None = None,
    ) -> None:
        """Start watching a directory.

        Args:
            name: Watcher name for identification
            path: Directory to watch
            callback: Called with (event_type, filepath, details) on changes
            patterns: File extensions to watch (None = all)
        """
        path = Path(path)
        if not path.is_dir():
            logger.warning("Watch path does not exist: %s", path)
            return

        self._watchers[name] = {
            "path": path,
            "patterns": patterns,
            "created_at": time.time(),
        }
        self._callbacks[name] = [callback] if callback else []
        self._snapshots[name] = self._snapshot_dir(path, patterns)
        logger.info("Watching %s: %s", name, path)

    def unwatch(self, name: str) -> None:
        """Stop watching a directory."""
        self._watchers.pop(name, None)
        self._callbacks.pop(name, None)
        self._snapshots.pop(name, None)

    def add_callback(self, name: str, callback: Callable) -> None:
        """Add a callback to an existing watcher."""
        if name in self._callbacks:
            self._callbacks[name].append(callback)

    def check_once(self) -> list[dict[str, Any]]:
        """Check all watched directories for changes. Returns list of events."""
        events = []
        for name, watcher in self._watchers.items():
            path = watcher["path"]
            patterns = watcher["patterns"]
            old_snapshot = self._snapshots.get(name, {})
            new_snapshot = self._snapshot_dir(path, patterns)

            # Detect new files
            for filename, mtime in new_snapshot.items():
                if filename not in old_snapshot:
                    event = {"type": "created", "file": filename, "path": str(path / filename), "mtime": mtime}
                    events.append(event)
                    self._fire_callbacks(name, event)

            # Detect deleted files
            for filename in old_snapshot:
                if filename not in new_snapshot:
                    event = {"type": "deleted", "file": filename, "path": str(path / filename)}
                    events.append(event)
                    self._fire_callbacks(name, event)

            # Detect modified files
            for filename, mtime in new_snapshot.items():
                if filename in old_snapshot and mtime != old_snapshot[filename]:
                    event = {"type": "modified", "file": filename, "path": str(path / filename), "mtime": mtime}
                    events.append(event)
                    self._fire_callbacks(name, event)

            self._snapshots[name] = new_snapshot

        return events

    def get_status(self) -> dict[str, Any]:
        """Get watcher status."""
        return {
            "watching": len(self._watchers),
            "watchers": {
                name: {
                    "path": str(w["path"]),
                    "files": len(self._snapshots.get(name, {})),
                }
                for name, w in self._watchers.items()
            },
        }

    # ── Internal ──────────────────────────────────────────────────

    def _snapshot_dir(self, path: Path, patterns: list[str] | None) -> dict[str, float]:
        """Take a snapshot of directory contents (name -> mtime)."""
        snapshot = {}
        try:
            for entry in os.scandir(path):
                if entry.is_file():
                    if patterns:
                        ext = Path(entry.name).suffix.lower()
                        if ext not in patterns:
                            continue
                    try:
                        snapshot[entry.name] = entry.stat().st_mtime
                    except OSError:
                        continue
        except OSError:
            pass
        return snapshot

    def _fire_callbacks(self, watcher_name: str, event: dict[str, Any]) -> None:
        """Fire all callbacks for a watcher."""
        for cb in self._callbacks.get(watcher_name, []):
            try:
                cb(event)
            except Exception as exc:
                logger.debug("Callback error for %s: %s", watcher_name, exc)


# Singleton
_watcher: FileWatcher | None = None


def get_file_watcher() -> FileWatcher:
    global _watcher
    if _watcher is None:
        _watcher = FileWatcher()
    return _watcher


def setup_default_watchers() -> None:
    """Set up default file watchers for common directories."""
    watcher = get_file_watcher()

    for name, path in DEFAULT_WATCH_PATHS:
        if path.is_dir():
            watcher.watch(name, path)

    logger.info("Default file watchers configured")
