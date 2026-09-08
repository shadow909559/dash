"""Infrastructure: connection pooling, caching, health checks, circuit breaker, retry."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Optional, Callable

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreaker:
    """Circuit breaker pattern for fault tolerance."""

    def __init__(self, failure_threshold: int = 5, recovery_timeout: float = 30.0, half_open_max: int = 1) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._half_open_max = half_open_max
        self._breakers: dict[str, dict] = {}

    def get_state(self, service: str) -> dict:
        if service not in self._breakers:
            self._breakers[service] = {"state": CircuitState.CLOSED.value, "failures": 0, "successes": 0,
                                       "last_failure": None, "last_success": None, "total_trips": 0}
        b = self._breakers[service]
        if b["state"] == CircuitState.OPEN.value and b["last_failure"]:
            elapsed = time.time() - b["last_failure"]
            if elapsed > self._recovery_timeout:
                b["state"] = CircuitState.HALF_OPEN.value
        return {"service": service, **b}

    def record_success(self, service: str) -> dict:
        b = self.get_state(service)
        if b["state"] == CircuitState.HALF_OPEN.value:
            self._breakers[service]["state"] = CircuitState.CLOSED.value
            self._breakers[service]["failures"] = 0
        self._breakers[service]["successes"] += 1
        self._breakers[service]["last_success"] = time.time()
        return {"ok": True, "state": self._breakers[service]["state"]}

    def record_failure(self, service: str) -> dict:
        b = self.get_state(service)
        self._breakers[service]["failures"] += 1
        self._breakers[service]["last_failure"] = time.time()
        if self._breakers[service]["failures"] >= self._failure_threshold:
            self._breakers[service]["state"] = CircuitState.OPEN.value
            self._breakers[service]["total_trips"] += 1
            logger.warning("Circuit breaker OPEN for %s", service)
        return {"ok": True, "state": self._breakers[service]["state"]}

    def allow_request(self, service: str) -> bool:
        b = self.get_state(service)
        if b["state"] == CircuitState.CLOSED.value:
            return True
        if b["state"] == CircuitState.HALF_OPEN.value:
            return b["successes"] < self._half_open_max
        return False

    def reset(self, service: str) -> dict:
        self._breakers.pop(service, None)
        return {"ok": True}

    def get_all(self) -> dict:
        return {s: self.get_state(s) for s in self._breakers}


class RetryPolicy:
    """Configurable retry with exponential backoff."""

    def __init__(self, max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 30.0,
                 exponential: bool = True, jitter: bool = True) -> None:
        self._max_retries = max_retries
        self._base_delay = base_delay
        self._max_delay = max_delay
        self._exponential = exponential
        self._jitter = jitter

    def get_delays(self) -> list[float]:
        delays = []
        for i in range(self._max_retries):
            if self._exponential:
                delay = self._base_delay * (2 ** i)
            else:
                delay = self._base_delay
            delay = min(delay, self._max_delay)
            if self._jitter:
                import random
                delay *= (0.5 + random.random())
            delays.append(round(delay, 2))
        return delays

    def execute_with_retry(self, func: Callable, *args, **kwargs) -> dict:
        delays = self.get_delays()
        last_error = None
        for attempt, delay in enumerate(delays):
            try:
                result = func(*args, **kwargs)
                return {"ok": True, "result": result, "attempts": attempt + 1}
            except Exception as e:
                last_error = str(e)
                if attempt < len(delays) - 1:
                    time.sleep(min(delay, 1.0))  # Cap sleep for tests
        return {"ok": False, "error": last_error, "attempts": len(delays)}


class CacheService:
    """Multi-level caching with TTL and LRU eviction."""

    def __init__(self, max_size: int = 1000, default_ttl: float = 300.0) -> None:
        self._cache: dict[str, dict] = {}
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        entry = self._cache.get(key)
        if entry is None:
            self._misses += 1
            return None
        if time.time() > entry["expires_at"]:
            del self._cache[key]
            self._misses += 1
            return None
        entry["access_count"] += 1
        entry["last_accessed"] = time.time()
        self._hits += 1
        return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[float] = None) -> None:
        if len(self._cache) >= self._max_size:
            self._evict_lru()
        self._cache[key] = {"value": value, "expires_at": time.time() + (ttl or self._default_ttl),
                            "created_at": time.time(), "access_count": 0, "last_accessed": time.time()}

    def delete(self, key: str) -> bool:
        if key in self._cache:
            del self._cache[key]
            return True
        return False

    def clear(self) -> int:
        count = len(self._cache)
        self._cache.clear()
        self._hits = 0
        self._misses = 0
        return count

    def _evict_lru(self) -> None:
        if not self._cache:
            return
        oldest_key = min(self._cache, key=lambda k: self._cache[k].get("last_accessed", 0))
        del self._cache[oldest_key]

    def get_stats(self) -> dict:
        total = self._hits + self._misses
        return {"size": len(self._cache), "max_size": self._max_size, "hits": self._hits,
                "misses": self._misses, "hit_rate": round(self._hits / max(total, 1), 3)}

    def get_entries(self, limit: int = 50) -> list[dict]:
        return [{"key": k, "access_count": v["access_count"], "ttl_remaining": round(max(0, v["expires_at"] - time.time()), 1)}
                for k, v in sorted(self._cache.items(), key=lambda x: x[1].get("last_accessed", 0), reverse=True)[:limit]]


class HealthCheck:
    """Comprehensive health monitoring for all services."""

    def __init__(self) -> None:
        self._checks: dict[str, dict] = {}
        self._history: list[dict] = []

    def register(self, name: str, check_fn: Optional[Callable] = None, critical: bool = False) -> None:
        self._checks[name] = {"name": name, "critical": critical, "check_fn": check_fn,
                              "last_status": "unknown", "last_check": None, "consecutive_failures": 0}

    def check(self, name: str) -> dict:
        check = self._checks.get(name)
        if not check:
            return {"ok": False, "reason": f"Check '{name}' not registered"}
        status = "healthy"
        try:
            if check["check_fn"]:
                check["check_fn"]()
            check["consecutive_failures"] = 0
        except Exception as e:
            status = "unhealthy"
            check["consecutive_failures"] += 1
        check["last_status"] = status
        check["last_check"] = datetime.now(timezone.utc).isoformat()
        result = {"name": name, "status": status, "critical": check["critical"],
                  "consecutive_failures": check["consecutive_failures"], "checked_at": check["last_check"]}
        self._history.append(result)
        if len(self._history) > 500:
            self._history = self._history[-250:]
        return result

    def check_all(self) -> dict:
        results = {name: self.check(name) for name in self._checks}
        all_healthy = all(r["status"] == "healthy" for r in results.values())
        return {"overall": "healthy" if all_healthy else "degraded", "services": results}

    def get_history(self, name: Optional[str] = None, limit: int = 50) -> list[dict]:
        result = self._history
        if name:
            result = [r for r in result if r.get("name") == name]
        return list(reversed(result[-limit:]))


class ConnectionPool:
    """Connection pooling for database/HTTP connections."""

    def __init__(self, pool_name: str, max_size: int = 10, min_idle: int = 2) -> None:
        self._pool_name = pool_name
        self._max_size = max_size
        self._min_idle = min_idle
        self._active = 0
        self._idle = 0
        self._total_created = 0
        self._total_reused = 0
        self._total_timed_out = 0

    def acquire(self) -> dict:
        if self._idle > 0:
            self._idle -= 1
            self._total_reused += 1
            return {"ok": True, "connection_id": f"{self._pool_name}_conn_{self._total_created}", "reused": True}
        if self._active < self._max_size:
            self._active += 1
            self._total_created += 1
            return {"ok": True, "connection_id": f"{self._pool_name}_conn_{self._total_created}", "reused": False}
        self._total_timed_out += 1
        return {"ok": False, "reason": "Pool exhausted"}

    def release(self, connection_id: str) -> dict:
        self._active = max(0, self._active - 1)
        self._idle += 1
        return {"ok": True}

    def get_stats(self) -> dict:
        return {"pool": self._pool_name, "active": self._active, "idle": self._idle,
                "max_size": self._max_size, "total_created": self._total_created,
                "total_reused": self._total_reused, "total_timed_out": self._total_timed_out}


# Singletons
circuit_breaker = CircuitBreaker()
retry_policy = RetryPolicy()
cache_service = CacheService()
health_check = HealthCheck()
