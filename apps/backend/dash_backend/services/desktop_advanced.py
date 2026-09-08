"""Desktop advanced: clipboard, screenshots, file browser, session replay, backup, debug."""
from __future__ import annotations

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class ClipboardHistoryService:
    """Track and search past clipboard contents."""

    def __init__(self) -> None:
        self._history: list[dict] = []
        self._max_size = 200

    def add(self, content: str, content_type: str = "text", source: str = "system") -> dict:
        entry = {"id": f"clip_{len(self._history)}", "content": content[:5000], "type": content_type, "source": source, "length": len(content), "copied_at": datetime.now(timezone.utc).isoformat()}
        self._history.append(entry)
        if len(self._history) > self._max_size:
            self._history = self._history[-self._max_size:]
        return {"ok": True, "entry": entry}

    def get_history(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._history[-limit:]))

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [h for h in self._history if q in h.get("content", "").lower()]

    def pin(self, clip_id: str) -> dict:
        for h in self._history:
            if h["id"] == clip_id:
                h["pinned"] = True
                return {"ok": True}
        return {"ok": False}

    def delete(self, clip_id: str) -> dict:
        self._history = [h for h in self._history if h["id"] != clip_id]
        return {"ok": True}

    def clear(self) -> dict:
        count = len(self._history)
        self._history.clear()
        return {"cleared": count}


class ScreenshotCaptureService:
    """Capture and annotate screenshots."""

    def __init__(self) -> None:
        self._captures: list[dict] = []

    def capture(self, region: str = "full", description: str = "") -> dict:
        capture = {"id": f"ss_{len(self._captures)}", "region": region, "description": description, "captured_at": datetime.now(timezone.utc).isoformat(), "annotations": []}
        self._captures.append(capture)
        return {"ok": True, "capture": capture}

    def annotate(self, capture_id: str, annotation_type: str, text: str, x: int = 0, y: int = 0) -> dict:
        for c in self._captures:
            if c["id"] == capture_id:
                ann = {"type": annotation_type, "text": text, "x": x, "y": y}
                c["annotations"].append(ann)
                return {"ok": True, "annotation": ann}
        return {"ok": False}

    def get_captures(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._captures[-limit:]))

    def delete(self, capture_id: str) -> dict:
        self._captures = [c for c in self._captures if c["id"] != capture_id]
        return {"ok": True}


class FileBrowserService:
    """Browse and manage files within the app."""

    def __init__(self) -> None:
        self._bookmarks: list[dict] = []
        self._recent: list[dict] = []

    def list_directory(self, path: str) -> dict:
        try:
            entries = []
            for name in sorted(os.listdir(path))[:100]:
                full = os.path.join(path, name)
                is_dir = os.path.isdir(full)
                entries.append({"name": name, "type": "directory" if is_dir else "file", "path": full, "size": 0 if is_dir else os.path.getsize(full)})
            return {"ok": True, "path": path, "entries": entries, "count": len(entries)}
        except PermissionError:
            return {"ok": False, "reason": "Permission denied"}
        except FileNotFoundError:
            return {"ok": False, "reason": "Path not found"}

    def bookmark(self, path: str, name: str = "") -> dict:
        bm = {"id": f"fbm_{len(self._bookmarks)}", "path": path, "name": name or path.split("/")[-1], "created_at": datetime.now(timezone.utc).isoformat()}
        self._bookmarks.append(bm)
        return {"ok": True, "bookmark": bm}

    def get_bookmarks(self) -> list[dict]:
        return list(self._bookmarks)

    def add_recent(self, path: str, action: str = "open") -> dict:
        self._recent.append({"path": path, "action": action, "timestamp": datetime.now(timezone.utc).isoformat()})
        if len(self._recent) > 100:
            self._recent = self._recent[-100:]
        return {"ok": True}

    def get_recent(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._recent[-limit:]))


class SessionReplayService:
    """Record and replay past sessions step by step."""

    def __init__(self) -> None:
        self._recordings: list[dict] = []
        self._current: Optional[dict] = None

    def start_recording(self, session_name: str = "") -> dict:
        self._current = {"id": f"rec_{len(self._recordings)}", "name": session_name or f"Session {len(self._recordings) + 1}", "events": [], "started_at": datetime.now(timezone.utc).isoformat()}
        return {"ok": True, "recording": self._current}

    def record_event(self, event_type: str, detail: str = "") -> dict:
        if self._current:
            self._current["events"].append({"type": event_type, "detail": detail, "timestamp": datetime.now(timezone.utc).isoformat()})
            return {"ok": True}
        return {"ok": False, "reason": "No active recording"}

    def stop_recording(self) -> dict:
        if self._current:
            self._current["stopped_at"] = datetime.now(timezone.utc).isoformat()
            self._recordings.append(self._current)
            result = dict(self._current)
            self._current = None
            return {"ok": True, "recording": result}
        return {"ok": False}

    def get_recordings(self, limit: int = 20) -> list[dict]:
        return list(reversed(self._recordings[-limit:]))

    def get_events(self, recording_id: str) -> list[dict]:
        for r in self._recordings:
            if r["id"] == recording_id:
                return r.get("events", [])
        return []


class BackupRestoreService:
    """Backup and restore all user data."""

    def __init__(self) -> None:
        self._backups: list[dict] = []

    def create_backup(self, name: str = "", include_settings: bool = True, include_memories: bool = True) -> dict:
        backup = {"id": f"backup_{len(self._backups)}", "name": name or f"Backup {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')}", "include_settings": include_settings, "include_memories": include_memories, "size_bytes": 0, "created_at": datetime.now(timezone.utc).isoformat()}
        self._backups.append(backup)
        return {"ok": True, "backup": backup}

    def get_backups(self) -> list[dict]:
        return list(self._backups)

    def delete_backup(self, backup_id: str) -> dict:
        self._backups = [b for b in self._backups if b["id"] != backup_id]
        return {"ok": True}

    def get_stats(self) -> dict:
        return {"total_backups": len(self._backups), "total_size": sum(b.get("size_bytes", 0) for b in self._backups)}


class DebugConsoleService:
    """Built-in debug console for developers."""

    def __init__(self) -> None:
        self._logs: list[dict] = []
        self._max_size = 5000

    def log(self, level: str, message: str, source: str = "", metadata: dict | None = None) -> dict:
        entry = {"level": level, "message": message, "source": source, "metadata": metadata or {}, "timestamp": datetime.now(timezone.utc).isoformat()}
        self._logs.append(entry)
        if len(self._logs) > self._max_size:
            self._logs = self._logs[-self._max_size // 2:]
        return {"ok": True}

    def get_logs(self, level: Optional[str] = None, source: Optional[str] = None, search: Optional[str] = None, limit: int = 100) -> list[dict]:
        result = self._logs
        if level:
            result = [l for l in result if l["level"] == level]
        if source:
            result = [l for l in result if source.lower() in l.get("source", "").lower()]
        if search:
            q = search.lower()
            result = [l for l in result if q in l.get("message", "").lower()]
        return list(reversed(result[-limit:]))

    def get_stats(self) -> dict:
        levels: dict[str, int] = {}
        for l in self._logs:
            levels[l["level"]] = levels.get(l["level"], 0) + 1
        return {"total": len(self._logs), "by_level": levels}

    def clear(self) -> dict:
        count = len(self._logs)
        self._logs.clear()
        return {"cleared": count}


clipboard_history = ClipboardHistoryService()
screenshot_capture = ScreenshotCaptureService()
file_browser = FileBrowserService()
session_replay = SessionReplayService()
backup_restore = BackupRestoreService()
debug_console = DebugConsoleService()
