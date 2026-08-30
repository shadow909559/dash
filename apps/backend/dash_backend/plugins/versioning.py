"""Plugin Versioning - Version management and compatibility checking."""

from __future__ import annotations

import logging
from typing import Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class PluginVersion:
    def __init__(self, version_str: str):
        self.raw = version_str
        self.parts = self._parse(version_str)

    @staticmethod
    def _parse(v: str) -> Tuple[int, ...]:
        parts = []
        for p in v.replace("-", ".").replace("_", ".").split("."):
            try:
                parts.append(int(p))
            except ValueError:
                parts.append(0)
        return tuple(parts)

    def __lt__(self, other: "PluginVersion") -> bool:
        return self.parts < other.parts

    def __gt__(self, other: "PluginVersion") -> bool:
        return self.parts > other.parts

    def __eq__(self, other: "PluginVersion") -> bool:
        return self.parts == other.parts

    def __str__(self) -> str:
        return self.raw


class PluginVersionManager:
    def __init__(self):
        self._compatibility_cache: Dict[str, Dict[str, bool]] = {}
        self._dash_version = "1.0.0"

    def set_dash_version(self, version: str) -> None:
        self._dash_version = version

    def is_compatible(self, plugin_version: str,
                       min_dash_version: str = "0.1.0",
                       max_dash_version: Optional[str] = None) -> bool:
        dv = PluginVersion(self._dash_version)
        pv = PluginVersion(min_dash_version)
        if dv < pv:
            return False
        if max_dash_version:
            mv = PluginVersion(max_dash_version)
            if dv > mv:
                return False
        return True

    def compare(self, v1: str, v2: str) -> int:
        pv1 = PluginVersion(v1)
        pv2 = PluginVersion(v2)
        if pv1 < pv2:
            return -1
        if pv1 > pv2:
            return 1
        return 0


_plugin_version_manager: Optional[PluginVersionManager] = None


def get_plugin_version_manager() -> PluginVersionManager:
    global _plugin_version_manager
    if _plugin_version_manager is None:
        _plugin_version_manager = PluginVersionManager()
    return _plugin_version_manager
