"""Cache Manager - Multi-level caching for performance optimization."""

from __future__ import annotations

import asyncio
import json
import logging
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional, Set
from enum import Enum

logger = logging.getLogger(__name__)


class CacheLevel(Enum):
    """Cache levels."""
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"


@dataclass
class CacheEntry:
    """A cache entry."""
    key: str
    value: Any
    ttl: float
    created_at: float
    access_count: int = 0
    last_accessed: float = 0.0
    size_bytes: int = 0
    
    @property
    def is_expired(self) -> bool:
        """Check if entry is expired."""
        return time.time() - self.created_at > self.ttl
    
    @property
    def age(self) -> float:
        """Get entry age in seconds."""
        return time.time() - self.created_at


class CachePolicy:
    """Cache eviction policy."""
    
    LRU = "lru"
    LFU = "lfu"
    FIFO = "fifo"
    TTL = "ttl"


class MemoryCache:
    """In-memory cache with LRU eviction."""
    
    def __init__(self, max_size: int = 1000, default_ttl: float = 3600):
        self.max_size = max_size
        self.default_ttl = default_ttl
        self._cache: Dict[str, CacheEntry] = {}
        self._lock = asyncio.Lock()
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
        }
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        async with self._lock:
            entry = self._cache.get(key)
            
            if entry is None:
                self._stats["misses"] += 1
                return None
            
            if entry.is_expired:
                del self._cache[key]
                self._stats["misses"] += 1
                return None
            
            # Update access stats
            entry.access_count += 1
            entry.last_accessed = time.time()
            self._stats["hits"] += 1
            
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        """Set a value in cache."""
        ttl = ttl or self.default_ttl
        
        async with self._lock:
            # Calculate size (rough estimate)
            size = len(json.dumps(value)) if isinstance(value, (dict, list)) else len(str(value))
            
            entry = CacheEntry(
                key=key,
                value=value,
                ttl=ttl,
                created_at=time.time(),
                last_accessed=time.time(),
                size_bytes=size,
            )
            
            self._cache[key] = entry
            
            # Evict if over capacity
            await self._evict_if_needed()
    
    async def delete(self, key: str) -> bool:
        """Delete a value from cache."""
        async with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self._cache.clear()
    
    async def _evict_if_needed(self) -> None:
        """Evict entries if cache is over capacity."""
        while len(self._cache) > self.max_size:
            # LRU eviction
            oldest_key = min(
                self._cache.keys(),
                key=lambda k: self._cache[k].last_accessed,
            )
            del self._cache[oldest_key]
            self._stats["evictions"] += 1
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self._stats["hits"] + self._stats["misses"]
        hit_rate = self._stats["hits"] / total_requests if total_requests > 0 else 0.0
        
        return {
            "hits": self._stats["hits"],
            "misses": self._stats["misses"],
            "hit_rate": hit_rate,
            "evictions": self._stats["evictions"],
            "size": len(self._cache),
            "max_size": self.max_size,
        }


class CacheManager:
    """Multi-level cache manager.
    
    Features:
    - Memory cache (fastest)
    - Disk cache (persistent)
    - Cache warming
    - Cache invalidation
    - Cache statistics
    """
    
    def __init__(
        self,
        memory_max_size: int = 1000,
        memory_default_ttl: float = 3600,
        disk_cache_dir: Optional[str] = None,
    ):
        self.memory_cache = MemoryCache(memory_max_size, memory_default_ttl)
        self._disk_cache_dir = disk_cache_dir
        self._enabled = True
        
    async def get(self, key: str, level: CacheLevel = CacheLevel.MEMORY) -> Optional[Any]:
        """Get a value from cache, checking levels in order."""
        if not self._enabled:
            return None
        
        # Try memory first
        value = await self.memory_cache.get(key)
        if value is not None:
            return value
        
        # Try disk if memory miss
        if level in [CacheLevel.DISK, CacheLevel.NETWORK]:
            value = await self._get_from_disk(key)
            if value is not None:
                # Promote to memory
                await self.memory_cache.set(key, value)
                return value
        
        return None
    
    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
        levels: Optional[List[CacheLevel]] = None,
    ) -> None:
        """Set a value in cache at specified levels."""
        if not self._enabled:
            return
        
        levels = levels or [CacheLevel.MEMORY]
        
        if CacheLevel.MEMORY in levels:
            await self.memory_cache.set(key, value, ttl)
        
        if CacheLevel.DISK in levels:
            await self._set_to_disk(key, value, ttl)
    
    async def delete(self, key: str) -> None:
        """Delete a value from all cache levels."""
        await self.memory_cache.delete(key)
        await self._delete_from_disk(key)
    
    async def clear(self) -> None:
        """Clear all cache levels."""
        await self.memory_cache.clear()
        # Clear disk cache if implemented
    
    async def warm(self, keys: List[str], load_func: callable) -> Dict[str, Any]:
        """Warm cache with pre-loaded values."""
        results = {}
        
        for key in keys:
            # Check if already cached
            cached = await self.get(key)
            if cached is not None:
                results[key] = cached
                continue
            
            # Load and cache
            try:
                value = await load_func(key)
                if value is not None:
                    await self.set(key, value)
                    results[key] = value
            except Exception as e:
                logger.error("Failed to warm cache for key %s: %s", key, e)
        
        return results
    
    async def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching a pattern."""
        count = 0
        
        # Simple pattern matching (exact or prefix)
        async with self.memory_cache._lock:
            keys_to_delete = []
            for key in self.memory_cache._cache.keys():
                if pattern in key or key.startswith(pattern):
                    keys_to_delete.append(key)
            
            for key in keys_to_delete:
                del self.memory_cache._cache[key]
                count += 1
        
        return count
    
    async def _get_from_disk(self, key: str) -> Optional[Any]:
        """Get value from disk cache."""
        # Placeholder for disk cache implementation
        return None
    
    async def _set_to_disk(self, key: str, value: Any, ttl: Optional[float]) -> None:
        """Set value in disk cache."""
        # Placeholder for disk cache implementation
        pass
    
    async def _delete_from_disk(self, key: str) -> None:
        """Delete value from disk cache."""
        # Placeholder for disk cache implementation
        pass
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "memory": self.memory_cache.get_stats(),
            "enabled": self._enabled,
        }
    
    def enable(self) -> None:
        """Enable caching."""
        self._enabled = True
    
    def disable(self) -> None:
        """Disable caching."""
        self._enabled = False


_cache_manager: Optional[CacheManager] = None


def get_cache_manager() -> CacheManager:
    global _cache_manager
    if _cache_manager is None:
        _cache_manager = CacheManager()
    return _cache_manager
