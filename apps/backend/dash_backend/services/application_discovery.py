"""Application Discovery Service for DASH AI OS.

Automatically discovers installed applications on Windows, mapping common
application names to their discovered executable paths. NEVER hardcodes
paths — all locations are discovered at runtime via the registry, Start Menu,
Program Files, and PATH.

Why this exists: The AI must be able to "open Chrome" without knowing where
Chrome is installed. This service provides a name→path resolution layer on
top of the existing registry/shortcut scanning.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.services.singleton import Singleton

logger = get_logger(__name__)

IS_WINDOWS = sys.platform == "win32"


class ApplicationDiscoveryService(Singleton):
    """Discover and resolve installed applications.

    Provides:
    - `discover_all()`: enumerate all installed apps (registry + shortcuts)
    - `resolve(name)`: map a friendly name to a discovered executable/launch path
    - `search(query)`: fuzzy search by name
    - Known-app alias mapping for common apps (used as search hints only,
      never as hardcoded launch paths).
    """

    # Common app aliases used to improve search matching. These are display
    # name hints, NOT paths. Actual paths are always discovered.
    KNOWN_ALIASES: Dict[str, List[str]] = {
        "chrome": ["google chrome", "chrome"],
        "edge": ["microsoft edge", "edge"],
        "firefox": ["mozilla firefox", "firefox"],
        "visual studio code": ["visual studio code", "vscode", "code"],
        "visual studio": ["visual studio"],
        "cursor": ["cursor"],
        "notepad": ["notepad", "notepad++"],
        "word": ["microsoft word", "word"],
        "excel": ["microsoft excel", "excel"],
        "powerpoint": ["microsoft powerpoint", "powerpoint"],
        "discord": ["discord"],
        "spotify": ["spotify"],
        "steam": ["steam"],
        "epic games": ["epic games", "epic games launcher"],
        "obs": ["obs studio", "obs"],
        "photoshop": ["adobe photoshop", "photoshop"],
        "blender": ["blender"],
        "android studio": ["android studio"],
        "intellij": ["intellij idea"],
        "pycharm": ["pycharm"],
        "terminal": ["windows terminal", "terminal"],
        "powershell": ["powershell"],
        "cmd": ["command prompt", "cmd", "command line"],
        "task manager": ["task manager"],
        "settings": ["settings"],
        "control panel": ["control panel"],
        "explorer": ["file explorer", "explorer"],
        "recycle bin": ["recycle bin"],
    }

    def __init__(self) -> None:
        self._cache: List[Dict[str, Any]] = []
        self._cache_loaded: bool = False

    # ────────────────────────────────────────────────────────
    # Discovery (registry + shortcuts + PATH)
    # ────────────────────────────────────────────────────────

    def _scan_registry(self) -> List[Dict[str, Any]]:
        """Scan the Windows registry for installed applications."""
        apps: List[Dict[str, Any]] = []
        if not IS_WINDOWS:
            return apps

        try:
            import winreg
            reg_paths = [
                (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_LOCAL_MACHINE, r"Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall"),
                (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Uninstall"),
            ]
            for root, path in reg_paths:
                try:
                    with winreg.OpenKey(root, path) as key:
                        i = 0
                        while True:
                            try:
                                subkey_name = winreg.EnumKey(key, i)
                                with winreg.OpenKey(key, subkey_name) as subkey:
                                    try:
                                        name = winreg.QueryValueEx(subkey, "DisplayName")[0]
                                    except Exception:
                                        i += 1
                                        continue
                                    install_location = ""
                                    try:
                                        install_location = winreg.QueryValueEx(subkey, "InstallLocation")[0]
                                    except Exception:
                                        pass
                                    display_icon = ""
                                    try:
                                        display_icon = winreg.QueryValueEx(subkey, "DisplayIcon")[0]
                                    except Exception:
                                        pass
                                    if name:
                                        apps.append({
                                            "name": name,
                                            "path": install_location or self._extract_exe(display_icon),
                                            "source": "registry",
                                            "aliases": [],
                                        })
                                    i += 1
                            except WindowsError:
                                break
                except (WindowsError, PermissionError):
                    continue
        except Exception as exc:
            logger.debug("Registry scan failed: %s", exc)
        return apps

    def _scan_shortcuts(self) -> List[Dict[str, Any]]:
        """Scan Start Menu and Desktop for shortcuts (.lnk/.url)."""
        apps: List[Dict[str, Any]] = []
        if not IS_WINDOWS:
            return apps

        dirs = [
            Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path(os.environ.get("PROGRAMDATA", "C:\\ProgramData")) / "Microsoft" / "Windows" / "Start Menu" / "Programs",
            Path.home() / "Desktop",
            Path(os.environ.get("PUBLIC", "C:\\Users\\Public")) / "Desktop",
        ]

        for d in dirs:
            if not d.exists():
                continue
            try:
                for item in d.rglob("*"):
                    if item.suffix.lower() in (".lnk", ".url"):
                        apps.append({
                            "name": item.stem,
                            "path": str(item),
                            "source": "shortcut",
                            "aliases": [],
                        })
            except Exception:
                continue
        return apps

    def _scan_program_files(self) -> List[Dict[str, Any]]:
        """Scan Program Files for executables (top-level only for speed)."""
        apps: List[Dict[str, Any]] = []
        if not IS_WINDOWS:
            return apps

        dirs = [
            Path(os.environ.get("ProgramFiles", "C:\\Program Files")),
            Path(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")),
        ]
        for d in dirs:
            if not d.exists():
                continue
            try:
                for item in d.iterdir():
                    if item.is_dir():
                        # Look for a main exe matching the folder name
                        for exe in item.glob("*.exe"):
                            if exe.stem.lower() == item.stem.lower():
                                apps.append({
                                    "name": item.stem,
                                    "path": str(exe),
                                    "source": "program_files",
                                    "aliases": [],
                                })
                                break
            except Exception:
                continue
        return apps

    @staticmethod
    def _extract_exe(display_icon: str) -> str:
        """Extract an executable path from a DisplayIcon value."""
        if not display_icon:
            return ""
        # DisplayIcon may be like "C:\\path\\app.exe,0"
        path = display_icon.split(",")[0].strip().strip('"')
        return path

    def discover_all(self, refresh: bool = False) -> List[Dict[str, Any]]:
        """Discover all installed applications.

        Args:
            refresh: Force re-scan even if cached.

        Returns:
            List of app dicts with name, path, source, aliases.
        """
        if self._cache_loaded and not refresh:
            return self._cache

        apps: List[Dict[str, Any]] = []
        apps.extend(self._scan_registry())
        apps.extend(self._scan_shortcuts())
        apps.extend(self._scan_program_files())

        # Deduplicate by name (case-insensitive)
        seen: Dict[str, Dict[str, Any]] = {}
        for app in apps:
            key = app["name"].strip().lower()
            if not key:
                continue
            if key not in seen:
                seen[key] = app
            elif not seen[key]["path"] and app["path"]:
                seen[key]["path"] = app["path"]

        self._cache = list(seen.values())
        self._cache_loaded = True
        logger.info("Discovered %d installed applications", len(self._cache))
        return self._cache

    # ────────────────────────────────────────────────────────
    # Resolution & search
    # ────────────────────────────────────────────────────────

    def _normalize(self, name: str) -> str:
        """Normalize a name for matching."""
        return re.sub(r"[^a-z0-9]+", " ", name.lower()).strip()

    def _matches(self, app_name: str, query: str) -> bool:
        """Check if an app name matches a query (substring on normalized)."""
        app_norm = self._normalize(app_name)
        query_norm = self._normalize(query)
        if not query_norm:
            return False
        return query_norm in app_norm or app_norm in query_norm

    def resolve(self, name: str) -> Optional[Dict[str, Any]]:
        """Resolve a friendly application name to a discovered app.

        Args:
            name: Friendly name (e.g., "Chrome", "VS Code", "Word").

        Returns:
            Best-matching app dict or None.
        """
        query = name.strip()
        if not query:
            return None

        apps = self.discover_all()
        query_lower = query.lower()

        # 1. Direct match on known aliases
        for canonical, aliases in self.KNOWN_ALIASES.items():
            if query_lower in aliases or query_lower == canonical:
                # Find the best app whose name matches any alias
                best = None
                for app in apps:
                    app_lower = app["name"].lower()
                    if any(a in app_lower for a in aliases):
                        if best is None or best["name"].lower() not in app_lower:
                            best = app
                return best

        # 2. Direct substring match
        matches = [app for app in apps if self._matches(app["name"], query)]
        if matches:
            # Prefer apps with discoverable paths
            matches.sort(key=lambda a: (bool(a["path"]), a["name"]))
            return matches[0]

        return None

    def search(self, query: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Search for applications by name.

        Args:
            query: Search query.
            limit: Max results.

        Returns:
            List of matching app dicts.
        """
        if not query:
            return self.discover_all()[:limit]

        apps = self.discover_all()
        query_lower = query.lower()

        # Collect from aliases first
        alias_matches: List[Dict[str, Any]] = []
        for canonical, aliases in self.KNOWN_ALIASES.items():
            if any(query_lower in a or a in query_lower for a in aliases):
                for app in apps:
                    if any(a in app["name"].lower() for a in aliases):
                        if app not in alias_matches:
                            alias_matches.append(app)

        direct = [app for app in apps if self._matches(app["name"], query)]
        seen = set()
        results: List[Dict[str, Any]] = []
        for app in alias_matches + direct:
            key = app["name"].lower()
            if key not in seen:
                seen.add(key)
                results.append(app)
            if len(results) >= limit:
                break
        return results

    def get_app(self, name: str) -> Optional[Dict[str, Any]]:
        """Get a resolved app; raises-friendly wrapper around resolve."""
        return self.resolve(name)


# Global singleton
_discovery: Optional[ApplicationDiscoveryService] = None


def get_application_discovery() -> ApplicationDiscoveryService:
    """Get or create the global ApplicationDiscoveryService singleton."""
    global _discovery
    if _discovery is None:
        _discovery = ApplicationDiscoveryService()
    return _discovery
