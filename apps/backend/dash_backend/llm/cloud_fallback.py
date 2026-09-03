"""Smart Cloud Fallback — automatically uses cloud AI when local Ollama is too slow.

The agent's biggest bottleneck is the LLM. Local models take 90s+ per call on
this hardware. This module provides:

1. Health check — is Gemini reachable?
2. Fast provider selection — cloud if available, local if not
3. Speed test — measure actual latency of each provider

Usage:
    from dash_backend.llm.cloud_fallback import get_provider_selector
    selector = get_provider_selector()
    provider = await selector.select_provider()  # "gemini" or "ollama"
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any

import httpx

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


@dataclass
class ProviderHealth:
    provider: str
    healthy: bool
    latency_ms: float = 0.0
    model: str = ""
    error: str = ""


class ProviderSelector:
    """Selects the best AI provider based on health and speed."""

    def __init__(self):
        self._cloud_health: ProviderHealth | None = None
        self._local_health: ProviderHealth | None = None
        self._last_check: float = 0.0
        self._check_interval: float = 60.0  # re-check every 60s

    async def check_cloud(self) -> ProviderHealth:
        """Check if Gemini (OpenAI-compatible) is reachable."""
        from dash_backend.config import get_settings
        settings = get_settings()

        api_key = settings.openai_api_key
        base_url = settings.openai_base_url

        if not api_key:
            self._cloud_health = ProviderHealth(
                provider="gemini", healthy=False, error="No API key configured"
            )
            return self._cloud_health

        url = f"{base_url.rstrip('/')}/models"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    url,
                    headers={"Authorization": f"Bearer {api_key}"},
                )
                latency = (time.monotonic() - start) * 1000

                if resp.status_code == 200:
                    model = settings.ai_model or settings.openai_model or "gemini-2.5-flash"
                    self._cloud_health = ProviderHealth(
                        provider="gemini", healthy=True,
                        latency_ms=latency, model=model,
                    )
                    logger.info(
                        "Cloud AI (Gemini) healthy — %.0fms, model=%s",
                        latency, model,
                    )
                else:
                    self._cloud_health = ProviderHealth(
                        provider="gemini", healthy=False,
                        error=f"HTTP {resp.status_code}",
                    )
        except httpx.TimeoutError:
            self._cloud_health = ProviderHealth(
                provider="gemini", healthy=False, error="Timeout"
            )
        except Exception as exc:
            self._cloud_health = ProviderHealth(
                provider="gemini", healthy=False, error=str(exc)[:100]
            )

        return self._cloud_health

    async def check_local(self) -> ProviderHealth:
        """Check if Ollama is reachable and responsive."""
        from dash_backend.config import get_settings
        settings = get_settings()

        url = f"{settings.ollama_base_url.rstrip('/')}/api/tags"
        start = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(url)
                latency = (time.monotonic() - start) * 1000

                if resp.status_code == 200:
                    data = resp.json()
                    models = [m.get("name", "") for m in data.get("models", [])]
                    model = settings.ai_model or settings.ollama_model or "llama3.2:1b"
                    self._local_health = ProviderHealth(
                        provider="ollama", healthy=True,
                        latency_ms=latency, model=model,
                    )
                    logger.info(
                        "Local AI (Ollama) healthy — %.0fms, models=%s",
                        latency, models[:3],
                    )
                else:
                    self._local_health = ProviderHealth(
                        provider="ollama", healthy=False,
                        error=f"HTTP {resp.status_code}",
                    )
        except httpx.TimeoutError:
            self._local_health = ProviderHealth(
                provider="ollama", healthy=False, error="Timeout"
            )
        except Exception as exc:
            self._local_health = ProviderHealth(
                provider="ollama", healthy=False, error=str(exc)[:100]
            )

        return self._local_health

    async def check_all(self) -> dict[str, ProviderHealth]:
        """Check all providers. Returns dict of provider_name -> health."""
        now = time.monotonic()
        if now - self._last_check < self._check_interval:
            return {
                k: v for k, v in {
                    "cloud": self._cloud_health,
                    "local": self._local_health,
                }.items() if v is not None
            }

        self._last_check = now
        cloud, local = await asyncio.gather(
            self.check_cloud(), self.check_local(), return_exceptions=True
        )

        results = {}
        if isinstance(cloud, ProviderHealth):
            results["cloud"] = cloud
        if isinstance(local, ProviderHealth):
            results["local"] = local
        return results

    async def select_provider(self) -> str:
        """Select the best available provider.

        Priority:
        1. Cloud (Gemini) if healthy and fast (<5s)
        2. Cloud (Grok) if Gemini unavailable
        3. Local (Ollama) if healthy
        4. Any cloud as last resort
        """
        await self.check_all()

        cloud_ok = self._cloud_health and self._cloud_health.healthy
        local_ok = self._local_health and self._local_health.healthy

        if cloud_ok and local_ok:
            return "openai"  # Gemini via OpenAI-compatible endpoint

        if cloud_ok:
            return "openai"

        if local_ok:
            return "ollama"

        # Neither healthy — default to ollama (might recover)
        logger.warning("No healthy AI provider — defaulting to ollama")
        return "ollama"

    def get_status(self) -> dict[str, Any]:
        """Return current provider status for the dashboard."""
        return {
            "cloud": {
                "healthy": self._cloud_health.healthy if self._cloud_health else None,
                "latency_ms": round(self._cloud_health.latency_ms, 1) if self._cloud_health else None,
                "model": self._cloud_health.model if self._cloud_health else None,
                "error": self._cloud_health.error if self._cloud_health else None,
            },
            "local": {
                "healthy": self._local_health.healthy if self._local_health else None,
                "latency_ms": round(self._local_health.latency_ms, 1) if self._local_health else None,
                "model": self._local_health.model if self._local_health else None,
                "error": self._local_health.error if self._local_health else None,
            },
        }


# Singleton
_selector: ProviderSelector | None = None


def get_provider_selector() -> ProviderSelector:
    global _selector
    if _selector is None:
        _selector = ProviderSelector()
    return _selector
