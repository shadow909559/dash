"""Plugin SDK tests."""

from __future__ import annotations

import pytest
import tempfile
from pathlib import Path

from dash_backend.plugins.manifest import PluginManifest
from dash_backend.plugins.permissions import PermissionRegistry, get_permission_registry
from dash_backend.plugins.sandbox import PluginSandbox
from dash_backend.plugins.api import PluginAPI


class TestPluginManifest:
    def test_from_dict(self):
        data = {
            "id": "test-plugin",
            "name": "Test Plugin",
            "version": "1.0.0",
            "description": "A test plugin",
            "permissions": ["memory.read", "filesystem.read"],
        }
        manifest = PluginManifest.from_dict(data)
        assert manifest.id == "test-plugin"
        assert manifest.version == "1.0.0"
        assert "memory.read" in manifest.permissions

    def test_to_dict_roundtrip(self):
        manifest = PluginManifest(
            id="roundtrip",
            name="Roundtrip",
            version="0.1.0",
            permissions=["memory.read"],
        )
        data = manifest.to_dict()
        restored = PluginManifest.from_dict(data)
        assert restored.id == manifest.id
        assert restored.name == manifest.name
        assert restored.permissions == manifest.permissions


class TestPermissionRegistry:
    def test_grant_and_check(self):
        reg = PermissionRegistry()
        reg.grant("plugin-a", ["memory.read", "memory.write"])
        assert reg.has("plugin-a", "memory.read") is True
        assert reg.has("plugin-a", "shell") is False

    def test_require_passes(self):
        reg = PermissionRegistry()
        reg.grant("plugin-a", ["filesystem.read"])
        reg.require("plugin-a", "filesystem.read")

    def test_require_raises(self):
        reg = PermissionRegistry()
        reg.grant("plugin-a", ["memory.read"])
        with pytest.raises(PermissionError):
            reg.require("plugin-a", "filesystem.write")

    def test_revoke_permission(self):
        reg = PermissionRegistry()
        reg.grant("plugin-a", ["memory.read", "memory.write"])
        reg.revoke("plugin-a", "memory.write")
        assert reg.has("plugin-a", "memory.write") is False
        assert reg.has("plugin-a", "memory.read") is True

    def test_list_permissions(self):
        reg = PermissionRegistry()
        reg.grant("plugin-a", ["memory.read", "tools.execute"])
        perms = reg.list_permissions("plugin-a")
        assert "memory.read" in perms
        assert "tools.execute" in perms
        assert len(perms) == 2


class TestPluginSandbox:
    def test_sandbox_isolates_path(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_dir = Path(tmpdir) / "plugins" / "test-plugin"
            sandbox_dir.mkdir(parents=True)

            sandbox = PluginSandbox("test-plugin", workspace_root=sandbox_dir)
            reg = get_permission_registry()
            reg.grant("test-plugin", ["filesystem.read", "filesystem.write"])

            sandbox.write_file("hello.txt", "Hello, Plugin!")
            content = sandbox.read_file("hello.txt")
            assert content == "Hello, Plugin!"

            files = sandbox.list_files()
            assert any(f.name == "hello.txt" for f in files)

    def test_sandbox_rejects_path_traversal(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_dir = Path(tmpdir) / "plugins" / "test-plugin"
            sandbox_dir.mkdir(parents=True)

            sandbox = PluginSandbox("test-plugin", workspace_root=sandbox_dir)
            reg = get_permission_registry()
            reg.grant("test-plugin", ["filesystem.read"])

            with pytest.raises(PermissionError, match="Path traversal"):
                sandbox.read_file("../../etc/passwd")

    def test_sandbox_rejects_missing_permission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            plugin_id = "test-plugin-noperm"
            sandbox_dir = Path(tmpdir) / "plugins" / plugin_id
            sandbox_dir.mkdir(parents=True)

            sandbox = PluginSandbox(plugin_id, workspace_root=sandbox_dir)
            # Create a file first so FileNotFoundError doesn't mask PermissionError
            (sandbox_dir / "existing.txt").write_text("data")
            # Don't grant filesystem.read - should raise PermissionError
            with pytest.raises(PermissionError):
                sandbox.read_file("existing.txt")


class TestPluginAPI:
    def test_api_has_identity(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_dir = Path(tmpdir) / "plugins" / "test-plugin"
            sandbox_dir.mkdir(parents=True)

            sandbox = PluginSandbox("test-plugin", workspace_root=sandbox_dir)
            api = PluginAPI("test-plugin", sandbox)
            assert api.id == "test-plugin"

    @pytest.mark.asyncio
    async def test_api_memory_search_requires_permission(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            sandbox_dir = Path(tmpdir) / "plugins" / "test-plugin"
            sandbox_dir.mkdir(parents=True)

            sandbox = PluginSandbox("test-plugin", workspace_root=sandbox_dir)
            api = PluginAPI("test-plugin", sandbox)

            # Don't grant memory.read - should raise PermissionError
            with pytest.raises(PermissionError):
                await api.memory_search("test query")

