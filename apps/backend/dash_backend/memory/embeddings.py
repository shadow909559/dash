"""Memory embedding service with caching.

Provides embedding generation for memory content with an in-memory cache
to avoid redundant API calls for identical or near-identical content.
"""

from __future__ import annotations

import hashlib
import time
from typing import Any

from dash_backend.logging_config import get_logger
from dash_backend.rag.embeddings import create_embedding

logger = get_logger(__name__)

# Simple in-memory embedding cache
# Key: md5 hash of content text
# Value: (embedding list, timestamp)
_embedding_cache: dict[str, tuple[list[float], float]] = {}
_CACHE_TTL_SECONDS = 3600  # 1 hour
_MAX_CACHE_SIZE = 1000


def _content_hash(text: str) -> str:
    return hashlib.md5(text.encode("utf-8")).hexdigest()


def _prune_cache() -> None:
    """Remove expired entries from the cache."""
    now = time.time()
    expired_keys = [
        k for k, (_, ts) in _embedding_cache.items()
        if now - ts > _CACHE_TTL_SECONDS
    ]
    for k in expired_keys:
        del _embedding_cache[k]

    # If still too large, remove oldest entries
    if len(_embedding_cache) > _MAX_CACHE_SIZE:
        sorted_items = sorted(
            _embedding_cache.items(), key=lambda x: x[1][1]
        )
        for k, _ in sorted_items[: len(sorted_items) - _MAX_CACHE_SIZE]:
            del _embedding_cache[k]


async def get_embedding(text: str) -> list[float] | None:
    """Get embedding for text, using cache if available.

    Returns None if no embedding provider is configured.
    """
    if not text:
        return None

    content_key = _content_hash(text)

    # Check cache
    cached = _embedding_cache.get(content_key)
    if cached is not None:
        emb, ts = cached
        if time.time() - ts <= _CACHE_TTL_SECONDS:
            logger.debug("Embedding cache hit for content hash %s", content_key[:8])
            return emb
        # Expired - remove and regenerate
        del _embedding_cache[content_key]

    # Generate embedding
    emb = await create_embedding(text)
    if emb is not None:
        # Store in cache
        _embedding_cache[content_key] = (emb, time.time())
        _prune_cache()
        logger.debug("Embedding cached for content hash %s", content_key[:8])

    return emb


def clear_embedding_cache() -> int:
    """Clear the embedding cache. Returns number of entries cleared."""
    global _embedding_cache
    count = len(_embedding_cache)
    _embedding_cache = {}
    logger.info("Cleared %d entries from embedding cache", count)
    return count


def get_cache_stats() -> dict[str, Any]:
    """Get cache statistics."""
    return {
        "size": len(_embedding_cache),
        "max_size": _MAX_CACHE_SIZE,
        "ttl_seconds": _CACHE_TTL_SECONDS,
    }