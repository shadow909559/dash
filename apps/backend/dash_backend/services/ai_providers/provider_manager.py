"""ProviderManager - manages multiple AI providers with fallback and health checks."""

from __future__ import annotations

import asyncio
from typing import Any, AsyncIterator

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_providers.base import (
    AIProvider,
    CompletionRequest,
    CompletionResponse,
    ProviderConfig,
    ProviderHealth,
)

logger = get_logger(__name__)


class ProviderManager:
    """Manages AI providers with automatic fallback and health monitoring.

    Supports:
      - Registering multiple providers
      - Ordered fallback (primary -> secondary -> tertiary)
      - Health checks for all providers
      - Streaming and non-streaming completions
      - Request timeout enforcement
    """

    def __init__(self) -> None:
        self._providers: dict[str, AIProvider] = {}
        self._order: list[str] = []
        self._health_cache: dict[str, ProviderHealth] = {}
        self._lock = asyncio.Lock()

    def register(self, provider: AIProvider, primary: bool = False) -> None:
        """Register a provider. If primary=True, it becomes the first choice."""
        self._providers[provider.name] = provider
        if primary:
            self._order.insert(0, provider.name)
        elif provider.name not in self._order:
            self._order.append(provider.name)
        logger.info("Registered AI provider: %s (primary=%s)", provider.name, primary)

    def unregister(self, name: str) -> None:
        """Remove a provider."""
        self._providers.pop(name, None)
        self._order = [p for p in self._order if p != name]
        self._health_cache.pop(name, None)

    def get_provider(self, name: str) -> AIProvider | None:
        """Get a specific provider by name."""
        return self._providers.get(name)

    def get_primary_provider(self) -> AIProvider | None:
        """Get the primary (first) provider."""
        if not self._order:
            return None
        return self._providers.get(self._order[0])

    def list_providers(self) -> list[dict[str, Any]]:
        """List all registered providers with their status."""
        results = []
        for name in self._order:
            provider = self._providers.get(name)
            if provider is None:
                continue
            health = self._health_cache.get(name)
            results.append({
                "name": name,
                "model": provider.config.model,
                "enabled": provider.config.enabled,
                "healthy": health.healthy if health else None,
                "latency_ms": health.latency_ms if health else None,
                "error": health.error if health else None,
            })
        return results

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        """Send a completion request with automatic fallback."""
        last_error: Exception | None = None
        for name in self._order:
            provider = self._providers.get(name)
            if provider is None or not provider.config.enabled:
                continue
            try:
                response = await asyncio.wait_for(
                    provider.complete(request),
                    timeout=provider.config.timeout_seconds,
                )
                await self._update_health(name, True, 0.0)
                return response
            except Exception as exc:
                last_error = exc
                logger.warning("Provider %s failed: %s - trying next", name, exc)
                await self._update_health(name, False, 0.0, str(exc))
                continue
        raise last_error or RuntimeError("No providers available")

    async def complete_streaming(
        self, request: CompletionRequest
    ) -> AsyncIterator[str]:
        """Stream a completion with automatic fallback."""
        sent = False
        for name in self._order:
            if sent:
                break
            provider = self._providers.get(name)
            if provider is None or not provider.config.enabled:
                continue
            try:
                async for token in provider.complete_streaming(request):
                    yield token
                sent = True
                await self._update_health(name, True, 0.0)
            except Exception as exc:
                logger.warning("Provider %s streaming failed: %s - trying next", name, exc)
                await self._update_health(name, False, 0.0, str(exc))
        if not sent:
            raise RuntimeError("No providers available for streaming")

    async def check_all_health(self) -> dict[str, ProviderHealth]:
        """Check health of all providers."""
        results = {}
        for name, provider in self._providers.items():
            try:
                health = await asyncio.wait_for(
                    provider.check_health(), timeout=10.0
                )
                results[name] = health
            except Exception as exc:
                results[name] = ProviderHealth(
                    healthy=False, error=str(exc)
                )
            self._health_cache[name] = results[name]
        return results

    async def _update_health(
        self, name: str, healthy: bool, latency_ms: float, error: str | None = None
    ) -> None:
        async with self._lock:
            from datetime import datetime
            self._health_cache[name] = ProviderHealth(
                healthy=healthy,
                latency_ms=latency_ms,
                last_check=datetime.utcnow(),
                error=error,
                model_loaded=healthy,
            )


# Singleton
_manager: ProviderManager | None = None


def get_provider_manager() -> ProviderManager:
    global _manager
    if _manager is None:
        _manager = ProviderManager()
    return _manager
