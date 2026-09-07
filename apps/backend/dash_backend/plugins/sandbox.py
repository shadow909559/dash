"""Plugin sandbox - restricts plugin filesystem and shell access."""

from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.plugins.permissions import get_permission_registry

logger = get_logger(__name__)


class PluginSandbox:
    """Restricts plugin access to filesystem and shell.

    All plugin file operations must go through this sandbox to ensure
    plugins cannot access files outside their designated workspace.
    """

    def __init__(self, plugin_id: str, workspace_root: Optional[Path] = None):
        self.plugin_id = plugin_id
        # Plugin workspace is isolated to its directory
        if workspace_root:
            self._workspace = workspace_root.resolve()
        else:
            self._workspace = Path.cwd().resolve() / "plugins" / plugin_id

        self._perm_registry = get_permission_registry()

    @property
    def workspace(self) -> Path:
        return self._workspace

    def read_file(self, path: str) -> str:
        """Read a file within the plugin workspace."""
        self._perm_registry.require(self.plugin_id, "filesystem.read")
        resolved = self._resolve_path(path)
        return resolved.read_text(encoding="utf-8")

    def write_file(self, path: str, content: str) -> int:
        """Write a file within the plugin workspace."""
        self._perm_registry.require(self.plugin_id, "filesystem.write")
        resolved = self._resolve_path(path)
        resolved.parent.mkdir(parents=True, exist_ok=True)
        return resolved.write_text(content, encoding="utf-8")

    def delete_file(self, path: str) -> None:
        """Delete a file within the plugin workspace."""
        self._perm_registry.require(self.plugin_id, "filesystem.delete")
        resolved = self._resolve_path(path)
        resolved.unlink()

    def list_files(self, path: str = ".") -> List[Path]:
        """List files within the plugin workspace."""
        self._perm_registry.require(self.plugin_id, "filesystem.read")
        resolved = self._resolve_path(path)
        if not resolved.exists():
            return []
        return [p for p in resolved.iterdir()]

    def run_command(self, command: List[str], timeout: int = 30) -> Dict[str, Any]:
        """Run a shell command (requires 'shell' permission).

        Only allows commands that do not start with dangerous operations.
        """
        self._perm_registry.require(self.plugin_id, "shell")

        dangerous_prefixes = ["rm", "del", "format", "shutdown", "reboot", "sudo", "chmod"]
        if command and command[0].lower() in dangerous_prefixes:
            raise PermissionError(f"Dangerous command not allowed: {command[0]}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self._workspace),
            )
            return {
                "returncode": result.returncode,
                "stdout": result.stdout[:5000],
                "stderr": result.stderr[:2000],
            }
        except subprocess.TimeoutExpired:
            return {"returncode": -1, "stdout": "", "stderr": "timeout"}
        except Exception as exc:
            return {"returncode": -1, "stdout": "", "stderr": str(exc)}

    def make_network_request(self, method: str, url: str, **kwargs: Any) -> Dict[str, Any]:
        """Make an HTTP request (requires 'network' permission)."""
        self._perm_registry.require(self.plugin_id, "network")
        import httpx
        try:
            with httpx.Client(timeout=15.0) as client:
                response = client.request(method, url, **kwargs)
            return {
                "status_code": response.status_code,
                "headers": dict(response.headers),
                "text": response.text[:10000],
            }
        except Exception as exc:
            return {"error": str(exc)}

    def _resolve_path(self, path: str) -> Path:
        """Resolve a path and ensure it stays within the workspace.

        Uses canonical resolution + ``Path.is_relative_to`` ancestry checking.
        A plain string-prefix check would wrongly accept sibling directories
        such as ``workspace_evil`` next to ``workspace``.
        """
        resolved = (self._workspace / path).resolve()
        workspace_resolved = self._workspace.resolve()
        if resolved != workspace_resolved and not resolved.is_relative_to(workspace_resolved):
            raise PermissionError(f"Path traversal blocked: '{path}' is outside plugin workspace")
        return resolved

