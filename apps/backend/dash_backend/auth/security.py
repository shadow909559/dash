"""Authentication security helpers."""

import base64
import hashlib
import hmac
import json
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

from dash_backend.config import get_settings

_PASSWORD_HASH_ALGORITHM = "pbkdf2_sha256"
_JWT_TYPE_ACCESS = "access"


class InvalidTokenError(Exception):
    """Raised when a JWT is invalid or expired."""


class AuthConfigurationError(RuntimeError):
    """Raised when authentication settings are incomplete."""


def hash_password(password: str) -> str:
    """Hash a password with PBKDF2-SHA256."""
    settings = get_settings()
    salt = secrets.token_urlsafe(24)
    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        settings.password_hash_iterations,
    )
    encoded_digest = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return (
        f"{_PASSWORD_HASH_ALGORITHM}"
        f"${settings.password_hash_iterations}"
        f"${salt}"
        f"${encoded_digest}"
    )


def verify_password(password: str, stored_hash: str) -> bool:
    """Verify a password against a stored PBKDF2-SHA256 hash."""
    try:
        algorithm, iterations_text, salt, encoded_digest = stored_hash.split("$", 3)
        iterations = int(iterations_text)
    except ValueError:
        return False

    if algorithm != _PASSWORD_HASH_ALGORITHM:
        return False

    digest = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt.encode("utf-8"),
        iterations,
    )
    expected = base64.urlsafe_b64encode(digest).decode("ascii").rstrip("=")
    return hmac.compare_digest(expected, encoded_digest)


def create_access_token(subject: str) -> tuple[str, int]:
    """Create a signed JWT access token and return it with its lifetime in seconds."""
    settings = get_settings()
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=settings.access_token_expire_minutes)
    expires_in = settings.access_token_expire_minutes * 60
    payload = {
        "sub": subject,
        "type": _JWT_TYPE_ACCESS,
        "iat": int(now.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    return _encode_jwt(payload), expires_in


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT access token."""
    try:
        header_segment, payload_segment, signature_segment = token.split(".")
    except ValueError as exc:
        raise InvalidTokenError("Malformed token") from exc

    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    expected_signature = _sign(signing_input)
    actual_signature = _b64url_decode(signature_segment)
    if not hmac.compare_digest(expected_signature, actual_signature):
        raise InvalidTokenError("Invalid token signature")

    try:
        header = json.loads(_b64url_decode(header_segment))
        payload = json.loads(_b64url_decode(payload_segment))
    except (json.JSONDecodeError, UnicodeDecodeError) as exc:
        raise InvalidTokenError("Invalid token payload") from exc

    settings = get_settings()
    if header.get("alg") != settings.jwt_algorithm or header.get("typ") != "JWT":
        raise InvalidTokenError("Unsupported token header")
    if payload.get("type") != _JWT_TYPE_ACCESS:
        raise InvalidTokenError("Unsupported token type")
    if not isinstance(payload.get("sub"), str):
        raise InvalidTokenError("Missing token subject")
    if not isinstance(payload.get("exp"), int):
        raise InvalidTokenError("Missing token expiration")
    if payload["exp"] <= int(datetime.now(UTC).timestamp()):
        raise InvalidTokenError("Expired token")

    return payload


def create_refresh_token() -> str:
    """Create an opaque refresh token."""
    return secrets.token_urlsafe(64)


def hash_refresh_token(token: str) -> str:
    """Hash a refresh token before storing it."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _encode_jwt(payload: dict[str, Any]) -> str:
    settings = get_settings()
    header = {"alg": settings.jwt_algorithm, "typ": "JWT"}
    header_segment = _b64url_encode(json.dumps(header, separators=(",", ":")).encode("utf-8"))
    payload_segment = _b64url_encode(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    signing_input = f"{header_segment}.{payload_segment}".encode("ascii")
    signature_segment = _b64url_encode(_sign(signing_input))
    return f"{header_segment}.{payload_segment}.{signature_segment}"


def _sign(signing_input: bytes) -> bytes:
    secret_key = _get_secret_key()
    return hmac.new(secret_key, signing_input, hashlib.sha256).digest()


def _get_secret_key() -> bytes:
    secret_key = get_settings().jwt_secret_key
    if not secret_key:
        raise AuthConfigurationError("DASH_JWT_SECRET_KEY must be configured")
    return secret_key.encode("utf-8")


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("ascii").rstrip("=")


def _b64url_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(f"{value}{padding}")
