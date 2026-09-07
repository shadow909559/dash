"""Cache Manager - Multi-tier caching for DASH AI OS.

Provides:
- In-memory cache (default, fast)
- Redis-backed cache (distributed)
- Multi-tier caching (memory + Redis)
- TTL-based expiration
- LRU eviction
- Cache statistics and monitoring
- Namespace support for isolation
- Bulk operations
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
import uuid
from collections import OrderedDict
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class CacheTier(Enum):
    """Cache tier levels."""
    MEMORY = "memory"
    REDIS = "redis"
    HYBRID = "hybrid"


class CacheStats:
    """Cache statistics tracker."""
    
    def __init__(self):
        self.hits: int = 0
        self.misses: int = 0
        self.sets: int = 0
        self.deletes: int = 0
        self.evictions: int = 0
        self.size_bytes: int = 0
        self.total_items: int = 0
    
    def hit_rate(self) -> float:
        """Get cache hit rate (0.0 to 1.0)."""
        total = self.hits + self.misses
        if total == 0:
            return 0.0
        return self.hits / total
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "hits": self.hits,
            "misses": self.misses,
            "hit_rate": self.hit_rate(),
            "sets": self.sets,
            "deletes": self.deletes,
            "evictions": self.evictions,
            "size_bytes": self.size_bytes,
            "total_items": self.total_items,
        }


@dataclass
class CacheEntry:
    """A cached entry with metadata.
    
    Attributes:
        key: Cache key
        value: Cached value
        ttl: Time-to-live in seconds
        created_at: When the entry was created
        expires_at: When the entry expires
        access_count: Number of times accessed
        size_bytes: Approximate size in bytes
    """
    key: str = ""
    value: Any = None
    ttl: float = 0.0  # 0 = no expiry
    created_at: float = 0.0
    expires_at: float = 0.0
    access_count: int = 0
    size_bytes: int = 0
    
    def __post_init__(self):
        if not self.created_at:
            self.created_at = time.time()
        if not self.expires_at and self.ttl > 0:
            self.expires_at = self.created_at + self.ttl
    
    def is_expired(self) -> bool:
        """Check if the entry has expired.
        
        Returns:
            True if expired
        """
        if self.expires_at <= 0:
            return False
        return time.time() > self.expires_at
    
    def estimated_size(self) -> int:
        """Estimate the size of this cache entry in bytes.
        
        Returns:
            Size in bytes
        """
        if isinstance(self.value, str):
            return len(self.value.encode('utf-8'))
        if isinstance(self.value, bytes):
            return len(self.value)
        if isinstance(self.value, dict) or isinstance(self.value, list):
            return len(json.dumps(self.value, default=str).encode('utf-8'))
        return 128  # Default for small objects


class MemoryCache:
    """In-memory cache with LRU eviction.
    
    Features:
    - TTL-based expiration
    - LRU eviction when max size reached
    - Namespace support
    - Cache statistics
    """
    
    def __init__(self, max_size: int = 10000, max_memory_mb: int = 512):
        self._max_size = max_size
        self._max_memory_bytes = max_memory_mb * 1024 * 1024
        
        self._entries: OrderedDict[str, CacheEntry] = OrderedDict()
        self._stats = CacheStats()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            
        Returns:
            Cached value or None
        """
        entry = self._entries.get(key)
        if entry is None:
            self._stats.misses += 1
            return None
        
        if entry.is_expired():
            self._entries.pop(key, None)
            self._stats.misses += 1
            return None
        
        # Move to end (LRU)
        self._entries.move_to_end(key)
        entry.access_count += 1
        self._stats.hits += 1
        
        return entry.value
    
    async def set(self, key: str, value: Any, ttl: float = 0.0) -> None:
        """Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
        """
        entry = CacheEntry(
            key=key,
            value=value,
            ttl=ttl,
        )
        entry.size_bytes = entry.estimated_size()
        
        # Check memory limit
        if self._stats.size_bytes + entry.size_bytes > self._max_memory_bytes:
            await self._evict_lru()
        
        # Check item count limit
        if len(self._entries) >= self._max_size:
            await self._evict_lru()
        
        self._entries[key] = entry
        self._stats.sets += 1
        self._stats.size_bytes += entry.size_bytes
        self._stats.total_items = len(self._entries)
    
    async def delete(self, key: str) -> bool:
        """Delete a key from the cache.
        
        Args:
            key: Key to delete
            
        Returns:
            True if deleted
        """
        entry = self._entries.pop(key, None)
        if entry:
            self._stats.deletes += 1
            self._stats.size_bytes -= entry.size_bytes
            self._stats.total_items = len(self._entries)
            return True
        return False
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists and is not expired.
        
        Args:
            key: Key to check
            
        Returns:
            True if exists
        """
        entry = self._entries.get(key)
        if entry is None:
            return False
        if entry.is_expired():
            self._entries.pop(key, None)
            return False
        return True
    
    async def clear(self, namespace: Optional[str] = None) -> int:
        """Clear cache entries.
        
        Args:
            namespace: Optional namespace to clear
            
        Returns:
            Number of entries cleared
        """
        if namespace:
            count = 0
            for key in list(self._entries.keys()):
                if key.startswith(f"{namespace}:"):
                    entry = self._entries.pop(key)
                    self._stats.size_bytes -= entry.size_bytes
                    count += 1
            self._stats.total_items = len(self._entries)
            return count
        
        count = len(self._entries)
        self._entries.clear()
        self._stats = CacheStats()
        return count
    
    async def get_many(self, keys: List[str]) -> Dict[str, Any]:
        """Get multiple values at once.
        
        Args:
            keys: List of keys
            
        Returns:
            Dict of key -> value for found items
        """
        result = {}
        for key in keys:
            value = await self.get(key)
            if value is not None:
                result[key] = value
        return result
    
    async def set_many(self, items: Dict[str, Any], ttl: float = 0.0) -> None:
        """Set multiple values at once.
        
        Args:
            items: Dict of key -> value
            ttl: Time-to-live in seconds
        """
        for key, value in items.items():
            await self.set(key, value, ttl=ttl)
    
    async def _evict_lru(self) -> None:
        """Evict the least recently used entry."""
        if not self._entries:
            return
        
        try:
            key, entry = self._entries.popitem(last=False)  # Pop oldest
            self._stats.evictions += 1
            self._stats.size_bytes -= entry.size_bytes
            self._stats.total_items = len(self._entries)
            logger.debug("Evicted cache entry: %s", key)
        except (KeyError, AttributeError):
            pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            **self._stats.to_dict(),
            "max_size": self._max_size,
            "max_memory_mb": self._max_memory_bytes / (1024 * 1024),
            "current_items": len(self._entries),
            "current_memory_bytes": self._stats.size_bytes,
        }


class CacheManager:
    """Multi-tier cache manager.
    
    Provides:
    - Memory cache (primary, fast)
    - Redis cache (secondary, distributed)
    - Automatic tier fallback
    - Namespace support
    - Cache warming
    - Statistics aggregation
    """
    
    def __init__(self, default_ttl: float = 300.0):
        self._default_ttl = default_ttl
        self._memory_cache = MemoryCache()
        self._redis_enabled = False
        
        self._stats = CacheStats()
    
    async def start(self) -> None:
        """Start the cache manager. Initialization is in __init__."""
        pass
    
    async def stop(self) -> None:
        """Stop the cache manager. Currently a no-op."""
        pass
    
    async def enable_redis(self, redis_url: str) -> bool:
        """Enable Redis as a secondary cache tier.
        
        Args:
            redis_url: Redis connection URL
            
        Returns:
            True if Redis is available
        """
        try:
            import redis.asyncio as redis_asyncio
            
            self._redis = await redis_asyncio.from_url(
                redis_url,
                decode_responses=True,
            )
            await self._redis.ping()
            self._redis_enabled = True
            logger.info("Redis cache enabled: %s", redis_url)
            return True
            
        except ImportError:
            logger.warning("redis package not available")
            return False
        except Exception as exc:
            logger.warning("Failed to connect to Redis: %s", exc)
            return False
    
    async def get(self, key: str, tier: CacheTier = CacheTier.HYBRID) -> Optional[Any]:
        """Get a value from the cache.
        
        Args:
            key: Cache key
            tier: Which cache tier to use
            
        Returns:
            Cached value or None
        """
        # Check memory first
        value = await self._memory_cache.get(key)
        if value is not None:
            self._stats.hits += 1
            return value
        
        # Check Redis if enabled
        if self._redis_enabled and tier in (CacheTier.REDIS, CacheTier.HYBRID):
            try:
                value = await self._redis.get(key)
                if value is not None:
                    # Warm memory cache
                    parsed = json.loads(value)
                    await self._memory_cache.set(key, parsed, ttl=self._default_ttl)
                    self._stats.hits += 1
                    return parsed
            except Exception as exc:
                logger.warning("Redis get failed: %s", exc)
        
        self._stats.misses += 1
        return None
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None,
                  tier: CacheTier = CacheTier.HYBRID) -> None:
        """Set a value in the cache.
        
        Args:
            key: Cache key
            value: Value to cache
            ttl: Time-to-live in seconds
            tier: Which cache tier to use
        """
        ttl = ttl or self._default_ttl
        
        # Set in memory
        await self._memory_cache.set(key, value, ttl=ttl)
        
        # Set in Redis if enabled
        if self._redis_enabled and tier in (CacheTier.REDIS, CacheTier.HYBRID):
            try:
                serialized = json.dumps(value, default=str)
                await self._redis.setex(key, int(ttl), serialized)
            except Exception as exc:
                logger.warning("Redis set failed: %s", exc)
        
        self._stats.sets += 1
    
    async def delete(self, key: str, tier: CacheTier = CacheTier.HYBRID) -> bool:
        """Delete a key from the cache.
        
        Args:
            key: Key to delete
            tier: Which cache tier to use
            
        Returns:
            True if deleted
        """
        memory_deleted = await self._memory_cache.delete(key)
        
        redis_deleted = False
        if self._redis_enabled and tier in (CacheTier.REDIS, CacheTier.HYBRID):
            try:
                redis_deleted = bool(await self._redis.delete(key))
            except Exception:
                pass
        
        self._stats.deletes += 1
        return memory_deleted or redis_deleted
    
    async def exists(self, key: str) -> bool:
        """Check if a key exists.
        
        Args:
            key: Key to check
            
        Returns:
            True if exists
        """
        return await self._memory_cache.exists(key)
    
    async def clear(self, namespace: Optional[str] = None) -> int:
        """Clear the cache.
        
        Args:
            namespace: Optional namespace to clear
            
        Returns:
            Number of entries cleared
        """
        count = await self._memory_cache.clear(namespace)
        
        if self._redis_enabled and namespace:
            try:
                cursor = 0
                pattern = f"{namespace}:*"
                while True:
                    cursor, keys = await self._redis.scan(cursor, match=pattern)
                    if keys:
                        await self._redis.delete(*keys)
                    if cursor == 0:
                        break
            except Exception:
                pass
        
        return count
    
    async def get_or_set(self, key: str, factory, ttl: Optional[float] = None) -> Any:
        """Get a value, or compute and cache it.
        
        Args:
            key: Cache key
            factory: Async function that produces the value
            ttl: Time-to-live in seconds
            
        Returns:
            Cached or computed value
        """
        value = await self.get(key)
        if value is not None:
            return value
        
        value = await factory()
        await self.set(key, value, ttl=ttl)
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get aggregated cache statistics."""
        memory_stats = self._memory_cache.get_stats()
        return {
            "memory": memory_stats,
            "redis_enabled": self._redis_enabled,
            "default_ttl": self._default_ttl,
            "aggregate": self._stats.to_dict(),
        }


# Global singleton
_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    """Get or create the global CacheManager singleton."""
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
