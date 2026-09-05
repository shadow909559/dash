"""Optional, backend-only Supabase adapter.

Phase 1 intentionally performs no data migration or data access.  It owns
configuration validation, SDK construction, and a bounded connectivity check
so an unavailable cloud service can never prevent DASH Core from operating.
"""

from __future__ import annotations

import asyncio
from functools import lru_cache
from time import perf_counter
from typing import Any
from urllib.parse import urlparse
import uuid

import httpx

from dash_backend.config import Settings, get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_CONNECT_TIMEOUT_SECONDS = 5.0


class SupabaseService:
    """Own DASH's optional Supabase SDK client and health checks."""

    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._client: Any | None = None
        self._sync_client: Any | None = None

    def _configuration_error(self) -> str | None:
        if not self._settings.supabase_enabled:
            return None
        if not self._settings.supabase_url:
            return "SUPABASE_URL is required when Supabase is enabled"
        if not self._settings.supabase_publishable_key:
            return "SUPABASE_PUBLISHABLE_KEY is required when Supabase is enabled"

        parsed = urlparse(self._settings.supabase_url)
        if parsed.scheme not in {"http", "https"} or not parsed.netloc:
            return "SUPABASE_URL must be an absolute HTTP(S) URL"
        return None

    def _get_client(self) -> Any:
        """Build the official SDK client only when the optional feature is used."""
        if self._client is None:
            error = self._configuration_error()
            if error:
                raise RuntimeError(error)
            from supabase import create_client

            self._client = create_client(
                self._settings.supabase_url,
                self._settings.supabase_publishable_key.get_secret_value(),
            )
        return self._client

    def sync_configuration_error(self) -> str | None:
        """Return a safe reason why the optional server-side worker cannot run."""
        if not self._settings.supabase_sync_enabled:
            return "Supabase sync is disabled"
        if not self._settings.supabase_enabled:
            return "SUPABASE_ENABLED must be true when sync is enabled"
        if not self._settings.supabase_service_role_key:
            return "SUPABASE_SERVICE_ROLE_KEY is required for server-side sync"
        try:
            uuid.UUID(self._settings.supabase_sync_owner_id or "")
        except (ValueError, TypeError, AttributeError):
            return "SUPABASE_SYNC_OWNER_ID must be a provisioned Supabase Auth UUID"
        return self._configuration_error()

    def get_sync_client(self) -> Any:
        """Return the server-only service-role client for the outbox worker."""
        if self._sync_client is None:
            error = self.sync_configuration_error()
            if error:
                raise RuntimeError(error)
            from supabase import create_client

            self._sync_client = create_client(
                self._settings.supabase_url,
                self._settings.supabase_service_role_key.get_secret_value(),
            )
        return self._sync_client

    async def check_connectivity(self) -> dict[str, Any]:
        """Return a safe, bounded Supabase status without raising to callers."""
        started = perf_counter()
        if not self._settings.supabase_enabled:
            return self._result(True, "disabled", "Supabase is disabled", started)

        configuration_error = self._configuration_error()
        if configuration_error:
            logger.warning("Supabase configuration is invalid: %s", configuration_error)
            return self._result(False, "configuration_error", configuration_error, started)

        try:
            # Instantiate the official client as part of the adapter contract.
            # The settings endpoint itself is deliberately used for Phase 1: it
            # checks reachability and the publishable key without querying or
            # modifying any DASH/Supabase data.
            await asyncio.to_thread(self._get_client)
            url = f"{self._settings.supabase_url.rstrip('/')}/auth/v1/settings"
            key = self._settings.supabase_publishable_key.get_secret_value()
            timeout = httpx.Timeout(_CONNECT_TIMEOUT_SECONDS)
            async with httpx.AsyncClient(timeout=timeout) as client:
                response = await client.get(url, headers={"apikey": key})
        except httpx.TimeoutException:
            logger.warning("Supabase connectivity check timed out")
            return self._result(False, "timeout", "Supabase request timed out", started)
        except (httpx.HTTPError, OSError) as exc:
            logger.warning("Supabase connectivity check failed: %s", type(exc).__name__)
            return self._result(False, "unavailable", "Supabase is unavailable", started)
        except Exception as exc:
            # SDK configuration/initialisation errors must remain non-fatal.
            logger.warning("Supabase client could not be initialized: %s", type(exc).__name__)
            return self._result(False, "initialization_error", "Supabase client initialization failed", started)

        if 200 <= response.status_code < 300:
            return self._result(True, "healthy", "Supabase is reachable", started)
        if response.status_code in {401, 403}:
            return self._result(False, "authentication_error", "Supabase rejected the publishable key", started)
        logger.warning("Supabase settings endpoint returned HTTP %s", response.status_code)
        return self._result(False, "unavailable", "Supabase returned an unexpected response", started)

    async def health_monitor_check(self) -> tuple[bool, dict[str, Any]]:
        """Adapt the status to DASH's system health-monitor contract."""
        status = await self.check_connectivity()
        return bool(status["healthy"]), status

    def _result(self, healthy: bool, status: str, message: str, started: float) -> dict[str, Any]:
        return {
            "enabled": self._settings.supabase_enabled,
            "healthy": healthy,
            "status": status,
            "message": message,
            "latency_ms": round((perf_counter() - started) * 1000, 2),
        }


@lru_cache
def get_supabase_service() -> SupabaseService:
    """Return the process-wide optional Supabase adapter."""
    return SupabaseService()
