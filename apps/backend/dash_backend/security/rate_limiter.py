"""Simple in-memory token-bucket rate limiter for lightweight production hardening.

This module is intentionally conservative: a process-local limiter that protects
sensitive endpoints (auth) and user-facing websocket message handling. It is not
intended as a distributed or perfectly-accurate rate limiter — for that, use
Redis or an API gateway in production.
"""
from __future__ import annotations

import asyncio
import time
from typing import Dict, Optional

from fastapi import HTTPException, Request, status

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class TokenBucket:
    def __init__(self, capacity: int, refill_rate_per_sec: float) -> None:
        self.capacity = capacity
        self.refill_rate = refill_rate_per_sec
        self.tokens = capacity
        self.last = time.monotonic()
        self.lock = asyncio.Lock()

    async def consume(self, amount: float = 1.0) -> bool:
        async with self.lock:
            now = time.monotonic()
            elapsed = now - self.last
            self.last = now
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            if self.tokens >= amount:
                self.tokens -= amount
                return True
            return False


class RateLimiter:
    """Process-local rate limiter keyed by arbitrary string (IP or user id)."""

    def __init__(self, capacity: int, refill_period_seconds: int) -> None:
        # Refill rate = capacity / period
        self.capacity = capacity
        self.refill_period_seconds = refill_period_seconds
        self.refill_rate = capacity / max(1.0, float(refill_period_seconds))
        self.buckets: Dict[str, TokenBucket] = {}
        self._lock = asyncio.Lock()

    async def allow(self, key: str, amount: float = 1.0) -> bool:
        # Get or create bucket for key
        async with self._lock:
            b = self.buckets.get(key)
            if b is None:
                b = TokenBucket(self.capacity, self.refill_rate)
                self.buckets[key] = b
        return await b.consume(amount)


_settings = get_settings()

# Default conservative limits
_auth_capacity = 10  # e.g., 10 requests
_auth_period = 60  # per minute

_ws_capacity = 30  # chat messages per minute
_ws_period = 60

_auth_limiter = RateLimiter(_auth_capacity, _auth_period)
_ws_limiter = RateLimiter(_ws_capacity, _ws_period)


async def auth_rate_limit(request: Request) -> None:
    """FastAPI dependency to limit auth endpoints by client IP.

    Raises HTTPException(429) if the client is over the limit.
    """
    client = request.client.host if request.client else "unknown"
    allowed = await _auth_limiter.allow(client)
    if not allowed:
        logger.warning("Rate limit exceeded for auth endpoint: %s", client)
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many requests, please try again later.",
        )


async def websocket_rate_limit_user(user_id: str) -> None:
    """Check the websocket message rate for a user and raise HTTPException if exceeded.

    This is intended to be used at the start of message handling (per message).
    """
    allowed = await _ws_limiter.allow(str(user_id))
    if not allowed:
        logger.warning("WebSocket rate limit exceeded for user: %s", user_id)
        # For WebSocket we cannot raise HTTPException; callers should map to their protocol.
        raise RuntimeError("rate_limited")
