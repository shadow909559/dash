# -*- coding: utf-8 -*-
"""Slack, Telegram, and Notion connectors with webhook receivers and
bidirectional message forwarding (decisions.md #37).

Design:
- Platform verification is real: Slack events are checked against the
  HMAC-SHA256 v0 signing scheme with a 5-minute replay window; Telegram
  webhooks must carry the configured secret-token header (constant-time
  compare); Notion webhooks are accepted only with a matching payload
  verification token or X-Notion-Signature. Unverified requests are
  rejected with 401 by the routes before touching state.
- Outbound delivery uses the platform's simplest real channel: Slack
  Incoming Webhooks and the Telegram Bot API sendMessage. Delivery is
  attempted only when credentials are configured; otherwise the message
  is recorded locally with status "recorded" so development and tests
  never touch the network. Failures mark the message "failed" with the
  error — no fake "sent".
- Bot tokens / signing secrets are encrypted at rest (AES-256-GCM with a
  per-install key file beside the local store), not stored plaintext.
- Forwarding rules (per service: inbound→DASH notifications, DASH→platform)
  default to OFF; inbound events are deduplicated by the platform's event
  id (event_id / update_id / request id).
- Configs, rules, and message history persist in the shared LocalStore.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import os
import secrets
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import parse_qs

from dash_backend.services.local_store import LocalStore

logger = logging.getLogger(__name__)

try:  # cryptography ships with the backend deps (used by security_hardening)
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    _AESGCM = AESGCM
except ImportError:  # pragma: no cover
    _AESGCM = None


# ── Secret box: encrypt bot tokens at rest ─────────────────────────────────

class SecretBox:
    """AES-256-GCM box keyed by a per-install key file. Protects stored
    credentials from casual DB copies, consistent with the caveats in
    decisions.md #34 (not a defense against full-disk attackers)."""

    def __init__(self, store: LocalStore) -> None:
        if _AESGCM is None:  # pragma: no cover
            raise RuntimeError("cryptography package required for connector secrets")
        key_path = store._path.parent / "connector_secrets.key"
        if not key_path.exists():
            key_path.parent.mkdir(parents=True, exist_ok=True)
            key_path.write_bytes(AESGCM.generate_key(bit_length=256))
        self._key = key_path.read_bytes()

    def encrypt(self, plaintext: str) -> str:
        if not plaintext:
            return ""
        nonce = secrets.token_bytes(12)
        ct = _AESGCM(self._key).encrypt(nonce, plaintext.encode(), None)
        return f"enc:{nonce.hex()}:{ct.hex()}"

    def decrypt(self, value: str) -> str:
        if not value or not value.startswith("enc:"):
            return value  # legacy plaintext or empty
        try:
            _, nonce_hex, ct_hex = value.split(":", 2)
            return _AESGCM(self._key).decrypt(bytes.fromhex(nonce_hex), bytes.fromhex(ct_hex), None).decode()
        except Exception:  # noqa: BLE001 — wrong key/corrupt row
            return ""


# ── Platform verification primitives ───────────────────────────────────────

SLACK_REPLAY_SECONDS = 5 * 60


def verify_slack_signature(signing_secret: str, timestamp: str, body: bytes, signature: str) -> tuple[bool, str]:
    """Slack v0 signing: HMAC-SHA256 over ``v0:timestamp:body``."""
    if not signing_secret:
        return False, "Slack signing secret not configured"
    if not timestamp or not signature:
        return False, "Missing Slack signature headers"
    try:
        ts = int(timestamp)
    except ValueError:
        return False, "Invalid Slack timestamp"
    if abs(time.time() - ts) > SLACK_REPLAY_SECONDS:
        return False, "Slack timestamp outside replay window"
    baseline = f"v0:{timestamp}:".encode() + body
    expected = "v0=" + hmac.new(signing_secret.encode(), baseline, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, signature):
        return False, "Slack signature mismatch"
    return True, ""


def verify_telegram_secret(configured_secret: str, header_value: str) -> tuple[bool, str]:
    if not configured_secret:
        return False, "Telegram secret token not configured"
    if not header_value:
        return False, "Missing X-Telegram-Bot-Api-Secret-Token header"
    if not hmac.compare_digest(configured_secret, header_value):
        return False, "Telegram secret token mismatch"
    return True, ""


def verify_notion_webhook(payload: dict, verification_token: str, signature_header: str = "") -> tuple[bool, str]:
    """Notion sends either a verification_token property (classic) or an
    X-Notion-Signature header (sha256 HMAC of the raw body with the token)."""
    if not verification_token:
        return False, "Notion verification token not configured"
    body_token = payload.get("verification_token") or ""
    if body_token and hmac.compare_digest(verification_token, body_token):
        return True, ""
    if signature_header:
        expected = "sha256=" + hmac.new(verification_token.encode(), json.dumps(payload, sort_keys=True).encode(), hashlib.sha256).hexdigest()
        if hmac.compare_digest(expected, signature_header):
            return True, ""
        return False, "Notion signature mismatch"
    return False, "Notion payload missing verification_token"


# ── Payload parsing ────────────────────────────────────────────────────────

def parse_slack_event(body_bytes: bytes) -> dict:
    """Normalize a Slack event payload (JSON events API, url_verification,
    or form-encoded slash command) to a common shape."""
    ctype_is_form = b"=" in body_bytes and not body_bytes.startswith(b"{")
    if ctype_is_form:
        form = {k: v[0] for k, v in parse_qs(body_bytes.decode("utf-8", "replace")).items()}
        return {
            "kind": "slash_command",
            "event_id": f"cmd_{form.get('trigger_id', secrets.token_hex(6))}",
            "author": form.get("user_name", "unknown"),
            "channel": form.get("channel_name", form.get("channel_id", "")),
            "text": form.get("text", ""),
            "command": form.get("command", ""),
            "raw": form,
        }
    payload = json.loads(body_bytes.decode("utf-8", "replace") or "{}")
    if payload.get("type") == "url_verification":
        return {"kind": "url_verification", "challenge": payload.get("challenge", ""), "event_id": ""}
    event = payload.get("event") or {}
    authz = payload.get("authorizations") or [{}]
    bot_only = event.get("subtype") == "bot_message" or bool(authz[0].get("is_bot", False))
    return {
        "kind": "event",
        "event_id": payload.get("event_id", ""),
        "event_type": event.get("type", payload.get("type", "")),
        "author": (event.get("user") or event.get("bot_id") or "unknown"),
        "channel": event.get("channel", ""),
        "text": event.get("text", ""),
        "bot_message": bool(bot_only),
        "raw": payload,
    }


def parse_telegram_update(payload: dict) -> dict:
    update_id = payload.get("update_id")
    message = payload.get("message") or payload.get("edited_message") or payload.get("channel_post") or {}
    chat = message.get("chat") or {}
    sender = message.get("from") or {}
    return {
        "kind": "update",
        "event_id": str(update_id) if update_id is not None else "",
        "author": sender.get("username") or sender.get("first_name") or "unknown",
        "channel": str(chat.get("id", "")),
        "channel_name": chat.get("title") or chat.get("username") or "",
        "text": message.get("text", message.get("caption", "")),
        "raw": payload,
    }


def parse_notion_event(payload: dict) -> dict:
    data = payload.get("data") or {}
    entity = data.get("entity") or {}
    return {
        "kind": "event",
        "event_id": payload.get("request_id", "") or f"notion_{secrets.token_hex(6)}",
        "event_type": payload.get("type", ""),
        "entity_type": entity.get("object", data.get("object", "")),
        "entity_id": entity.get("id", data.get("id", "")),
        "title": _notion_title(entity),
        "workspace": payload.get("workspace_id", "") or data.get("workspace_id", ""),
        "raw": payload,
    }


def _notion_title(entity: dict) -> str:
    props = entity.get("properties") or {}
    for prop in props.values():
        if isinstance(prop, dict) and prop.get("type") == "title":
            parts = prop.get("title") or []
            return "".join(p.get("plain_text", "") for p in parts)
    return ""


# ── Outbound delivery (real HTTP when configured) ──────────────────────────

def deliver_slack(webhook_url: str, text: str) -> tuple[bool, str]:
    """Post to a Slack Incoming Webhook. Returns (ok, error)."""
    if not webhook_url:
        return False, "no_slack_webhook"
    import httpx

    try:
        resp = httpx.post(webhook_url, json={"text": text}, timeout=10.0)
        return (resp.status_code == 200, "" if resp.status_code == 200 else f"slack_http_{resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return False, f"slack_error_{type(exc).__name__}"


def deliver_telegram(bot_token: str, chat_id: str, text: str) -> tuple[bool, str]:
    """Send via the Telegram Bot API sendMessage."""
    if not bot_token or not chat_id:
        return False, "no_telegram_credentials"
    import httpx

    try:
        resp = httpx.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json={"chat_id": chat_id, "text": text},
            timeout=10.0,
        )
        ok = resp.status_code == 200 and (resp.json().get("ok") is True)
        return (ok, "" if ok else f"telegram_http_{resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return False, f"telegram_error_{type(exc).__name__}"


def deliver_notion(webhook_url: str, text: str) -> tuple[bool, str]:
    """Notion has no bot-message primitive; forward via a user-supplied
    relay webhook if configured (e.g. an automation endpoint)."""
    if not webhook_url:
        return False, "no_notion_relay"
    import httpx

    try:
        resp = httpx.post(webhook_url, json={"content": text}, timeout=10.0)
        return (resp.status_code < 300, "" if resp.status_code < 300 else f"notion_http_{resp.status_code}")
    except Exception as exc:  # noqa: BLE001
        return False, f"notion_error_{type(exc).__name__}"


# ── Connector service ──────────────────────────────────────────────────────

_CONNECTOR_SERVICES = ("slack", "telegram", "notion")


class ConnectorService:
    """Configs, verification secrets, forwarding rules, and message history
    for the Slack/Telegram/Notion connectors."""

    def __init__(self, store: Optional[LocalStore] = None) -> None:
        self._store = store if store is not None else LocalStore.instance()
        self._box = SecretBox(self._store)
        self._configs: dict[str, dict] = {}
        for row in self._store.query("SELECT key, data FROM kv_settings WHERE key LIKE 'connector_cfg_%'"):
            cfg = json.loads(row["data"])
            for secret_field in ("bot_token", "signing_secret", "webhook_secret"):
                if cfg.get(secret_field):
                    cfg[secret_field] = self._box.decrypt(cfg[secret_field])
            self._configs[cfg["service"]] = cfg
        self._rules: dict[str, dict] = self._store.kv_get("connector_rules", {}) or {}
        self._messages: dict[str, list[dict]] = {s: [] for s in _CONNECTOR_SERVICES}
        for row in self._store.query("SELECT key, data FROM kv_settings WHERE key LIKE 'connector_msgs_%'"):
            self._messages[row["key"].removeprefix("connector_msgs_")] = json.loads(row["data"])
        self._seen: dict[str, set[str]] = {s: set() for s in _CONNECTOR_SERVICES}
        self._events: list[dict] = []

    # ── Configuration ────────────────────────────────────────────────

    def configure(self, service: str, *, bot_token: str = "", webhook_url: str = "",
                  signing_secret: str = "", webhook_secret: str = "",
                  channel_id: str = "", workspace_id: str = "", enabled: bool = True) -> dict:
        if service not in _CONNECTOR_SERVICES:
            return {"ok": False, "reason": f"Unsupported connector: {service}"}
        cfg = {
            "service": service,
            "bot_token": bot_token,
            "webhook_url": webhook_url,
            "signing_secret": signing_secret,   # Slack signing secret
            "webhook_secret": webhook_secret,   # Telegram secret token / Notion verification token
            "channel_id": channel_id,
            "workspace_id": workspace_id,
            "enabled": enabled,
            "configured_at": datetime.now(timezone.utc).isoformat(),
        }
        stored = {**cfg}
        for secret_field in ("bot_token", "signing_secret", "webhook_secret"):
            if stored[secret_field]:
                stored[secret_field] = self._box.encrypt(stored[secret_field])
        self._store.kv_set(f"connector_cfg_{service}", stored)
        self._configs[service] = cfg
        self._log_event("configured", service)
        return {"ok": True, "service": service, "enabled": enabled}

    def get_config(self, service: str) -> dict:
        cfg = self._configs.get(service)
        if not cfg:
            return {"ok": False, "reason": "not_configured", "service": service}
        return {
            "ok": True,
            "service": service,
            "enabled": cfg["enabled"],
            "has_bot_token": bool(cfg["bot_token"]),
            "has_webhook_url": bool(cfg["webhook_url"]),
            "has_signing_secret": bool(cfg["signing_secret"]),
            "has_webhook_secret": bool(cfg["webhook_secret"]),
            "channel_id": cfg["channel_id"],
            "workspace_id": cfg["workspace_id"],
            "configured_at": cfg["configured_at"],
        }

    def status(self) -> list[dict]:
        return [
            {
                "service": s,
                **{k: v for k, v in self.get_config(s).items() if k not in ("ok", "service", "reason")},
                "messages": len(self._messages.get(s, [])),
                "rules": self._rules.get(s, {"to_dash": False, "from_dash": False}),
            }
            for s in _CONNECTOR_SERVICES
        ]

    def _enabled(self, service: str) -> bool:
        cfg = self._configs.get(service)
        return bool(cfg and cfg["enabled"])

    # ── Verification + inbound webhooks ─────────────────────────────

    def ingest_slack(self, timestamp: str, body: bytes, signature: str) -> dict:
        cfg = self._configs.get("slack") or {}
        ok, reason = verify_slack_signature(cfg.get("signing_secret", ""), timestamp, body, signature)
        if not ok:
            self._log_event("slack_verify_failed", "slack", reason)
            return {"ok": False, "status_code": 401, "reason": reason}
        parsed = parse_slack_event(body)
        if parsed["kind"] == "url_verification":
            return {"ok": True, "challenge": parsed.get("challenge", "")}
        if parsed.get("bot_message"):
            return {"ok": True, "ignored": "bot_message"}
        if parsed["kind"] == "slash_command":
            return self._record_inbound("slack", parsed["channel"], parsed["text"], parsed["author"],
                                        {"command": parsed["command"]}, parsed["event_id"])
        return self._record_inbound("slack", parsed["channel"], parsed["text"], parsed["author"],
                                    {"event_type": parsed.get("event_type", "")}, parsed["event_id"])

    def ingest_telegram(self, payload: dict, secret_header: str) -> dict:
        cfg = self._configs.get("telegram") or {}
        ok, reason = verify_telegram_secret(cfg.get("webhook_secret", ""), secret_header)
        if not ok:
            self._log_event("telegram_verify_failed", "telegram", reason)
            return {"ok": False, "status_code": 401, "reason": reason}
        parsed = parse_telegram_update(payload)
        return self._record_inbound("telegram", parsed["channel"] or parsed["channel_name"],
                                    parsed["text"], parsed["author"],
                                    {"channel_name": parsed["channel_name"]}, parsed["event_id"])

    def ingest_notion(self, payload: dict, signature_header: str = "") -> dict:
        cfg = self._configs.get("notion") or {}
        ok, reason = verify_notion_webhook(payload, cfg.get("webhook_secret", ""), signature_header)
        if not ok:
            self._log_event("notion_verify_failed", "notion", reason)
            return {"ok": False, "status_code": 401, "reason": reason}
        parsed = parse_notion_event(payload)
        text = parsed["title"] or parsed["event_type"] or "Notion update"
        return self._record_inbound("notion", parsed["workspace"], text, "notion",
                                    {"event_type": parsed["event_type"], "entity_type": parsed["entity_type"],
                                     "entity_id": parsed["entity_id"]},
                                    parsed["event_id"])

    # ── Forwarding ───────────────────────────────────────────────────

    def set_rules(self, service: str, to_dash: Optional[bool] = None, from_dash: Optional[bool] = None) -> dict:
        if service not in _CONNECTOR_SERVICES:
            return {"ok": False, "reason": f"Unsupported connector: {service}"}
        rules = self._rules.get(service, {"to_dash": False, "from_dash": False})
        if to_dash is not None:
            rules["to_dash"] = bool(to_dash)
        if from_dash is not None:
            rules["from_dash"] = bool(from_dash)
        self._rules[service] = rules
        self._store.kv_set("connector_rules", self._rules)
        return {"ok": True, "service": service, **rules}

    def get_rules(self) -> dict:
        return {s: self._rules.get(s, {"to_dash": False, "from_dash": False}) for s in _CONNECTOR_SERVICES}

    def _record_inbound(self, service: str, channel: str, text: str, author: str,
                        metadata: dict, event_id: str) -> dict:
        if event_id and event_id in self._seen[service]:
            return {"ok": True, "duplicate": True, "service": service}
        if event_id:
            self._seen[service].add(event_id)
            if len(self._seen[service]) > 500:
                self._seen[service] = set(sorted(self._seen[service])[-500:])
        msg = {
            "id": f"im_{secrets.token_hex(8)}",
            "service": service,
            "direction": "inbound",
            "content": text,
            "author": author,
            "channel": channel,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata,
        }
        self._messages.setdefault(service, []).append(msg)
        self._persist_messages(service)
        self._log_event("message_received", service, channel)
        forwarded = {"dash_notification": False}
        if self.get_rules()[service]["to_dash"]:
            forwarded["dash_notification"] = self._notify_dash(service, msg)
        return {"ok": True, "message_id": msg["id"], "service": service, **forwarded}

    def _notify_dash(self, service: str, msg: dict) -> bool:
        """Forward an inbound platform message into DASH notifications.
        Failures never break webhook handling."""
        try:
            from dash_backend.services.notifications_push import get_notification_service

            result = get_notification_service().send(
                title=f"{service.title()} #{msg['channel']}: {msg['author']}".strip(),
                body=msg["content"][:500],
                data={"source": f"connector_{service}", "message_id": msg["id"]},
            )
            return result.get("status") in ("sent", "deferred", "scheduled")
        except Exception:  # noqa: BLE001
            logger.exception("Dash notification forwarding failed for %s", service)
            return False

    def forward_out(self, service: str, text: str, channel: str = "") -> dict:
        """Send a DASH message out through a platform connector."""
        if service not in _CONNECTOR_SERVICES:
            return {"ok": False, "reason": f"Unsupported connector: {service}"}
        if not self._enabled(service):
            return {"ok": False, "reason": f"{service} connector not configured or disabled"}
        cfg = self._configs[service]
        if service == "slack":
            ok, error = deliver_slack(cfg["webhook_url"], text)
        elif service == "telegram":
            ok, error = deliver_telegram(cfg["bot_token"], channel or cfg["channel_id"], text)
        else:
            ok, error = deliver_notion(cfg["webhook_url"], text)
        status = "sent" if ok else ("recorded" if error == "no_" + ("slack_webhook" if service == "slack" else "telegram_credentials" if service == "telegram" else "notion_relay") else "failed")
        msg = {
            "id": f"om_{secrets.token_hex(8)}",
            "service": service,
            "direction": "outbound",
            "content": text,
            "author": "DASH",
            "channel": channel or cfg["channel_id"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "error": "" if ok else error,
        }
        self._messages.setdefault(service, []).append(msg)
        self._persist_messages(service)
        self._log_event("message_sent" if ok else "message_" + status, service, msg["channel"])
        return {"ok": True, "message_id": msg["id"], "status": status,
                "service": service, "error": msg["error"]}

    # ── Reads ────────────────────────────────────────────────────────

    def get_messages(self, service: str, limit: int = 50) -> list[dict]:
        return list(self._messages.get(service, [])[-limit:])

    def get_events(self, limit: int = 100) -> list[dict]:
        return self._events[-limit:]

    # ── Internals ────────────────────────────────────────────────────

    def _persist_messages(self, service: str) -> None:
        # Keep the last 200 per service; history is diagnostic, not core data.
        self._messages[service] = self._messages[service][-200:]
        self._store.kv_set(f"connector_msgs_{service}", self._messages[service])

    def _log_event(self, event: str, service: str, detail: str = "") -> None:
        self._events.append({
            "event": event,
            "service": service,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._events) > 500:
            self._events = self._events[-500:]


_singleton: Optional[ConnectorService] = None


def get_connector_service() -> ConnectorService:
    global _singleton
    if _singleton is None:
        _singleton = ConnectorService()
    return _singleton
