"""Plugin manifest model - defines plugin metadata and permissions."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class PluginManifest:
    """Plugin metadata and permission declarations.

    Plugins declare their requirements in a plugin.yaml or plugin.json
    file at the root of the plugin directory.
    """

    id: str
    name: str
    version: str
    description: str = ""
    author: str = ""
    license: str = "MIT"
    entry_point: str = "main.py"  # Python file to load

    # Permissions requested by the plugin
    permissions: List[str] = field(default_factory=list)

    # Tools the plugin registers
    tools: List[Dict[str, Any]] = field(default_factory=list)

    # Hooks the plugin listens for
    hooks: List[str] = field(default_factory=list)

    # Dependencies (Python packages)
    dependencies: List[str] = field(default_factory=list)

    min_dash_version: str = "0.1.0"
    max_dash_version: Optional[str] = None

    # Plugin-specific config
    config: Dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "PluginManifest":
        return cls(
            id=data.get("id", ""),
            name=data.get("name", ""),
            version=data.get("version", "0.1.0"),
            description=data.get("description", ""),
            author=data.get("author", ""),
            license=data.get("license", "MIT"),
            entry_point=data.get("entry_point", "main.py"),
            permissions=data.get("permissions", []),
            tools=data.get("tools", []),
            hooks=data.get("hooks", []),
            dependencies=data.get("dependencies", []),
            min_dash_version=data.get("min_dash_version", "0.1.0"),
            max_dash_version=data.get("max_dash_version"),
            config=data.get("config", {}),
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "license": self.license,
            "entry_point": self.entry_point,
            "permissions": self.permissions,
            "tools": self.tools,
            "hooks": self.hooks,
            "dependencies": self.dependencies,
            "min_dash_version": self.min_dash_version,
            "max_dash_version": self.max_dash_version,
            "config": self.config,
        }

