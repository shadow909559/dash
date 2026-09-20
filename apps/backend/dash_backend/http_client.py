"""Process-wide shared httpx.AsyncClient pool.

Latency rationale (decisions.md #89): creating an ``httpx.AsyncClient`` per
request re-does the TCP connect (and TLS handshake for remote hosts) on every
single call — measured double-digit milliseconds per chat message against a
local Ollama, worse under port-pool pressure. One shared client per timeout
class keeps connections alive between requests; httpx handles per-request
concurrency internally, so sharing is safe for concurrent callers.

``close_shared_clients()`` is awaited at app shutdown so no sockets leak.
"""

from __future__ import annotations

from typing import Dict

import httpx

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_clients: Dict[float, httpx.AsyncClient] = {}


def get_shared_client(timeout: float = 60.0) -> httpx.AsyncClient:
    """Return the process-wide client for this timeout class, creating it once.

    Keep-alive connections expire after 120s idle (longer than typical gaps
    between chat messages); the pool caps are generous for a local assistant
    but bounded so a runaway caller cannot exhaust sockets.
    """
    client = _clients.get(timeout)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(
            timeout=httpx.Timeout(timeout, connect=10.0),
            limits=httpx.Limits(
                max_connections=20,
                max_keepalive_connections=10,
                keepalive_expiry=120.0,
            ),
        )
        _clients[timeout] = client
        logger.debug("created shared httpx client (timeout=%.0fs)", timeout)
    return client


async def close_shared_clients() -> None:
    """Close every pooled client (app shutdown path)."""
    for timeout, client in list(_clients.items()):
        try:
            await client.aclose()
        except Exception:
            logger.exception("failed to close shared httpx client (timeout=%.0f)", timeout)
    _clients.clear()
