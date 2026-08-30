"""Tests for the optional Supabase Phase 1 adapter."""

from __future__ import annotations

import httpx
import pytest

from dash_backend.config import Settings
from dash_backend.services.supabase import SupabaseService


def _settings(**overrides: object) -> Settings:
    defaults: dict[str, object] = {
        "supabase_enabled": True,
        "supabase_url": "https://example.supabase.co",
        "supabase_publishable_key": "test-publishable-key",
    }
    defaults.update(overrides)
    return Settings(**defaults)


@pytest.mark.asyncio
async def test_disabled_supabase_is_healthy_without_network() -> None:
    result = await SupabaseService(_settings(supabase_enabled=False)).check_connectivity()
    assert result["healthy"] is True
    assert result["status"] == "disabled"


@pytest.mark.asyncio
async def test_missing_credentials_are_reported_without_raising() -> None:
    result = await SupabaseService(_settings(supabase_publishable_key=None)).check_connectivity()
    assert result["healthy"] is False
    assert result["status"] == "configuration_error"


@pytest.mark.asyncio
async def test_invalid_url_is_reported_without_raising() -> None:
    result = await SupabaseService(_settings(supabase_url="not-a-url")).check_connectivity()
    assert result["healthy"] is False
    assert result["status"] == "configuration_error"


@pytest.mark.asyncio
async def test_timeout_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SupabaseService(_settings())
    monkeypatch.setattr(service, "_get_client", lambda: object())

    class TimeoutClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> None:
            raise httpx.ReadTimeout("timed out")

    monkeypatch.setattr("dash_backend.services.supabase.httpx.AsyncClient", lambda **_: TimeoutClient())
    result = await service.check_connectivity()
    assert result["healthy"] is False
    assert result["status"] == "timeout"


@pytest.mark.asyncio
async def test_connection_failure_is_non_fatal(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SupabaseService(_settings())
    monkeypatch.setattr(service, "_get_client", lambda: object())

    class FailingClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> None:
            raise httpx.ConnectError("connection refused")

    monkeypatch.setattr("dash_backend.services.supabase.httpx.AsyncClient", lambda **_: FailingClient())
    result = await service.check_connectivity()
    assert result["healthy"] is False
    assert result["status"] == "unavailable"


@pytest.mark.asyncio
async def test_successful_connectivity_is_reported(monkeypatch: pytest.MonkeyPatch) -> None:
    service = SupabaseService(_settings())
    monkeypatch.setattr(service, "_get_client", lambda: object())

    class HealthyClient:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def get(self, *args: object, **kwargs: object) -> httpx.Response:
            return httpx.Response(200)

    monkeypatch.setattr("dash_backend.services.supabase.httpx.AsyncClient", lambda **_: HealthyClient())
    result = await service.check_connectivity()
    assert result["healthy"] is True
    assert result["status"] == "healthy"
