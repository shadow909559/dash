"""Sandbox and path-guard containment regression tests.

Proves the fixes for:
- plugins/sandbox.py ``startswith`` sibling-prefix bypass
- /files path policy (allowlist roots, traversal, secret files)
"""

from __future__ import annotations

from pathlib import Path

import pytest

from dash_backend.plugins.sandbox import PluginSandbox
from dash_backend.security.path_guard import (
    PathDenied,
    ensure_writable,
    is_secret_file,
    resolve_allowed,
)


# ── Plugin sandbox workspace containment ────────────────────────────


def _make_sandbox(tmp_path: Path) -> PluginSandbox:
    workspace = tmp_path / "workspace"
    workspace.mkdir(parents=True, exist_ok=True)
    return PluginSandbox(plugin_id="test-plugin", workspace_root=workspace)


@pytest.fixture
def sandbox(tmp_path: Path) -> PluginSandbox:
    ws = tmp_path / "ws"
    ws.mkdir()
    (ws / "file.txt").write_text("hello")
    (ws / "subdir").mkdir()
    (ws / "subdir" / "nested.txt").write_text("nested")
    return PluginSandbox(plugin_id="t", workspace_root=ws)


def test_workspace_file_allowed(sandbox: PluginSandbox, tmp_path: Path) -> None:
    resolved = sandbox._resolve_path("file.txt")
    assert resolved.is_relative_to((tmp_path / "ws").resolve())


def test_workspace_subdir_file_allowed(sandbox: PluginSandbox, tmp_path: Path) -> None:
    resolved = sandbox._resolve_path("subdir/nested.txt")
    assert resolved.is_relative_to((tmp_path / "ws").resolve())


def test_workspace_sibling_denied(sandbox: PluginSandbox, tmp_path: Path) -> None:
    """The old startswith() bug: 'ws_evil' passes a prefix check against 'ws'."""
    evil = tmp_path / "ws_evil"
    evil.mkdir(exist_ok=True)
    (evil / "stolen.txt").write_text("secret")
    with pytest.raises(PermissionError):
        sandbox._resolve_path("../ws_evil/stolen.txt")


def test_parent_directory_denied(sandbox: PluginSandbox, tmp_path: Path) -> None:
    with pytest.raises(PermissionError):
        sandbox._resolve_path("../../outside.txt")


def test_absolute_traversal_denied(sandbox: PluginSandbox) -> None:
    with pytest.raises(PermissionError):
        sandbox._resolve_path(str(Path.home() / "somewhere" / "else.txt"))


# ── Shared path guard (REST /files + WS file commands) ──────────────


def test_resolve_inside_home_allowed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASH_ALLOWED_FILE_ROOTS", str(tmp_path))
    from dash_backend.config import get_settings

    get_settings.cache_clear()
    try:
        target = tmp_path / "docs"
        target.mkdir()
        resolved = resolve_allowed(str(target))
        assert resolved == target.resolve()

        ensure = ensure_writable(str(target / "note.txt"))
        assert ensure.is_relative_to(target.resolve())
    finally:
        get_settings.cache_clear()


def test_resolve_outside_roots_denied(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DASH_ALLOWED_FILE_ROOTS", str(tmp_path))
    from dash_backend.config import get_settings

    get_settings.cache_clear()
    try:
        with pytest.raises(PathDenied):
            resolve_allowed(r"C:\Windows\System32\drivers\etc\hosts")
    finally:
        get_settings.cache_clear()


def test_secret_files_flagged(tmp_path: Path) -> None:
    assert is_secret_file(tmp_path / ".env")
    assert is_secret_file(tmp_path / ".env.production")
    assert is_secret_file(tmp_path / "id_rsa")
    assert is_secret_file(tmp_path / "server.pem")
    assert not is_secret_file(tmp_path / "notes.txt")
