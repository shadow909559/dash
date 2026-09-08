"""Data management: retention, import/export, bulk ops, soft delete, versioning, archive."""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Any, Optional

logger = logging.getLogger(__name__)


class DataRetentionService:
    """Auto-delete old data based on configurable policies."""

    def __init__(self) -> None:
        self._policies: dict[str, dict] = {
            "memories": {"retention_days": 365, "auto_delete": False, "archive_before_delete": True},
            "conversations": {"retention_days": 90, "auto_delete": False, "archive_before_delete": True},
            "notifications": {"retention_days": 30, "auto_delete": True, "archive_before_delete": False},
            "audit_logs": {"retention_days": 365, "auto_delete": False, "archive_before_delete": True},
            "error_logs": {"retention_days": 14, "auto_delete": True, "archive_before_delete": False},
            "activity_events": {"retention_days": 60, "auto_delete": True, "archive_before_delete": False},
            "sessions": {"retention_days": 7, "auto_delete": True, "archive_before_delete": False},
            "backups": {"retention_days": 90, "auto_delete": True, "archive_before_delete": False},
        }
        self._deletion_log: list[dict] = []

    def get_policies(self) -> dict:
        return dict(self._policies)

    def set_policy(self, data_type: str, retention_days: int, auto_delete: bool = False, archive: bool = True) -> dict:
        self._policies[data_type] = {"retention_days": retention_days, "auto_delete": auto_delete, "archive_before_delete": archive}
        return {"ok": True, "policy": self._policies[data_type]}

    def check_expired(self, data_type: str, items: list[dict]) -> list[dict]:
        policy = self._policies.get(data_type, {})
        days = policy.get("retention_days", 30)
        cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
        return [i for i in items if i.get("created_at", "") < cutoff]

    def delete_expired(self, data_type: str, items: list[dict]) -> dict:
        expired = self.check_expired(data_type, items)
        for item in expired:
            self._deletion_log.append({"data_type": data_type, "item_id": item.get("id"), "deleted_at": datetime.now(timezone.utc).isoformat()})
        return {"deleted": len(expired), "remaining": len(items) - len(expired)}

    def get_deletion_log(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._deletion_log[-limit:]))


class VersioningService:
    """Track versions of any entity with history and rollback."""

    def __init__(self) -> None:
        self._versions: dict[str, list[dict]] = {}

    def save_version(self, entity_type: str, entity_id: str, data: dict, author: str = "system") -> dict:
        key = f"{entity_type}:{entity_id}"
        if key not in self._versions:
            self._versions[key] = []
        version_num = len(self._versions[key]) + 1
        version = {"version": version_num, "data": data, "author": author, "created_at": datetime.now(timezone.utc).isoformat()}
        self._versions[key].append(version)
        return {"ok": True, "version": version}

    def get_versions(self, entity_type: str, entity_id: str) -> list[dict]:
        return self._versions.get(f"{entity_type}:{entity_id}", [])

    def get_version(self, entity_type: str, entity_id: str, version: int) -> Optional[dict]:
        versions = self._versions.get(f"{entity_type}:{entity_id}", [])
        for v in versions:
            if v["version"] == version:
                return v
        return None

    def get_latest(self, entity_type: str, entity_id: str) -> Optional[dict]:
        versions = self._versions.get(f"{entity_type}:{entity_id}", [])
        return versions[-1] if versions else None

    def rollback(self, entity_type: str, entity_id: str, version: int) -> dict:
        target = self.get_version(entity_type, entity_id, version)
        if not target:
            return {"ok": False, "reason": "Version not found"}
        return self.save_version(entity_type, entity_id, target["data"], author=f"rollback_to_v{version}")


class ArchiveService:
    """Archive old data for long-term storage."""

    def __init__(self) -> None:
        self._archives: list[dict] = []

    def archive(self, data_type: str, items: list[dict], reason: str = "retention") -> dict:
        archive = {"id": f"arch_{len(self._archives)}", "data_type": data_type, "count": len(items), "reason": reason, "archived_at": datetime.now(timezone.utc).isoformat()}
        self._archives.append(archive)
        return {"ok": True, "archive": archive, "items_archived": len(items)}

    def get_archives(self, data_type: Optional[str] = None) -> list[dict]:
        if data_type:
            return [a for a in self._archives if a["data_type"] == data_type]
        return list(self._archives)

    def restore(self, archive_id: str) -> dict:
        for a in self._archives:
            if a["id"] == archive_id:
                return {"ok": True, "restored": a["count"], "data_type": a["data_type"]}
        return {"ok": False, "reason": "Archive not found"}

    def get_stats(self) -> dict:
        types: dict[str, int] = {}
        for a in self._archives:
            t = a["data_type"]
            types[t] = types.get(t, 0) + a["count"]
        return {"total_archives": len(self._archives), "by_type": types}


class SoftDeleteService:
    """Soft delete with recovery support."""

    def __init__(self) -> None:
        self._deleted: list[dict] = []

    def soft_delete(self, entity_type: str, entity_id: str, data: dict, deleted_by: str = "user") -> dict:
        entry = {"entity_type": entity_type, "entity_id": entity_id, "data": data, "deleted_by": deleted_by, "deleted_at": datetime.now(timezone.utc).isoformat(), "recoverable_until": (datetime.now(timezone.utc) + timedelta(days=30)).isoformat()}
        self._deleted.append(entry)
        return {"ok": True, "recoverable_until": entry["recoverable_until"]}

    def get_deleted(self, entity_type: Optional[str] = None) -> list[dict]:
        if entity_type:
            return [d for d in self._deleted if d["entity_type"] == entity_type]
        return list(self._deleted)

    def recover(self, entity_id: str) -> dict:
        for d in self._deleted:
            if d["entity_id"] == entity_id:
                self._deleted = [x for x in self._deleted if x["entity_id"] != entity_id]
                return {"ok": True, "data": d["data"]}
        return {"ok": False, "reason": "Not found"}

    def permanent_delete(self, entity_id: str) -> dict:
        before = len(self._deleted)
        self._deleted = [d for d in self._deleted if d["entity_id"] != entity_id]
        return {"ok": True, "deleted": before - len(self._deleted)}


class BulkOperationsService:
    """Bulk edit/delete/import operations."""

    def __init__(self) -> None:
        self._operations: list[dict] = []

    def bulk_delete(self, entity_type: str, entity_ids: list[str]) -> dict:
        op = {"type": "bulk_delete", "entity_type": entity_type, "count": len(entity_ids), "timestamp": datetime.now(timezone.utc).isoformat()}
        self._operations.append(op)
        return {"ok": True, "deleted": len(entity_ids)}

    def bulk_update(self, entity_type: str, entity_ids: list[str], updates: dict) -> dict:
        op = {"type": "bulk_update", "entity_type": entity_type, "count": len(entity_ids), "updates": list(updates.keys()), "timestamp": datetime.now(timezone.utc).isoformat()}
        self._operations.append(op)
        return {"ok": True, "updated": len(entity_ids)}

    def bulk_tag(self, entity_type: str, entity_ids: list[str], tags: list[str]) -> dict:
        op = {"type": "bulk_tag", "entity_type": entity_type, "count": len(entity_ids), "tags": tags, "timestamp": datetime.now(timezone.utc).isoformat()}
        self._operations.append(op)
        return {"ok": True, "tagged": len(entity_ids)}

    def get_operations(self, limit: int = 50) -> list[dict]:
        return list(reversed(self._operations[-limit:]))


retention_service = DataRetentionService()
versioning_service = VersioningService()
archive_service = ArchiveService()
soft_delete_service = SoftDeleteService()
bulk_operations = BulkOperationsService()
