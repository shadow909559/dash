"""Plugin system: API, marketplace, sandboxing, permissions."""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


# ── Plugin Permissions Model ───────────────────────────────────────────────

PLUGIN_PERMISSIONS = {
    "memory.read": "Read memories",
    "memory.write": "Create/edit memories",
    "memory.delete": "Delete memories",
    "conversation.read": "Read conversations",
    "conversation.send": "Send messages",
    "file.read": "Read files",
    "file.write": "Write files",
    "system.execute": "Execute system commands",
    "system.monitor": "Monitor system stats",
    "network.request": "Make HTTP requests",
    "notification.send": "Send notifications",
    "settings.read": "Read settings",
    "settings.write": "Modify settings",
    "auth.verify": "Verify authentication",
    "agent.invoke": "Invoke other agents",
    "workflow.trigger": "Trigger workflows",
    "voice.tts": "Text-to-speech",
    "voice.stt": "Speech-to-text",
    "browser.control": "Control browser",
    "calendar.read": "Read calendar",
    "calendar.write": "Write calendar events",
    "email.read": "Read emails",
    "email.send": "Send emails",
}


class PluginRegistry:
    """Plugin registration, management, and marketplace."""

    def __init__(self) -> None:
        self._plugins: dict[str, dict] = {}
        self._installed: dict[str, dict] = {}
        self._enabled: dict[str, bool] = {}
        self._ratings: dict[str, list[float]] = {}

        # Seed with sample marketplace plugins
        self._marketplace = [
            {
                "id": "plg_weather",
                "name": "Weather Assistant",
                "description": "Get weather forecasts and alerts for any location",
                "author": "dash-community",
                "version": "1.0.0",
                "category": "utilities",
                "permissions": ["network.request"],
                "rating": 4.5,
                "installs": 1250,
                "icon": "cloud-sun",
                "status": "available",
            },
            {
                "id": "plg_todoist",
                "name": "Todoist Sync",
                "description": "Sync DASH tasks with Todoist projects",
                "author": "dash-official",
                "version": "1.2.0",
                "category": "productivity",
                "permissions": ["network.request", "memory.write"],
                "rating": 4.2,
                "installs": 890,
                "icon": "check-circle",
                "status": "available",
            },
            {
                "id": "plg_github",
                "name": "GitHub Integration",
                "description": "Manage issues, PRs, and repos through DASH",
                "author": "dash-official",
                "version": "2.0.0",
                "category": "development",
                "permissions": ["network.request", "memory.read", "memory.write"],
                "rating": 4.7,
                "installs": 2100,
                "icon": "github",
                "status": "available",
            },
            {
                "id": "plg_notion",
                "name": "Notion Connector",
                "description": "Read and write Notion pages and databases",
                "author": "dash-community",
                "version": "1.1.0",
                "category": "productivity",
                "permissions": ["network.request", "memory.write", "memory.read"],
                "rating": 4.0,
                "installs": 560,
                "icon": "book-open",
                "status": "available",
            },
            {
                "id": "plg_slack",
                "name": "Slack Bridge",
                "description": "Send messages and search Slack channels from DASH",
                "author": "dash-official",
                "version": "1.3.0",
                "category": "communication",
                "permissions": ["network.request", "notification.send"],
                "rating": 4.4,
                "installs": 1800,
                "icon": "hash",
                "status": "available",
            },
            {
                "id": "plg_code_runner",
                "name": "Code Runner",
                "description": "Execute Python, JavaScript, and Bash snippets in a sandbox",
                "author": "dash-official",
                "version": "1.0.0",
                "category": "development",
                "permissions": ["system.execute", "file.read", "file.write"],
                "rating": 4.8,
                "installs": 3200,
                "icon": "play",
                "status": "available",
            },
            {
                "id": "plg_image_gen",
                "name": "Image Generator",
                "description": "Generate images from text prompts using Stable Diffusion",
                "author": "dash-community",
                "version": "0.9.0",
                "category": "creative",
                "permissions": ["network.request", "file.write"],
                "rating": 3.9,
                "installs": 720,
                "icon": "image",
                "status": "beta",
            },
            {
                "id": "plg_zapier",
                "name": "Zapier Connector",
                "description": "Connect to 5000+ apps through Zapier webhooks",
                "author": "dash-community",
                "version": "1.0.0",
                "category": "integration",
                "permissions": ["network.request"],
                "rating": 4.1,
                "installs": 940,
                "icon": "zap",
                "status": "available",
            },
        ]

    # ── Marketplace ─────────────────────────────────────────────────

    def get_marketplace(self, category: Optional[str] = None) -> list[dict]:
        plugins = self._marketplace
        if category:
            plugins = [p for p in plugins if p.get("category") == category]
        return sorted(plugins, key=lambda x: x.get("installs", 0), reverse=True)

    def get_marketplace_categories(self) -> list[str]:
        return sorted(set(p.get("category", "other") for p in self._marketplace))

    # ── Install / Uninstall ─────────────────────────────────────────

    def install(self, plugin_id: str, granted_permissions: list[str] | None = None) -> dict:
        plugin = next((p for p in self._marketplace if p["id"] == plugin_id), None)
        if not plugin:
            return {"ok": False, "reason": "Plugin not found in marketplace"}

        if plugin_id in self._installed:
            return {"ok": False, "reason": "Already installed"}

        perms = granted_permissions or plugin.get("permissions", [])

        # Validate requested permissions exist
        invalid = [p for p in perms if p not in PLUGIN_PERMISSIONS]
        if invalid:
            return {"ok": False, "reason": f"Invalid permissions: {invalid}"}

        install_record = {
            **plugin,
            "installed_at": datetime.now(timezone.utc).isoformat(),
            "granted_permissions": perms,
            "sandbox": True,
        }
        self._installed[plugin_id] = install_record
        self._enabled[plugin_id] = True

        return {"ok": True, "plugin": install_record}

    def uninstall(self, plugin_id: str) -> dict:
        if plugin_id not in self._installed:
            return {"ok": False, "reason": "Plugin not installed"}
        del self._installed[plugin_id]
        self._enabled.pop(plugin_id, None)
        return {"ok": True}

    def get_installed(self) -> list[dict]:
        result = []
        for pid, plugin in self._installed.items():
            result.append({
                **plugin,
                "enabled": self._enabled.get(pid, False),
            })
        return result

    def toggle(self, plugin_id: str, enabled: bool | None = None) -> dict:
        if plugin_id not in self._installed:
            return {"ok": False, "reason": "Plugin not installed"}
        self._enabled[plugin_id] = enabled if enabled is not None else not self._enabled.get(plugin_id, False)
        return {"ok": True, "enabled": self._enabled[plugin_id]}

    # ── Permissions ─────────────────────────────────────────────────

    def get_permissions(self, plugin_id: str) -> dict:
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return {"ok": False, "reason": "Plugin not installed"}
        return {
            "ok": True,
            "granted": plugin.get("granted_permissions", []),
            "available": list(PLUGIN_PERMISSIONS.keys()),
        }

    def grant_permission(self, plugin_id: str, permission: str) -> dict:
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return {"ok": False, "reason": "Plugin not installed"}
        if permission not in PLUGIN_PERMISSIONS:
            return {"ok": False, "reason": f"Unknown permission: {permission}"}
        perms = plugin.get("granted_permissions", [])
        if permission not in perms:
            perms.append(permission)
            plugin["granted_permissions"] = perms
        return {"ok": True}

    def revoke_permission(self, plugin_id: str, permission: str) -> dict:
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return {"ok": False, "reason": "Plugin not installed"}
        perms = plugin.get("granted_permissions", [])
        plugin["granted_permissions"] = [p for p in perms if p != permission]
        return {"ok": True}

    def check_permission(self, plugin_id: str, permission: str) -> bool:
        plugin = self._installed.get(plugin_id)
        if not plugin:
            return False
        if not self._enabled.get(plugin_id, False):
            return False
        return permission in plugin.get("granted_permissions", [])

    # ── Ratings ─────────────────────────────────────────────────────

    def rate_plugin(self, plugin_id: str, rating: float) -> dict:
        if not 1.0 <= rating <= 5.0:
            return {"ok": False, "reason": "Rating must be 1-5"}
        self._ratings.setdefault(plugin_id, []).append(rating)
        return {"ok": True, "rating": rating}

    def get_rating(self, plugin_id: str) -> dict:
        ratings = self._ratings.get(plugin_id, [])
        if not ratings:
            return {"avg": 0, "count": 0}
        return {"avg": round(sum(ratings) / len(ratings), 1), "count": len(ratings)}

    # ── Stats ───────────────────────────────────────────────────────

    def get_stats(self) -> dict:
        return {
            "marketplace_total": len(self._marketplace),
            "installed": len(self._installed),
            "enabled": sum(1 for v in self._enabled.values() if v),
            "categories": self.get_marketplace_categories(),
        }

    def get_all_permissions(self) -> dict:
        return PLUGIN_PERMISSIONS


# Singleton
plugin_registry = PluginRegistry()
