"""Permission service - manages command whitelist and approval decisions.

Every command requiring approval goes through this service.
Supports:
  - Always allow (whitelist)
  - Always deny (blacklist)
  - Per-category permissions
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)


class PermissionService(Singleton):
    """Manages command approval decisions."""

    def __init__(self) -> None:
        # user_id -> category -> set of actions always allowed
        self._always_allowed: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )
        # user_id -> category -> set of actions always denied
        self._always_denied: dict[str, dict[str, set[str]]] = defaultdict(
            lambda: defaultdict(set)
        )

    def add_always_allowed(
        self,
        user_id: str,
        category: str,
        action: str,
    ) -> None:
        """Add an action to the always-allow list for a user."""
        self._always_allowed[user_id][category].add(action)
        logger.info(
            "Always allow: user=%s cat=%s action=%s",
            user_id, category, action,
        )

    def remove_always_allowed(
        self,
        user_id: str,
        category: str,
        action: str,
    ) -> None:
        """Remove an action from the always-allow list."""
        if category in self._always_allowed.get(user_id, {}):
            self._always_allowed[user_id][category].discard(action)
            logger.info(
                "Removed always-allow: user=%s cat=%s action=%s",
                user_id, category, action,
            )

    def is_always_allowed(
        self,
        user_id: str,
        category: str,
        action: str,
    ) -> bool:
        """Check if an action is always allowed for a user."""
        return action in self._always_allowed.get(user_id, {}).get(category, set())

    def add_denied_forever(
        self,
        user_id: str,
        category: str,
        action: str,
    ) -> None:
        """Add an action to the deny-forever list."""
        self._always_denied[user_id][category].add(action)
        logger.info(
            "Deny forever: user=%s cat=%s action=%s",
            user_id, category, action,
        )

    def is_denied(
        self,
        user_id: str,
        category: str,
        action: str,
    ) -> bool:
        """Check if an action is denied for a user."""
        return action in self._always_denied.get(user_id, {}).get(category, set())

    def get_allow_list(
        self,
        user_id: str,
    ) -> dict[str, list[str]]:
        """Get all always-allowed actions for a user."""
        return {
            cat: list(actions)
            for cat, actions in self._always_allowed.get(user_id, {}).items()
        }

    def get_deny_list(
        self,
        user_id: str,
    ) -> dict[str, list[str]]:
        """Get all denied actions for a user."""
        return {
            cat: list(actions)
            for cat, actions in self._always_denied.get(user_id, {}).items()
        }

    def clear_user_permissions(self, user_id: str) -> None:
        """Clear all permissions for a user."""
        self._always_allowed.pop(user_id, None)
        self._always_denied.pop(user_id, None)
        logger.info("Cleared permissions for user=%s", user_id)

    def get_status(self) -> dict[str, Any]:
        """Return snapshot of permission state."""
        return {
            "total_allow_entries": sum(
                len(actions)
                for user in self._always_allowed.values()
                for actions in user.values()
            ),
            "total_deny_entries": sum(
                len(actions)
                for user in self._always_denied.values()
                for actions in user.values()
            ),
            "users": list(
                set(list(self._always_allowed.keys()) + list(self._always_denied.keys()))
            ),
        }


# Global singleton
_permission_service: PermissionService | None = None


def get_permission_service() -> PermissionService:
    """Get or create the global PermissionService instance."""
    global _permission_service
    if _permission_service is None:
        _permission_service = PermissionService()
    return _permission_service
