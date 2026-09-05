"""Local device identity for the single-user DASH installation.

DASH is a personal, single-user system: the Windows user account / device is
the identity boundary. There is no login UI. Instead:

    Windows starts
        -> DASH Core starts
        -> DASH generates (once) or loads a persistent installation identity
        -> Local DASH clients read the same identity file and authenticate
           every REST/WebSocket request with the device token.

Security properties:
- The identity file lives under %LOCALAPPDATA%\\DASH (user-scoped) and is
  ACL-hardened on Windows so only the current Windows user can read it.
- The token is a 384-bit URL-safe random secret generated at install time.
- Verification compares SHA-256 hashes in constant time; the raw token is
  never logged.
- Requests without a valid device token are rejected with 401/403. There is
  NO fallback that provisions a guest identity.

Environment overrides (explicit, documented):
- DASH_IDENTITY_FILE : absolute path to the identity JSON file.
- DASH_DEVICE_TOKEN  : explicit token value (used by tests/CI and headless
  bootstrap). When set, it takes precedence over the stored token for
  verification but never overwrites the file.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import subprocess
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_IDENTITY_VERSION = 1


class DeviceIdentityError(RuntimeError):
    """Raised when the device identity cannot be established."""


@dataclass(frozen=True)
class DeviceIdentity:
    install_id: str
    device_token: str
    created_at: str
    path: str

    @property
    def token_fingerprint(self) -> str:
        """Short non-reversible fingerprint safe for logs."""
        return hashlib.sha256(self.device_token.encode()).hexdigest()[:12]


_lock = threading.Lock()
_cached_identity: DeviceIdentity | None = None


def _identity_file_path() -> Path:
    override = os.environ.get("DASH_IDENTITY_FILE")
    if override:
        return Path(override)

    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DASH" / "identity.json"

    # Non-Windows (development/CI): user-scoped dot directory.
    return Path.home() / ".dash" / "identity.json"


def _harden_windows_acl(path: Path) -> None:
    """Best-effort: restrict the file to the current Windows user only."""
    user = os.environ.get("USERNAME", "")
    if not user:
        logger.warning("Cannot harden identity-file ACLs: USERNAME not set")
        return
    try:
        proc = subprocess.run(
            ["icacls", str(path), "/inheritance:r", "/grant:r", f"{user}:F"],
            capture_output=True,
            text=True,
            windowsHide=True,
        )
        if proc.returncode != 0:
            logger.warning(
                "icacls failed to restrict %s (rc=%s): %s",
                path,
                proc.returncode,
                (proc.stderr or proc.stdout or "").strip(),
            )
        else:
            logger.info("Identity file ACL restricted to user '%s': %s", user, path)
    except Exception:
        logger.warning("Could not harden ACLs on identity file", exc_info=True)


def _create_identity(path: Path) -> DeviceIdentity:
    identity = DeviceIdentity(
        install_id=secrets.token_hex(16),
        device_token=secrets.token_urlsafe(48),
        created_at=datetime.now(timezone.utc).isoformat(),
        path=str(path),
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "version": _IDENTITY_VERSION,
        "install_id": identity.install_id,
        "device_token": identity.device_token,
        "created_at": identity.created_at,
    }
    try:
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    except OSError as exc:
        raise DeviceIdentityError(f"Cannot write DASH identity file at {path}: {exc}") from exc

    if os.name == "nt":
        _harden_windows_acl(path)

    logger.info(
        "Created new DASH device identity install_id=%s fingerprint=%s at %s",
        identity.install_id,
        identity.token_fingerprint,
        path,
    )
    return identity


def _load_identity(path: Path) -> DeviceIdentity:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DeviceIdentityError(f"DASH identity file at {path} is unreadable/corrupt: {exc}") from exc

    token = payload.get("device_token")
    install_id = payload.get("install_id")
    if not token or not install_id:
        raise DeviceIdentityError(f"DASH identity file at {path} is missing required fields")

    return DeviceIdentity(
        install_id=str(install_id),
        device_token=str(token),
        created_at=str(payload.get("created_at", "")),
        path=str(path),
    )


def get_identity(force_reload: bool = False) -> DeviceIdentity:
    """Load or create the persistent installation identity (cached)."""
    global _cached_identity
    with _lock:
        if _cached_identity is not None and not force_reload:
            return _cached_identity

        env_token = os.environ.get("DASH_DEVICE_TOKEN")
        path = _identity_file_path()

        if env_token:
            # Explicit bootstrap token (tests/CI). Prefer file metadata if present.
            if path.exists():
                base = _load_identity(path)
                _cached_identity = DeviceIdentity(
                    install_id=base.install_id,
                    device_token=env_token,
                    created_at=base.created_at,
                    path=str(path),
                )
            else:
                _cached_identity = DeviceIdentity(
                    install_id=secrets.token_hex(16),
                    device_token=env_token,
                    created_at=datetime.now(timezone.utc).isoformat(),
                    path=str(path),
                )
            logger.info(
                "Using DASH_DEVICE_TOKEN from environment (install_id=%s fingerprint=%s)",
                _cached_identity.install_id,
                _cached_identity.token_fingerprint,
            )
            return _cached_identity

        if path.exists():
            _cached_identity = _load_identity(path)
            logger.info(
                "Loaded DASH device identity install_id=%s fingerprint=%s",
                _cached_identity.install_id,
                _cached_identity.token_fingerprint,
            )
        else:
            _cached_identity = _create_identity(path)

        return _cached_identity


def verify_device_token(token: str | None) -> bool:
    """Constant-time verification of a candidate device token."""
    if not token:
        return False
    identity = get_identity()
    expected = hmac.new(b"dash-device-token", identity.device_token.encode(), hashlib.sha256).hexdigest()
    provided = hmac.new(b"dash-device-token", token.encode(), hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, provided)


def rotate_device_token() -> DeviceIdentity:
    """Generate a fresh device token, preserving install_id. Clients must be
    re-provisioned after rotation."""
    global _cached_identity
    with _lock:
        current = get_identity()
        path = Path(current.path)
        new_token = secrets.token_urlsafe(48)
        payload = {
            "version": _IDENTITY_VERSION,
            "install_id": current.install_id,
            "device_token": new_token,
            "created_at": current.created_at,
            "rotated_at": datetime.now(timezone.utc).isoformat(),
        }
        path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
        if os.name == "nt":
            _harden_windows_acl(path)
        _cached_identity = DeviceIdentity(
            install_id=current.install_id,
            device_token=new_token,
            created_at=current.created_at,
            path=str(path),
        )
        logger.warning(
            "Device token rotated install_id=%s new_fingerprint=%s", current.install_id, _cached_identity.token_fingerprint
        )
        return _cached_identity


def extract_ws_token(websocket) -> str | None:
    """Device token from WebSocket query param (?token=...) or x-dash-token header.

    Shared by all WebSocket endpoints to avoid duplication.
    """
    token = websocket.query_params.get("token")
    if not token:
        token = websocket.headers.get("x-dash-token")
    return token
