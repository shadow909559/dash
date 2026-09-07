"""Simple in-memory cache with TTL support."""

import time
import hashlib
import json
from typing import Any, Optional, Dict
from dataclasses import dataclass


@dataclass
class CacheEntry:
    """Cache entry with value and expiration."""
    value: Any
    expires_at: float


class SimpleCache:
    """Simple in-memory cache with time-to-live (TTL) support."""
    
    def __init__(self, default_ttl: float = 3600.0):
        """Initialize cache with default TTL in seconds."""
        self._cache: Dict[str, CacheEntry] = {}
        self.default_ttl = default_ttl
    
    def _generate_key(self, prefix: str, *args, **kwargs) -> str:
        """Generate a cache key from arguments."""
        key_data = {"prefix": prefix, "args": args, "kwargs": kwargs}
        key_str = json.dumps(key_data, sort_keys=True, default=str)
        return hashlib.md5(key_str.encode()).hexdigest()
    
    def get(self, prefix: str, *args, **kwargs) -> Optional[Any]:
        """Get a value from cache if it exists and hasn't expired."""
        key = self._generate_key(prefix, *args, **kwargs)
        entry = self._cache.get(key)
        
        if entry is None:
            return None
        
        if time.time() > entry.expires_at:
            # Expired, remove and return None
            del self._cache[key]
            return None
        
        return entry.value
    
    def set(self, prefix: str, value: Any, ttl: Optional[float] = None, *args, **kwargs) -> None:
        """Set a value in cache with optional TTL override."""
        key = self._generate_key(prefix, *args, **kwargs)
        ttl = ttl if ttl is not None else self.default_ttl
        expires_at = time.time() + ttl
        self._cache[key] = CacheEntry(value=value, expires_at=expires_at)
    
    def clear(self) -> None:
        """Clear all cache entries."""
        self._cache.clear()
    
    def cleanup_expired(self) -> int:
        """Remove expired entries and return count of removed entries."""
        now = time.time()
        expired_keys = [
            key for key, entry in self._cache.items()
            if now > entry.expires_at
        ]
        for key in expired_keys:
            del self._cache[key]
        return len(expired_keys)


# Global cache instance
_global_cache = SimpleCache(default_ttl=3600.0)  # 1 hour default


def get_cache() -> SimpleCache:
    """Get the global cache instance."""
    return _global_cache
