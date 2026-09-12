"""Development-only tooling routes.

`GET /devtools/device-token` exists purely so the renderer can run in a
PLAIN BROWSER (vite dev server / web build) during development: Electron
normally hands the renderer the device token from identity.json via
preload, but a browser has no Electron bridge. With this endpoint the web
preview authenticates exactly like the installed app.

Guarded twice on purpose (defense in depth):
1. env gate  — 404 unless settings.env == "development" (default-off in
   staging/production deployments even if someone imports the router).
2. loopback gate — 403 unless the request originates from 127.0.0.1/::1.
   The backend binds loopback by default, so only a local browser can
   reach it; a token is never served to a LAN-remote caller.

There is deliberately no POST/PUT here — read-only, one field.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from dash_backend.config import get_settings
from dash_backend.logging_config import get_logger
from dash_backend.security.local_identity import get_identity

logger = get_logger(__name__)

router = APIRouter()

_LOOPBACK = {"127.0.0.1", "::1", "localhost", "::ffff:127.0.0.1"}


def _devtools_enabled(request: Request) -> bool:
    settings = get_settings()
    if settings.env != "development":
        return False
    client_host = request.client.host if request.client else ""
    return client_host in _LOOPBACK


@router.get("/device-token")
async def get_device_token(request: Request) -> dict:
    """Return the local device token for browser-based development only."""
    if not _devtools_enabled(request):
        # 404 (not 403) outside development: don't advertise the route.
        raise HTTPException(status_code=404, detail="Not found")
    try:
        identity = get_identity()
    except Exception:
        logger.exception("devtools: could not load device identity")
        raise HTTPException(status_code=500, detail="Identity unavailable")
    return {"ok": True, "token": identity.device_token}
