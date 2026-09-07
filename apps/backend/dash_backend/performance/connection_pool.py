"""Connection Pool - Database and external service connection pooling."""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class PoolState(Enum):
    """Connection pool state."""
    IDLE = "idle"
    BUSY = "busy"
    CLOSED = "closed"


@dataclass
class PoolConfig:
    """Configuration for connection pool."""
    min_size: int = 2
    max_size: int = 10
    max_idle_time: float = 300.0  # 5 minutes
    max_age: float = 3600.0  # 1 hour
    acquire_timeout: float = 30.0


class ConnectionPool:
    """Generic connection pool.
    
    Features:
    - Connection reuse
    - Connection limits
    - Idle connection management
    - Connection lifecycle management
    """
    
    def __init__(
        self,
        create_connection: Callable,
        close_connection: Callable,
        config: Optional[PoolConfig] = None,
    ):
        self._create_connection = create_connection
        self._close_connection = close_connection
        self._config = config or PoolConfig()
        
        self._pool: Dict[str, Any] = {}
        self._available: Set[str] = set()
        self._in_use: Set[str] = set()
        self._created_at: Dict[str, float] = {}
        self._last_used: Dict[str, float] = {}
        self._lock = asyncio.Lock()
        self._closed = False
        
    async def acquire(self) -> Optional[Any]:
        """Acquire a connection from the pool."""
        if self._closed:
            raise RuntimeError("Pool is closed")
        
        async with self._lock:
            # Try to get an available connection
            if self._available:
                conn_id = self._available.pop()
                self._in_use.add(conn_id)
                self._last_used[conn_id] = asyncio.get_event_loop().time()
                return self._pool[conn_id]
            
            # Create new connection if under max size
            if len(self._pool) < self._config.max_size:
                try:
                    conn = await self._create_connection()
                    conn_id = str(id(conn))
                    self._pool[conn_id] = conn
                    self._in_use.add(conn_id)
                    self._created_at[conn_id] = asyncio.get_event_loop().time()
                    self._last_used[conn_id] = asyncio.get_event_loop().time()
                    logger.debug("Created new connection: %s", conn_id)
                    return conn
                except Exception as e:
                    logger.error("Failed to create connection: %s", e)
                    return None
            
            # Wait for available connection
            logger.warning("Pool exhausted, waiting for connection")
            return None
    
    async def release(self, connection: Any) -> None:
        """Release a connection back to the pool."""
        if self._closed:
            await self._close_connection(connection)
            return
        
        async with self._lock:
            conn_id = str(id(connection))
            
            if conn_id in self._in_use:
                self._in_use.remove(conn_id)
                self._available.add(conn_id)
                self._last_used[conn_id] = asyncio.get_event_loop().time()
    
    async def close(self) -> None:
        """Close all connections in the pool."""
        self._closed = True
        
        async with self._lock:
            for conn_id, conn in self._pool.items():
                try:
                    await self._close_connection(conn)
                except Exception as e:
                    logger.error("Failed to close connection %s: %s", conn_id, e)
            
            self._pool.clear()
            self._available.clear()
            self._in_use.clear()
            self._created_at.clear()
            self._last_used.clear()
            
            logger.info("Connection pool closed")
    
    async def cleanup_idle(self) -> int:
        """Clean up idle connections that have exceeded max idle time."""
        now = asyncio.get_event_loop().time()
        closed = 0
        
        async with self._lock:
            # Don't close below min_size
            while len(self._pool) > self._config.min_size:
                # Find oldest idle connection
                oldest_id = None
                oldest_time = now
                
                for conn_id in self._available:
                    last_used = self._last_used.get(conn_id, now)
                    if last_used < oldest_time:
                        oldest_time = last_used
                        oldest_id = conn_id
                
                if oldest_id and (now - oldest_time) > self._config.max_idle_time:
                    conn = self._pool.pop(oldest_id)
                    self._available.discard(oldest_id)
                    self._created_at.pop(oldest_id, None)
                    self._last_used.pop(oldest_id, None)
                    
                    try:
                        await self._close_connection(conn)
                        closed += 1
                    except Exception as e:
                        logger.error("Failed to close idle connection: %s", e)
                else:
                    break
        
        if closed > 0:
            logger.info("Cleaned up %d idle connections", closed)
        
        return closed
    
    async def cleanup_aged(self) -> int:
        """Clean up connections that have exceeded max age."""
        now = asyncio.get_event_loop().time()
        closed = 0
        
        async with self._lock:
            aged_ids = []
            
            for conn_id, created_at in self._created_at.items():
                if (now - created_at) > self._config.max_age:
                    aged_ids.append(conn_id)
            
            for conn_id in aged_ids:
                if conn_id in self._available:
                    conn = self._pool.pop(conn_id)
                    self._available.discard(conn_id)
                    self._in_use.discard(conn_id)
                    self._created_at.pop(conn_id, None)
                    self._last_used.pop(conn_id, None)
                    
                    try:
                        await self._close_connection(conn)
                        closed += 1
                    except Exception as e:
                        logger.error("Failed to close aged connection: %s", e)
        
        if closed > 0:
            logger.info("Cleaned up %d aged connections", closed)
        
        return closed
    
    def get_stats(self) -> Dict[str, Any]:
        """Get pool statistics."""
        return {
            "total": len(self._pool),
            "available": len(self._available),
            "in_use": len(self._in_use),
            "min_size": self._config.min_size,
            "max_size": self._config.max_size,
            "closed": self._closed,
        }
    
    @asynccontextmanager
    async def connection(self):
        """Context manager for acquiring/releasing connections."""
        conn = await self.acquire()
        try:
            yield conn
        finally:
            if conn:
                await self.release(conn)


# Singleton pools
_pools: Dict[str, ConnectionPool] = {}


def register_pool(name: str, pool: ConnectionPool) -> None:
    """Register a connection pool."""
    _pools[name] = pool
    logger.info("Registered connection pool: %s", name)


def get_pool(name: str) -> Optional[ConnectionPool]:
    """Get a registered connection pool."""
    return _pools.get(name)


async def close_all_pools() -> None:
    """Close all registered pools."""
    for name, pool in _pools.items():
        try:
            await pool.close()
        except Exception as e:
            logger.error("Failed to close pool %s: %s", name, e)
    
    _pools.clear()
