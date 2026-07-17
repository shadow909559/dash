"""Embedding abstraction for RAG.

Provides a simple provider-agnostic interface. Returns None when no provider
is configured, allowing the service layer to gracefully fall back to text search.
"""

from __future__ import annotations

from typing import List
import json

import httpx

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


async def create_embedding(text: str) -> list[float] | None:
    """Create an embedding vector for the given text using configured provider.

    Returns list[float] or None if embeddings are not available.
    """
    settings = get_settings()
    provider = (settings.ai_provider or "").lower()

    if not text:
        return None

    # Prefer OpenAI if API key present
    if provider == "openai" and settings.openai_api_key:
        base = settings.openai_base_url.rstrip("/")
        url = f"{base}/embeddings"
        model = settings.ai_model or "text-embedding-3-small"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": text, "model": model}
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                # OpenAI embeddings response structure
                emb = (data.get("data") or [{}])[0].get("embedding")
                if isinstance(emb, list):
                    return [float(x) for x in emb]
        except Exception as exc:  # pragma: no cover - network/IO
            logger.warning("Embedding request failed: %s", exc)
            return None

    # Ollama or other providers could be implemented here later.
    if provider == "ollama":
        # Ollama embedding API is provider-specific; placeholder for future.
        logger.debug("Ollama embedding provider selected but not implemented")
        return None

    # No provider configured
    logger.debug("No embedding provider configured (ai_provider=%r)", provider)
    return None
