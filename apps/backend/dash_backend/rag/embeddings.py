"""Embedding abstraction for RAG.

Provides a simple provider-agnostic interface. Returns None when no provider
is configured, allowing the service layer to gracefully fall back to text search.

Includes caching to avoid redundant embedding generation for identical text.
"""

from __future__ import annotations

from typing import List

import httpx

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger
from dash_backend.cache.simple_cache import get_cache

logger = get_logger(__name__)


async def create_embedding(text: str) -> list[float] | None:
    """Create an embedding vector for the given text using configured provider.

    Returns list[float] or None if embeddings are not available.
    
    Results are cached for 24 hours to avoid redundant API calls.
    """
    settings = get_settings()
    provider = (settings.ai_provider or "").lower()

    if not text:
        return None
    
    # Check cache first
    cache = get_cache()
    cache_key = f"embedding_{text[:500]}"  # Use first 500 chars as cache key
    cached_embedding = cache.get(cache_key)
    if cached_embedding is not None:
        logger.debug("Using cached embedding for text: %s", text[:50])
        return cached_embedding

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
                    embedding = [float(x) for x in emb]
                    # Cache the result for 24 hours
                    cache.set(cache_key, embedding, ttl=86400.0)
                    return embedding
        except Exception as exc:  # pragma: no cover - network/IO
            logger.warning("Embedding request failed: %s", exc)
            return None

    # Ollama embeddings via the native API.
    if provider == "ollama":
        return await _ollama_embedding(text)

    # No provider configured
    logger.debug("No embedding provider configured (ai_provider=%r)", provider)
    return None


async def _ollama_embed_batch_api(
    client: "httpx.AsyncClient", base: str, model: str, texts: List[str]
) -> list[list[float]] | None:
    """Embed texts via Ollama's /api/embed (batch) endpoint.

    Returns None when the endpoint is unavailable so callers can fall back
    to the legacy per-text /api/embeddings endpoint.
    """
    try:
        resp = await client.post(
            f"{base}/api/embed", json={"model": model, "input": texts}
        )
        if resp.status_code == 404:
            return None
        resp.raise_for_status()
        data = resp.json()
        embs = data.get("embeddings")
        if isinstance(embs, list) and len(embs) == len(texts):
            return [[float(x) for x in e] for e in embs]
        return None
    except httpx.HTTPStatusError as exc:
        if exc.response.status_code == 404:
            return None
        raise


async def _ollama_embedding(text: str) -> list[float] | None:
    """Create an embedding via Ollama, trying batch then legacy endpoints."""
    settings = get_settings()
    base = settings.ollama_base_url.rstrip("/")
    model = settings.ollama_embedding_model or "nomic-embed-text"
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            result = await _ollama_embed_batch_api(client, base, model, [text])
            if result is not None:
                cache = get_cache()
                cache.set(f"embedding_{text[:500]}", result[0], ttl=86400.0)
                return result[0]

            # Legacy fallback: one text per request.
            resp = await client.post(
                f"{base}/api/embeddings", json={"model": model, "prompt": text}
            )
            resp.raise_for_status()
            emb = resp.json().get("embedding")
            if isinstance(emb, list):
                embedding = [float(x) for x in emb]
                get_cache().set(f"embedding_{text[:500]}", embedding, ttl=86400.0)
                return embedding
            logger.warning("Ollama embedding response missing 'embedding' field")
            return None
    except Exception as exc:  # pragma: no cover - network/IO
        logger.warning("Ollama embedding request failed: %s", exc)
        return None


async def create_embeddings_batch(texts: List[str]) -> List[list[float] | None]:
    """Create embedding vectors for multiple texts in a single batch request.
    
    This is more efficient than calling create_embedding multiple times
    as it reduces network overhead and allows the provider to optimize.
    
    Returns a list of embeddings (or None for each text if embedding failed).
    Results are cached individually for 24 hours.
    """
    settings = get_settings()
    provider = (settings.ai_provider or "").lower()
    
    if not texts:
        return []
    
    # Check cache for each text
    cache = get_cache()
    results = []
    uncached_texts = []
    uncached_indices = []
    
    for i, text in enumerate(texts):
        if not text:
            results.append(None)
            continue
        
        cache_key = f"embedding_{text[:500]}"
        cached_embedding = cache.get(cache_key)
        if cached_embedding is not None:
            results.append(cached_embedding)
        else:
            results.append(None)
            uncached_texts.append(text)
            uncached_indices.append(i)
    
    # If all were cached, return early
    if not uncached_texts:
        return results
    
    # Batch request for uncached texts
    if provider == "openai" and settings.openai_api_key:
        base = settings.openai_base_url.rstrip("/")
        url = f"{base}/embeddings"
        model = settings.ai_model or "text-embedding-3-small"
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        payload = {"input": uncached_texts, "model": model}
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                resp = await client.post(url, json=payload, headers=headers)
                resp.raise_for_status()
                data = resp.json()
                
                # OpenAI batch embeddings response structure
                embeddings_data = data.get("data", [])
                
                # Map results back to original indices
                for idx, emb_data in zip(uncached_indices, embeddings_data):
                    emb = emb_data.get("embedding")
                    if isinstance(emb, list):
                        embedding = [float(x) for x in emb]
                        # Cache the result
                        cache_key = f"embedding_{uncached_texts[uncached_indices.index(idx)][:500]}"
                        cache.set(cache_key, embedding, ttl=86400.0)
                        results[idx] = embedding
                    else:
                        results[idx] = None
                        
        except Exception as exc:
            logger.warning("Batch embedding request failed: %s", exc)
            # Fill uncached results with None
            for idx in uncached_indices:
                results[idx] = None

    # Ollama embeddings via the native API.
    elif provider == "ollama":
        settings_ = get_settings()
        base = settings_.ollama_base_url.rstrip("/")
        model = settings_.ollama_embedding_model or "nomic-embed-text"
        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                embs = await _ollama_embed_batch_api(client, base, model, uncached_texts)
                if embs is None:
                    # Legacy fallback: sequential per-text requests.
                    embs = []
                    for text in uncached_texts:
                        resp = await client.post(
                            f"{base}/api/embeddings",
                            json={"model": model, "prompt": text},
                        )
                        resp.raise_for_status()
                        emb = resp.json().get("embedding")
                        embs.append([float(x) for x in emb] if isinstance(emb, list) else None)
                for idx, emb in zip(uncached_indices, embs):
                    if emb is not None:
                        cache.set(f"embedding_{uncached_texts[uncached_indices.index(idx)][:500]}", emb, ttl=86400.0)
                        results[idx] = emb
        except Exception as exc:
            logger.warning("Batch embedding request failed: %s", exc)
            for idx in uncached_indices:
                if results[idx] is None:
                    results[idx] = None

    return results
