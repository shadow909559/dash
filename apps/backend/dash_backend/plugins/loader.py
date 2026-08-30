"""Plugin loader - discovers, validates, and loads plugins."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.plugins.manifest import PluginManifest
from dash_backend.plugins.permissions import get_permission_registry

logger = get_logger(__name__)


class PluginInstance:
    """A loaded plugin instance with its manifest and module."""

    def __init__(self, manifest: PluginManifest, module: Any, directory: Path):
        self.manifest = manifest
        self.module = module
        self.directory = directory
        self._instance: Optional[Any] = None

    @property
    def instance(self) -> Any:
        """Get the plugin's main class instance (lazy-initialized)."""
        if self._instance is None:
            for attr_name in dir(self.module):
                attr = getattr(self.module, attr_name)
                if isinstance(attr, type) and hasattr(attr, "plugin_id"):
                    self._instance = attr()
                    break
        return self._instance

    def activate(self) -> None:
        """Activate the plugin (called during registration)."""
        if self.instance and hasattr(self.instance, "on_activate"):
            try:
                self.instance.on_activate()
            except Exception:
                logger.exception("Plugin %s on_activate failed", self.manifest.id)

    def deactivate(self) -> None:
        """Deactivate the plugin (called during unload)."""
        if self.instance and hasattr(self.instance, "on_deactivate"):
            try:
                self.instance.on_deactivate()
            except Exception:
                logger.exception("Plugin %s on_deactivate failed", self.manifest.id)


class PluginLoader:
    """Discovers and loads plugins from the filesystem."""

    def __init__(self, plugin_dirs: Optional[List[Path]] = None):
        if plugin_dirs:
            self._plugin_dirs = plugin_dirs
        else:
            # Default: look in plugins/ directories
            cwd = Path.cwd()
            self._plugin_dirs = [
                cwd / "plugins",
                cwd / "dash_backend" / "plugins" / "builtin",
                Path.home() / ".dash" / "plugins",
            ]
        self._loaded: Dict[str, PluginInstance] = {}

    def discover(self) -> List[PluginManifest]:
        """Discover available plugins without loading them."""
        manifests = []
        for directory in self._plugin_dirs:
            if not directory.exists():
                continue
            for entry in directory.iterdir():
                if entry.is_dir():
                    manifest = self._read_manifest(entry)
                    if manifest:
                        manifests.append(manifest)
        return manifests

    def load(self, plugin_id: str) -> Optional[PluginInstance]:
        """Load a specific plugin by ID."""
        if plugin_id in self._loaded:
            return self._loaded[plugin_id]

        for directory in self._plugin_dirs:
            candidate = directory / plugin_id
            if candidate.exists() and candidate.is_dir():
                return self._load_from_dir(candidate)

        logger.warning("Plugin '%s' not found in any plugin directory", plugin_id)
        return None

    def load_all(self) -> List[PluginInstance]:
        """Discover and load all available plugins."""
        instances = []
        for manifest in self.discover():
            try:
                instance = self._load_from_dir(
                    self._find_plugin_dir(manifest.id)
                )
                if instance:
                    instances.append(instance)
                    self._loaded[manifest.id] = instance
            except Exception:
                logger.exception("Failed to load plugin '%s'", manifest.id)
        return instances

    def unload(self, plugin_id: str) -> bool:
        """Unload a plugin by ID."""
        instance = self._loaded.pop(plugin_id, None)
        if instance:
            try:
                instance.deactivate()
            except Exception:
                logger.exception("Error deactivating plugin '%s'", plugin_id)
            return True
        return False

    def get_loaded(self, plugin_id: str) -> Optional[PluginInstance]:
        """Get a loaded plugin instance by ID."""
        return self._loaded.get(plugin_id)

    def list_loaded(self) -> List[PluginInstance]:
        """List all currently loaded plugins."""
        return list(self._loaded.values())

    def _read_manifest(self, directory: Path) -> Optional[PluginManifest]:
        """Read plugin manifest from a directory."""
        import json
        import yaml

        # Try JSON first, then YAML
        manifest_path = directory / "plugin.json"
        if manifest_path.exists():
            try:
                data = json.loads(manifest_path.read_text(encoding="utf-8"))
                return PluginManifest.from_dict(data)
            except Exception:
                logger.exception("Invalid manifest JSON in %s", manifest_path)

        manifest_path = directory / "plugin.yaml"
        if manifest_path.exists():
            try:
                data = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
                return PluginManifest.from_dict(data)
            except Exception:
                logger.exception("Invalid manifest YAML in %s", manifest_path)

        return None

    def _load_from_dir(self, directory: Path) -> Optional[PluginInstance]:
        """Load a plugin from a directory."""
        manifest = self._read_manifest(directory)
        if not manifest:
            logger.warning("No manifest found in %s", directory)
            return None

        entry_path = directory / manifest.entry_point
        if not entry_path.exists():
            logger.warning("Entry point '%s' not found for plugin '%s'", entry_path, manifest.id)
            return None

        # Load the module
        try:
            spec = importlib.util.spec_from_file_location(
                f"dash_plugin_{manifest.id}",
                str(entry_path),
            )
            if spec is None or spec.loader is None:
                logger.warning("Could not load spec for plugin '%s'", manifest.id)
                return None

            module = importlib.util.module_from_spec(spec)
            sys.modules[spec.name] = module
            spec.loader.exec_module(module)

            instance = PluginInstance(manifest, module, directory)

            # Grant permissions
            perm_registry = get_permission_registry()
            perm_registry.grant(manifest.id, manifest.permissions)

            instance.activate()
            logger.info("Loaded plugin '%s' v%s", manifest.id, manifest.version)
            return instance

        except Exception:
            logger.exception("Failed to load plugin module from '%s'", entry_path)
            return None

    def _find_plugin_dir(self, plugin_id: str) -> Path:
        """Find a plugin directory by ID."""
        for directory in self._plugin_dirs:
            candidate = directory / plugin_id
            if candidate.exists():
                return candidate
        raise FileNotFoundError(f"Plugin directory for '{plugin_id}' not found")


# Global loader singleton
_loader: Optional[PluginLoader] = None


def get_plugin_loader() -> PluginLoader:
    global _loader
    if _loader is None:
        _loader = PluginLoader()
    return _loader

