"""Plugin permission registry and enforcement."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


# Standard permission names
PERMISSION_NAMES = {
    "memory.read": "Read memories",
    "memory.write": "Write memories",
    "memory.delete": "Delete memories",
    "conversation.read": "Read conversations",
    "conversation.write": "Write conversations",
    "filesystem.read": "Read files in sandbox",
    "filesystem.write": "Write files in sandbox",
    "filesystem.delete": "Delete files in sandbox",
    "network": "Make network requests",
    "shell": "Execute shell commands",
    "tools.register": "Register new tools",
    "tools.execute": "Execute existing tools",
    "planner.read": "Read planner goals",
    "planner.write": "Write planner goals",
    "rag.read": "Read RAG documents",
    "rag.write": "Write RAG documents",
    "ui.notify": "Show notifications",
    "ui.toast": "Show toast messages",
    "user.id": "Access user ID",
    "user.email": "Access user email",
}


@dataclass
class PermissionRegistry:
    """Tracks which plugins have which permissions."""

    _permissions: Dict[str, List[str]] = field(default_factory=dict)

    def grant(self, plugin_id: str, permissions: List[str]) -> None:
        """Grant permissions to a plugin."""
        existing = self._permissions.setdefault(plugin_id, [])
        for perm in permissions:
            if perm not in existing:
                if perm in PERMISSION_NAMES or perm.startswith("custom:"):
                    existing.append(perm)
                else:
                    logger.warning("Unknown permission '%s' for plugin '%s'", perm, plugin_id)

    def revoke(self, plugin_id: str, permission: str) -> None:
        """Revoke a single permission."""
        perms = self._permissions.get(plugin_id, [])
        if permission in perms:
            perms.remove(permission)

    def has(self, plugin_id: str, permission: str) -> bool:
        """Check if a plugin has a specific permission."""
        return permission in self._permissions.get(plugin_id, [])

    def list_permissions(self, plugin_id: str) -> List[str]:
        """List all permissions granted to a plugin."""
        return list(self._permissions.get(plugin_id, []))

    def require(self, plugin_id: str, permission: str) -> None:
        """Assert that a plugin has a permission; raise PermissionError if not."""
        if not self.has(plugin_id, permission):
            raise PermissionError(
                f"Plugin '{plugin_id}' lacks required permission: '{permission}' "
                f"({PERMISSION_NAMES.get(permission, 'unknown')})"
            )


# Global permission registry
_registry: Optional[PermissionRegistry] = None


def get_permission_registry() -> PermissionRegistry:
    global _registry
    if _registry is None:
        _registry = PermissionRegistry()
    return _registry

