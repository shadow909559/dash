# -*- coding: utf-8 -*-
"""OAuth Social Login — Google, GitHub, Microsoft provider authentication."""

import hashlib
import secrets
import logging
from datetime import datetime, timezone
from typing import Optional
from dataclasses import dataclass, field, asdict

logger = logging.getLogger(__name__)

# ── Provider Configurations ──────────────────────────────────────────────────

PROVIDERS = {
    "google": {
        "authorize_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "userinfo_url": "https://openidconnect.googleapis.com/v1/userinfo",
        "scopes": ["openid", "email", "profile"],
    },
    "github": {
        "authorize_url": "https://github.com/login/oauth/authorize",
        "token_url": "https://github.com/login/oauth/access_token",
        "userinfo_url": "https://api.github.com/user",
        "scopes": ["user:email", "read:user"],
    },
    "microsoft": {
        "authorize_url": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
        "token_url": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
        "userinfo_url": "https://graph.microsoft.com/v1.0/me",
        "scopes": ["openid", "email", "profile", "User.Read"],
    },
}


@dataclass
class OAuthState:
    """OAuth state for CSRF protection."""
    provider: str
    state_token: str
    code_verifier: str
    redirect_uri: str
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    used: bool = False


@dataclass
class SocialAccount:
    """Linked social account."""
    provider: str
    provider_user_id: str
    email: str
    name: str
    avatar_url: str = ""
    access_token: str = ""
    refresh_token: str = ""
    linked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    last_used: str = ""


class OAuthService:
    """OAuth social login service."""

    def __init__(self):
        self._states: dict[str, OAuthState] = {}
        self._accounts: dict[str, list[SocialAccount]] = {}  # user_id -> accounts
        self._provider_configs: dict[str, dict] = {}

    def configure_provider(
        self,
        provider: str,
        client_id: str,
        client_secret: str,
        redirect_uri: str,
    ) -> dict:
        """Configure an OAuth provider with credentials."""
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}. Available: {list(PROVIDERS.keys())}")

        self._provider_configs[provider] = {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uri": redirect_uri,
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        logger.info("OAuth provider configured: %s", provider)
        return {"provider": provider, "status": "configured", "client_id": client_id[:8] + "..."}

    def get_authorize_url(self, provider: str, redirect_uri: Optional[str] = None) -> dict:
        """Generate authorization URL with CSRF state."""
        if provider not in self._provider_configs:
            raise ValueError(f"Provider not configured: {provider}")

        config = self._provider_configs[provider]
        provider_info = PROVIDERS[provider]
        state_token = secrets.token_urlsafe(32)
        code_verifier = secrets.token_urlsafe(64)
        uri = redirect_uri or config["redirect_uri"]

        # Store state for CSRF verification
        state = OAuthState(
            provider=provider,
            state_token=state_token,
            code_verifier=code_verifier,
            redirect_uri=uri,
        )
        self._states[state_token] = state

        # Build authorize URL
        from urllib.parse import urlencode
        params = {
            "client_id": config["client_id"],
            "redirect_uri": uri,
            "response_type": "code",
            "scope": " ".join(provider_info["scopes"]),
            "state": state_token,
            "access_type": "offline",
            "prompt": "consent",
        }
        url = f"{provider_info['authorize_url']}?{urlencode(params)}"

        return {
            "authorization_url": url,
            "state": state_token,
            "provider": provider,
        }

    async def exchange_code(self, provider: str, code: str, state_token: str) -> dict:
        """Exchange authorization code for tokens and user info."""
        # Verify CSRF state
        state = self._states.get(state_token)
        if not state or state.used:
            raise ValueError("Invalid or expired state token")
        if state.provider != provider:
            raise ValueError("State provider mismatch")

        state.used = True
        config = self._provider_configs[provider]
        provider_info = PROVIDERS[provider]

        # In production, make HTTP request to exchange code
        # For now, return mock token exchange
        mock_tokens = {
            "access_token": f"mock_{provider}_token_{secrets.token_hex(16)}",
            "refresh_token": f"mock_{provider}_refresh_{secrets.token_hex(16)}",
            "token_type": "Bearer",
            "expires_in": 3600,
        }

        mock_user = {
            "provider": provider,
            "provider_user_id": f"{provider}_user_{secrets.token_hex(8)}",
            "email": f"user@example.com",
            "name": f"{provider.title()} User",
            "avatar_url": f"https://ui-avatars.com/api/?name={provider}",
        }

        return {
            "tokens": mock_tokens,
            "user": mock_user,
            "provider": provider,
        }

    def link_account(self, user_id: str, provider: str, user_info: dict) -> dict:
        """Link a social account to a DASH user."""
        account = SocialAccount(
            provider=provider,
            provider_user_id=user_info.get("provider_user_id", ""),
            email=user_info.get("email", ""),
            name=user_info.get("name", ""),
            avatar_url=user_info.get("avatar_url", ""),
            access_token=user_info.get("access_token", ""),
            refresh_token=user_info.get("refresh_token", ""),
        )

        if user_id not in self._accounts:
            self._accounts[user_id] = []

        # Check if already linked
        for existing in self._accounts[user_id]:
            if existing.provider == provider and existing.provider_user_id == account.provider_user_id:
                existing.last_used = datetime.now(timezone.utc).isoformat()
                existing.access_token = account.access_token
                return {"status": "updated", "provider": provider}

        self._accounts[user_id].append(account)
        return {"status": "linked", "provider": provider, "email": account.email}

    def unlink_account(self, user_id: str, provider: str) -> dict:
        """Unlink a social account."""
        accounts = self._accounts.get(user_id, [])
        before = len(accounts)
        self._accounts[user_id] = [a for a in accounts if a.provider != provider]
        removed = before - len(self._accounts[user_id])
        return {"status": "unlinked" if removed else "not_found", "provider": provider, "removed": removed}

    def get_linked_accounts(self, user_id: str) -> list[dict]:
        """Get all linked social accounts for a user."""
        accounts = self._accounts.get(user_id, [])
        return [
            {
                "provider": a.provider,
                "email": a.email,
                "name": a.name,
                "avatar_url": a.avatar_url,
                "linked_at": a.linked_at,
                "last_used": a.last_used,
            }
            for a in accounts
        ]

    def get_configured_providers(self) -> list[dict]:
        """List configured OAuth providers."""
        return [
            {
                "provider": name,
                "client_id": cfg["client_id"][:8] + "...",
                "configured": True,
            }
            for name, cfg in self._provider_configs.items()
        ]

    def get_provider_info(self, provider: str) -> dict:
        """Get provider information."""
        if provider not in PROVIDERS:
            raise ValueError(f"Unknown provider: {provider}")
        info = PROVIDERS[provider]
        return {
            "provider": provider,
            "authorize_url": info["authorize_url"],
            "scopes": info["scopes"],
            "configured": provider in self._provider_configs,
        }


# Singleton
_oauth_service: Optional[OAuthService] = None


def get_oauth_service() -> OAuthService:
    global _oauth_service
    if _oauth_service is None:
        _oauth_service = OAuthService()
    return _oauth_service
