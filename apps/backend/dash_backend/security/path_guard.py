"""Filesystem path authorization for DASH local clients.

Every file-bearing endpoint (REST /files, WebSocket file commands) must route
paths through this module. It provides:

- Explicit allow-list of root directories (special user folders by default,
  extendable via DASH_ALLOWED_FILE_ROOTS).
- Canonical resolution + ancestry containment via ``Path.is_relative_to``
  (immune to the ``workspace`` vs ``workspace_evil`` prefix bypass).
- Traversal defense: ``..`` segments are resolved away *before* the check.
- Secret-file deny list: identity material (.env, keys, credentials) can be
  read, copied out, moved, renamed or deleted only when explicitly allowed.
"""

from __future__ import annotations

import os
from pathlib import Path

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class PathDenied(PermissionError):
    """Raised when a path is outside all allowed roots or is a protected file."""


_SECRET_NAMES = {
    ".env",
    ".env.local",
    ".env.production",
    ".env.development",
    "credentials.json",
    "secrets.json",
    # DASH's own credential store must never be readable through the API
    "identity.json",
}
_SECRET_SUFFIXES = (".pem", ".key", ".pfx", ".p12")
_SECRET_PREFIXES = ("id_rsa", "id_ed25519", "id_ecdsa", ".env")


def default_roots() -> list[Path]:
    """User special folders — the sensible allow-list for a personal assistant.

    Overlapping roots (e.g. Desktop inside Home) are intentional: any of
    them authorizes access, so ancestors like the home directory must be
    kept rather than deduplicated away.
    """
    home = Path.home()
    candidates = [
        home / "Desktop",
        home / "Documents",
        home / "Downloads",
        home / "Pictures",
        home / "Videos",
        home / "Music",
        home,
    ]
    roots: list[Path] = []
    for c in candidates:
        try:
            roots.append(c.resolve())
        except OSError:
            continue
    return roots


def _configured_extra_roots() -> list[Path]:
    raw = get_settings().allowed_file_roots_raw
    roots: list[Path] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            roots.append(Path(os.path.expandvars(part)).expanduser().resolve())
        except OSError:
            logger.warning("Ignoring unresolvable allowed-file-root entry: %s", part)
    return roots


def allowed_roots() -> list[Path]:
    """Effective allow-list (default special folders + configured extras)."""
    return _configured_extra_roots() + default_roots()


def is_secret_file(path: Path) -> bool:
    name = path.name.lower()
    return name in _SECRET_NAMES or name.startswith(_SECRET_PREFIXES) or name.endswith(_SECRET_SUFFIXES)


def resolve_allowed(path_str: str) -> Path:
    """Resolve ``path_str`` and verify it is inside an allowed root.

    Raises PathDenied for traversal attempts, sibling tricks, and anything
    escaping the allow-list. The returned Path is fully resolved.
    """
    if not path_str or not path_str.strip():
        raise PathDenied("Empty path")

    stripped = path_str.strip()

    # Reject paths that are just special characters (e.g. "$" resolves to cwd on Windows)
    if not any(c.isalnum() for c in stripped.replace("\\", "").replace("/", "")):
        raise PathDenied(f"Path contains no alphanumeric characters: {stripped}")

    candidate = Path(os.path.expandvars(stripped)).expanduser()

    # Special folder aliases like "desktop" keep working.
    from dash_backend.api.routes.files_rest import SPECIAL_FOLDERS

    if candidate.parts and len(candidate.parts) == 1 and candidate.parts[0].lower() in SPECIAL_FOLDERS:
        resolved = Path(SPECIAL_FOLDERS[candidate.parts[0].lower()]).resolve()
    else:
        try:
            resolved = candidate.resolve(strict=False)
        except OSError as exc:
            raise PathDenied(f"Cannot resolve path: {exc}") from exc

    for root in allowed_roots():
        if resolved == root or resolved.is_relative_to(root):
            return resolved

    logger.warning("Path denied (outside allowed roots): %s -> %s", path_str, resolved)
    raise PathDenied(f"Path is outside allowed directories: {resolved}")


def ensure_writable(path_str: str, *, allow_secret_files: bool = False) -> Path:
    """Resolve + allowlist check for destructive operations."""
    resolved = resolve_allowed(path_str)
    if not allow_secret_files and is_secret_file(resolved):
        logger.warning("Path denied (protected secret file): %s", resolved)
        raise PathDenied(f"Refusing to modify protected file: {resolved.name}")
    return resolved
