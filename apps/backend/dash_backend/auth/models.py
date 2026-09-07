"""Compatibility exports for authentication models."""

from dash_backend.db.models.user import User
from dash_backend.db.models.refresh_tokens import RefreshToken


__all__ = [
    "User",
    "RefreshToken",
]