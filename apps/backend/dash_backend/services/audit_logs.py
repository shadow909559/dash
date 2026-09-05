"""Audit log service for tracking all command executions and system operations."""

from __future__ import annotations

import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Any

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class AuditLogService:
    """Persists audit log entries for security and compliance tracking.

    Logs are stored as rotating JSON files in the application data directory.
    """

    def __init__(self, log_dir: str | None = None) -> None:
        if log_dir:
            self._log_dir = Path(log_dir)
        else:
            self._log_dir = Path(os.getenv("DASH_AUDIT_LOG_DIR", Path.cwd() / "audit_logs"))
        self._log_dir.mkdir(parents=True, exist_ok=True)
        self._max_entries_per_file: int = 10000
        self._current_file: Path | None = None
        self._entries: list[dict[str, Any]] = []
        self._enabled: bool = True

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled

    def _get_log_file(self) -> Path:
        """Get or create the current log file based on date."""
        today = datetime.now().strftime("%Y-%m-%d")
        return self._log_dir / f"audit_{today}.jsonl"

    def log(
        self,
        event_type: str,
        user_id: str = "",
        action: str = "",
        category: str = "",
        status: str = "",
        details: dict[str, Any] | None = None,
        source_ip: str = "",
    ) -> None:
        """Record an audit log entry."""
        if not self._enabled:
            return
        entry = {
            "timestamp": time.time(),
            "datetime": datetime.now().isoformat(),
            "event_type": event_type,
            "user_id": user_id,
            "action": action,
            "category": category,
            "status": status,
            "details": details or {},
            "source_ip": source_ip,
        }
        self._entries.append(entry)
        # Flush immediately
        try:
            self._flush()
        except Exception:
            pass

    def _flush(self) -> None:
        """Flush entries to disk."""
        if not self._entries:
            return
        log_file = self._get_log_file()
        with open(log_file, "a", encoding="utf-8") as f:
            for entry in self._entries:
                f.write(json.dumps(entry, default=str) + "\n")
        self._entries.clear()

        # Rotate if too large
        try:
            if log_file.stat().st_size > 10 * 1024 * 1024:  # 10MB
                self._rotate(log_file)
        except Exception:
            pass

    def _rotate(self, log_file: Path) -> None:
        """Rotate log file when it gets too large."""
        try:
            stamp = datetime.now().strftime("%H%M%S")
            rotated = log_file.with_suffix(f".{stamp}.jsonl")
            log_file.rename(rotated)
        except Exception:
            pass

    def query(
        self,
        start_time: float | None = None,
        end_time: float | None = None,
        user_id: str | None = None,
        event_type: str | None = None,
        action: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit logs with filters."""
        results = []
        for log_file in sorted(self._log_dir.glob("audit_*.jsonl"), reverse=True):
            try:
                with open(log_file, "r", encoding="utf-8") as f:
                    for line in f:
                        try:
                            entry = json.loads(line)
                        except json.JSONDecodeError:
                            continue
                        if start_time and entry.get("timestamp", 0) < start_time:
                            continue
                        if end_time and entry.get("timestamp", 0) > end_time:
                            continue
                        if user_id and entry.get("user_id") != user_id:
                            continue
                        if event_type and entry.get("event_type") != event_type:
                            continue
                        if action and entry.get("action") != action:
                            continue
                        results.append(entry)
                        if len(results) >= limit:
                            return results
            except FileNotFoundError:
                pass
        return results

    def get_stats(self) -> dict[str, Any]:
        """Get audit log statistics."""
        total_entries = 0
        file_count = 0
        for log_file in self._log_dir.glob("audit_*.jsonl"):
            file_count += 1
            try:
                total_entries += sum(1 for _ in log_file.open())
            except Exception:
                pass
        return {
            "enabled": self._enabled,
            "log_directory": str(self._log_dir),
            "total_files": file_count,
            "total_entries": total_entries,
            "cached_entries": len(self._entries),
        }


# Global singleton
_audit_service: AuditLogService | None = None


def get_audit_service() -> AuditLogService:
    global _audit_service
    if _audit_service is None:
        _audit_service = AuditLogService()
    return _audit_service
