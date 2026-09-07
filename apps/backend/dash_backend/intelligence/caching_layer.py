"""Caching Layer - Result caching for performance optimization."""

from __future__ import annotations

import hashlib
import json
from typing import Dict, List, Optional, Any, Callable, Awaitable
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime, timedelta
import asyncio

from dash_backend.core.logging import get_logger

logger = get_logger(__name__)


class CachePolicy(Enum):
    LRU = "lru"
    FIFO = "fifo"
    LFU = "lfu"
    TTL = "ttl"


@dataclass
class CacheEntry:
    key: str
    value: Any
    created_at: datetime = field(default_factory=datetime.utcnow)
    expires_at: Optional[datetime] = None
    access_count: int = 0
    last_accessed: Optional[datetime] = None
    size: int = 0


class CachingLayer:
    """Manages result caching with multiple eviction policies."""
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 3600, policy: CachePolicy = CachePolicy.LRU):
        self.cache: Dict[str, CacheEntry] = {}
        self.max_size = max_size
        self.default_ttl = default_ttl
        self.policy = policy
        self.hit_count = 0
        self.miss_count = 0
        self._lock = asyncio.Lock()
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = f"{prefix}:{json.dumps(args, sort_keys=True)}:{json.dumps(kwargs, sort_keys=True)}"
        return hashlib.sha256(key_data.encode()).hexdigest()
    
    async def get(self, key: str) -> Optional[Any]:
        """Get a value from cache."""
        async with self._lock:
            if key not in self.cache:
                self.miss_count += 1
                return None
            
            entry = self.cache[key]
            
            # Check if expired
            if entry.expires_at and entry.expires_at < datetime.utcnow():
                del self.cache[key]
                self.miss_count += 1
                return None
            
            # Update access statistics
            entry.access_count += 1
            entry.last_accessed = datetime.utcnow()
            self.hit_count += 1
            
            logger.debug(f"Cache hit: {key}")
            return entry.value
    
    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """Set a value in cache."""
        async with self._lock:
            # Evict if at capacity
            if len(self.cache) >= self.max_size:
                await self._evict()
            
            # Calculate expiration
            expires_at = None
            if ttl is not None:
                expires_at = datetime.utcnow() + timedelta(seconds=ttl)
            elif self.default_ttl > 0:
                expires_at = datetime.utcnow() + timedelta(seconds=self.default_ttl)
            
            # Calculate size (rough estimate)
            size = len(json.dumps(value, default=str))
            
            entry = CacheEntry(
                key=key,
                value=value,
                expires_at=expires_at,
                size=size,
            )
            
            self.cache[key] = entry
            logger.debug(f"Cache set: {key} (TTL: {ttl or self.default_ttl}s)")
    
    async def delete(self, key: str) -> bool:
        """Delete a key from cache."""
        async with self._lock:
            if key in self.cache:
                del self.cache[key]
                logger.debug(f"Cache delete: {key}")
                return True
            return False
    
    async def clear(self) -> None:
        """Clear all cache entries."""
        async with self._lock:
            self.cache.clear()
            self.hit_count = 0
            self.miss_count = 0
            logger.info("Cache cleared")
    
    async def _evict(self) -> None:
        """Evict entries based on policy."""
        if not self.cache:
            return
        
        if self.policy == CachePolicy.LRU:
            # Evict least recently used
            lru_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].last_accessed or datetime.min
            )
            del self.cache[lru_key]
        
        elif self.policy == CachePolicy.LFU:
            # Evict least frequently used
            lfu_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].access_count
            )
            del self.cache[lfu_key]
        
        elif self.policy == CachePolicy.FIFO:
            # Evict oldest
            fifo_key = min(
                self.cache.keys(),
                key=lambda k: self.cache[k].created_at
            )
            del self.cache[fifo_key]
        
        elif self.policy == CachePolicy.TTL:
            # Evict expired first, then oldest
            expired_keys = [
                k for k, v in self.cache.items()
                if v.expires_at and v.expires_at < datetime.utcnow()
            ]
            if expired_keys:
                del self.cache[expired_keys[0]]
            else:
                oldest_key = min(
                    self.cache.keys(),
                    key=lambda k: self.cache[k].created_at
                )
                del self.cache[oldest_key]
        
        logger.debug(f"Cache evicted (policy: {self.policy.value})")
    
    async def get_or_compute(self, key: str, compute_func: Callable[[], Awaitable[Any]], ttl: Optional[int] = None) -> Any:
        """Get value from cache or compute it."""
        value = await self.get(key)
        
        if value is not None:
            return value
        
        # Compute value
        value = await compute_func()
        await self.set(key, value, ttl)
        
        return value
    
    def get_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        total_requests = self.hit_count + self.miss_count
        hit_rate = self.hit_count / total_requests if total_requests > 0 else 0
        
        return {
            "size": len(self.cache),
            "max_size": self.max_size,
            "hit_count": self.hit_count,
            "miss_count": self.miss_count,
            "hit_rate": hit_rate,
            "policy": self.policy.value,
        }
    
    async def cleanup_expired(self) -> int:
        """Remove all expired entries."""
        async with self._lock:
            expired_keys = [
                k for k, v in self.cache.items()
                if v.expires_at and v.expires_at < datetime.utcnow()
            ]
            
            for key in expired_keys:
                del self.cache[key]
            
            if expired_keys:
                logger.info(f"Cleaned up {len(expired_keys)} expired cache entries")
            
            return len(expired_keys)
