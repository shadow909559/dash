"""Grok (xAI) AI Provider — OpenAI-compatible API at api.x.ai."""

from __future__ import annotations

import httpx

from dash_backend.logging_config import get_logger
from dash_backend.services.ai_providers.base import AIProvider, ProviderHealth

logger = get_logger(__name__)


class GrokProvider(AIProvider):
    """xAI Grok provider — uses OpenAI-compatible API."""

    name = "grok"

    def __init__(
        self,
        api_key: str,
        model: str = "grok-3-mini",
        base_url: str = "https://api.x.ai/v1",
    ):
        self._api_key = api_key
        self._model = model
        self._base_url = base_url.rstrip("/")

    @property
    def model(self) -> str:
        return self._model

    async def health_check(self) -> ProviderHealth:
        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(
                    f"{self._base_url}/models",
                    headers={"Authorization": f"Bearer {self._api_key}"},
                )
                if resp.status_code == 200:
                    return ProviderHealth(healthy=True, model=self._model)
                return ProviderHealth(
                    healthy=False, error=f"HTTP {resp.status_code}"
                )
        except Exception as exc:
            return ProviderHealth(healthy=False, error=str(exc)[:100])

    async def complete(
        self,
        messages: list[dict],
        model: str | None = None,
        **kwargs,
    ) -> str:
        url = f"{self._base_url}/chat/completions"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model or self._model,
            "messages": messages,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()

        choice = data.get("choices", [{}])[0]
        return choice.get("message", {}).get("content", "")
