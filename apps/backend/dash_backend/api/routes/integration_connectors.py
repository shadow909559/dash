# -*- coding: utf-8 -*-
"""Slack / Telegram / Notion connector routes.

Webhook receivers are intentionally unauthenticated HTTP endpoints —
platforms deliver events server-to-server — but each verifies a platform
credential before touching state:
- Slack: v0 HMAC-SHA256 signature + 5-minute replay window
- Telegram: X-Telegram-Bot-Api-Secret-Token (constant-time compare)
- Notion: payload verification_token or X-Notion-Signature
Everything else requires a DASH JWT.
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response

from dash_backend.auth.dependencies import get_current_user
from dash_backend.services.integration_connectors import get_connector_service

router = APIRouter(prefix="/connectors", tags=["connectors"])

_service = get_connector_service()


@router.get("/status")
async def status(_user=Depends(get_current_user)):
    return {"ok": True, "connectors": _service.status()}


@router.post("/configure")
async def configure(body: dict, _user=Depends(get_current_user)):
    service = (body or {}).get("service", "")
    if service not in ("slack", "telegram", "notion"):
        raise HTTPException(400, "service must be slack, telegram, or notion")
    result = _service.configure(
        service,
        bot_token=body.get("bot_token", ""),
        webhook_url=body.get("webhook_url", ""),
        signing_secret=body.get("signing_secret", ""),
        webhook_secret=body.get("webhook_secret", ""),
        channel_id=body.get("channel_id", ""),
        workspace_id=body.get("workspace_id", ""),
        enabled=body.get("enabled", True),
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "configure failed"))
    return result


# ── Webhook receivers (unauthenticated, platform-verified) ────────────────

@router.post("/slack/events")
async def slack_events(request: Request):
    body = await request.body()
    result = _service.ingest_slack(
        timestamp=request.headers.get("X-Slack-Request-Timestamp", ""),
        body=body,
        signature=request.headers.get("X-Slack-Signature", ""),
    )
    if not result.get("ok"):
        raise HTTPException(result.get("status_code", 401), result.get("reason", "unauthorized"))
    if "challenge" in result:  # Slack url_verification handshake
        return Response(content=result["challenge"], media_type="text/plain")
    return {k: v for k, v in result.items() if k != "status_code"}


@router.post("/telegram/{secret_token}")
async def telegram_webhook(secret_token: str, request: Request):
    """Telegram accepts two webhook secret styles; both are supported:
    1. path token — the secret is embedded in the callback URL, or
    2. header — X-Telegram-Bot-Api-Secret-Token (verified in the service)."""
    payload = await request.json()
    header = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    result = _service.ingest_telegram(payload, header or secret_token)
    if not result.get("ok"):
        raise HTTPException(result.get("status_code", 401), result.get("reason", "unauthorized"))
    return {k: v for k, v in result.items() if k != "status_code"}


@router.post("/notion/webhook")
async def notion_webhook(request: Request):
    payload = await request.json()
    result = _service.ingest_notion(payload, request.headers.get("X-Notion-Signature", ""))
    if not result.get("ok"):
        raise HTTPException(result.get("status_code", 401), result.get("reason", "unauthorized"))
    return {k: v for k, v in result.items() if k != "status_code"}


# ── Forwarding + reads (authenticated) ────────────────────────────────────

@router.post("/forward")
async def forward(body: dict, _user=Depends(get_current_user)):
    result = _service.forward_out(
        (body or {}).get("service", ""),
        (body or {}).get("text", ""),
        (body or {}).get("channel", ""),
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "forward failed"))
    return result


@router.get("/rules")
async def rules(_user=Depends(get_current_user)):
    return {"ok": True, "rules": _service.get_rules()}


@router.post("/rules")
async def set_rules(body: dict, _user=Depends(get_current_user)):
    result = _service.set_rules(
        (body or {}).get("service", ""),
        to_dash=body.get("to_dash"),
        from_dash=body.get("from_dash"),
    )
    if not result.get("ok"):
        raise HTTPException(400, result.get("reason", "invalid service"))
    return result


@router.get("/messages/{service}")
async def messages(service: str, limit: int = 50, _user=Depends(get_current_user)):
    if service not in ("slack", "telegram", "notion"):
        raise HTTPException(400, "service must be slack, telegram, or notion")
    return {"ok": True, "messages": _service.get_messages(service, limit)}


@router.get("/events")
async def events(limit: int = 100, _user=Depends(get_current_user)):
    return {"ok": True, "events": _service.get_events(limit)}
