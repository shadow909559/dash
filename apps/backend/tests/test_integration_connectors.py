"""Tests for the Slack / Telegram / Notion connectors.

Covers the guarantees that matter:
- Platform verification is enforced (forged requests rejected 401; properly
  signed requests accepted) — Slack HMAC v0, Telegram secret token,
  Notion verification token.
- Slack url_verification challenge handshake.
- Inbound messages deduplicate by platform event id.
- Forwarding rule `to_dash` pushes inbound messages into DASH notifications.
- Outbound forward without credentials records honestly (no fake "sent").
- Configs survive a connector restart (SQLite persistence).
- Route-level auth: webhooks are open but verified; everything else needs JWT.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time

import pytest

from dash_backend.services.integration_connectors import (
    ConnectorService,
    parse_notion_event,
    parse_slack_event,
    parse_telegram_update,
)
from dash_backend.services.local_store import open_store


def _make_service(tmp_path, monkeypatch):
    """Connector service on an isolated store; notifications mocked so
    forwarding doesn't depend on the push service singleton."""
    db = tmp_path / "connectors.db"
    monkeypatch.setenv("DASH_LOCAL_STORE", str(db))
    from dash_backend.services.local_store import LocalStore

    LocalStore._instances.clear()
    sent: list[dict] = []

    svc = ConnectorService(store=open_store(db))

    class FakePush:
        def send(self, title, body, **kwargs):
            sent.append({"title": title, "body": body, **kwargs})
            return {"status": "sent", "id": "n_fake"}

    # _notify_dash imports get_notification_service lazily; patch the source
    # module attribute so the lazy import picks up the fake.
    import dash_backend.services.notifications_push as push_mod

    monkeypatch.setattr(push_mod, "get_notification_service", lambda: FakePush())
    return svc, sent


SLACK_SECRET = "sh_test_signing_secret"


def _slack_headers(body: bytes, secret: str = SLACK_SECRET, ts: int | None = None):
    timestamp = str(ts if ts is not None else int(time.time()))
    baseline = f"v0:{timestamp}:".encode() + body
    sig = "v0=" + hmac.new(secret.encode(), baseline, hashlib.sha256).hexdigest()
    return {"X-Slack-Request-Timestamp": timestamp, "X-Slack-Signature": sig}


TG_SECRET = "tg_test_secret_token"


def _tg_payload(update_id=9001, text="hello from telegram"):
    return {"update_id": update_id, "message": {"message_id": 1, "date": int(time.time()),
             "chat": {"id": -100200, "title": "DASH Test"}, "from": {"username": "alice"},
             "text": text}}


NOTION_TOKEN = "nt_test_verification_token"


@pytest.fixture()
def configured(tmp_path, monkeypatch):
    svc, sent = _make_service(tmp_path, monkeypatch)
    svc.configure("slack", signing_secret=SLACK_SECRET)
    svc.configure("telegram", webhook_secret=TG_SECRET, bot_token="123:abc")
    svc.configure("notion", webhook_secret=NOTION_TOKEN)
    return svc, sent


# ── Verification ──────────────────────────────────────────────────────────

def test_slack_rejects_unsigned(configured):
    svc, _ = configured
    body = json.dumps({"type": "event_callback", "event": {"type": "message", "text": "hi"}}).encode()
    result = svc.ingest_slack("", body, "")
    assert not result["ok"] and result["status_code"] == 401


def test_slack_rejects_forged_signature(configured):
    svc, _ = configured
    body = b'{"type":"event_callback"}'
    headers = _slack_headers(body, secret="attacker_secret")
    result = svc.ingest_slack(headers["X-Slack-Request-Timestamp"], body, headers["X-Slack-Signature"])
    assert not result["ok"] and "mismatch" in result["reason"].lower()


def test_slack_rejects_stale_timestamp(configured):
    svc, _ = configured
    body = b'{"type":"event_callback"}'
    old = int(time.time()) - 3600  # 1h old — outside 5-minute window
    headers = _slack_headers(body, ts=old)
    result = svc.ingest_slack(headers["X-Slack-Request-Timestamp"], body, headers["X-Slack-Signature"])
    assert not result["ok"] and "replay" in result["reason"].lower()


def test_slack_accepts_valid_event(configured):
    svc, _ = configured
    body = json.dumps({"type": "event_callback", "event_id": "Ev111",
                       "event": {"type": "message", "user": "U1", "channel": "C1", "text": "deploy is red"}}).encode()
    h = _slack_headers(body)
    result = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    assert result["ok"] and result["message_id"]
    msgs = svc.get_messages("slack")
    assert msgs[-1]["content"] == "deploy is red" and msgs[-1]["author"] == "U1"


def test_slack_url_verification_challenge(configured):
    svc, _ = configured
    body = json.dumps({"type": "url_verification", "challenge": "ch_abc"}).encode()
    h = _slack_headers(body)
    result = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    assert result["ok"] and result["challenge"] == "ch_abc"


def test_slack_deduplicates_event_id(configured):
    svc, _ = configured
    body = json.dumps({"type": "event_callback", "event_id": "EvDup",
                       "event": {"type": "message", "user": "U1", "channel": "C1", "text": "once"}}).encode()
    h = _slack_headers(body)
    r1 = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    r2 = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    assert r1["ok"] and r2["ok"] and r2.get("duplicate") is True
    assert len([m for m in svc.get_messages("slack") if m["content"] == "once"]) == 1


def test_telegram_rejects_wrong_secret(configured):
    svc, _ = configured
    result = svc.ingest_telegram(_tg_payload(), "wrong_token")
    assert not result["ok"] and result["status_code"] == 401


def test_telegram_accepts_correct_secret(configured):
    svc, _ = configured
    result = svc.ingest_telegram(_tg_payload(text="standup in 5"), TG_SECRET)
    assert result["ok"] and result["message_id"]
    msg = svc.get_messages("telegram")[-1]
    assert msg["content"] == "standup in 5" and msg["author"] == "alice"
    assert msg["channel"] == "-100200"


def test_telegram_updates_dedup(configured):
    svc, _ = configured
    r1 = svc.ingest_telegram(_tg_payload(update_id=42), TG_SECRET)
    r2 = svc.ingest_telegram(_tg_payload(update_id=42), TG_SECRET)
    assert r1["ok"] and r2.get("duplicate") is True


def test_notion_rejects_bad_token(configured):
    svc, _ = configured
    result = svc.ingest_notion({"type": "page.updated", "verification_token": "nope"})
    assert not result["ok"] and result["status_code"] == 401


def test_notion_accepts_verification_token(configured):
    svc, _ = configured
    result = svc.ingest_notion({
        "type": "page.updated", "verification_token": NOTION_TOKEN,
        "data": {"entity": {"object": "page", "id": "pg1",
                            "properties": {"Title": {"type": "title", "title": [{"plain_text": "Roadmap"}]}}}},
    })
    assert result["ok"] and result["message_id"]
    msg = svc.get_messages("notion")[-1]
    assert "Roadmap" in msg["content"]


# ── Forwarding ────────────────────────────────────────────────────────────

def test_to_dash_rule_forwards_into_notifications(configured):
    svc, sent = configured
    svc.set_rules("slack", to_dash=True)
    body = json.dumps({"type": "event_callback", "event_id": "EvFwd",
                       "event": {"type": "message", "user": "U9", "channel": "C9", "text": "pager duty"}}).encode()
    h = _slack_headers(body)
    result = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    assert result["ok"] and result["dash_notification"] is True
    assert any("pager duty" in s["body"] for s in sent)
    assert any("Slack #C9" in s["title"] for s in sent)


def test_no_forwarding_by_default(configured):
    svc, sent = configured
    body = json.dumps({"type": "event_callback", "event_id": "EvNF",
                       "event": {"type": "message", "user": "U1", "channel": "C1", "text": "quiet"}}).encode()
    h = _slack_headers(body)
    result = svc.ingest_slack(h["X-Slack-Request-Timestamp"], body, h["X-Slack-Signature"])
    assert result["ok"] and result["dash_notification"] is False
    assert not sent


def test_outbound_without_credentials_records_honestly(tmp_path, monkeypatch):
    svc, _ = _make_service(tmp_path, monkeypatch)
    svc.configure("slack", webhook_url="")  # enabled but no webhook
    result = svc.forward_out("slack", "hello channel")
    assert result["ok"] and result["status"] == "recorded"
    assert result["error"] == "no_slack_webhook"


def test_outbound_disabled_connector_rejected(tmp_path, monkeypatch):
    svc, _ = _make_service(tmp_path, monkeypatch)
    result = svc.forward_out("telegram", "hello")
    assert not result["ok"] and "not configured" in result["reason"]


def test_outbound_telegram_success(monkeypatch):
    """Real delivery path with mocked httpx — asserts the Bot API contract."""
    calls = {}

    class FakeResp:
        status_code = 200
        def json(self):
            return {"ok": True}

    def fake_post(url, json=None, timeout=None):
        calls["url"] = url
        calls["json"] = json
        return FakeResp()

    monkeypatch.setattr("httpx.post", fake_post)

    svc = _bare_service(monkeypatch)
    svc.configure("telegram", bot_token="123:abc", channel_id="-100200")
    result = svc.forward_out("telegram", "daily summary")
    assert result["ok"] and result["status"] == "sent"
    assert calls["url"].endswith("/bot123:abc/sendMessage")
    assert calls["json"] == {"chat_id": "-100200", "text": "daily summary"}


def _bare_service(monkeypatch):
    from dash_backend.services.local_store import LocalStore

    monkeypatch.setenv("DASH_LOCAL_STORE", "memory")
    LocalStore._instances.clear()
    return ConnectorService(store=LocalStore.instance())


# ── Persistence ───────────────────────────────────────────────────────────

def test_config_persists_and_secret_decrypts(tmp_path, monkeypatch):
    svc, _ = _make_service(tmp_path, monkeypatch)
    svc.configure("telegram", webhook_secret=TG_SECRET, bot_token="123:abc")
    # on-disk value must be ciphertext, not plaintext
    raw = svc._store.kv_get("connector_cfg_telegram")
    assert raw["bot_token"].startswith("enc:") and TG_SECRET not in json.dumps(raw)
    # fresh instance = restart simulation
    from dash_backend.services.local_store import open_store as os_

    fresh = ConnectorService(store=os_(tmp_path / "connectors.db"))
    assert fresh.get_config("telegram")["has_bot_token"] is True
    status = {s["service"]: s for s in fresh.status()}
    assert status["telegram"]["has_webhook_secret"]
    # decrypted secret still verifies a webhook
    assert fresh.ingest_telegram(_tg_payload(), TG_SECRET)["ok"]


def test_rules_persist(tmp_path, monkeypatch):
    svc, _ = _make_service(tmp_path, monkeypatch)
    svc.set_rules("notion", to_dash=True, from_dash=True)
    from dash_backend.services.local_store import open_store as os_

    fresh = ConnectorService(store=os_(tmp_path / "connectors.db"))
    assert fresh.get_rules()["notion"] == {"to_dash": True, "from_dash": True}


# ── Route-level ───────────────────────────────────────────────────────────


async def test_routes_auth_enforcement(client):
    """/connectors status/rules/forward require JWT; webhook receivers do not
    (they verify platform credentials instead). The client fixture injects a
    valid token by default, so override with a bad one per request."""
    bad = {"Authorization": "Bearer invalid-token"}
    for method, path in [("GET", "/api/v1/connectors/status"), ("GET", "/api/v1/connectors/rules"),
                         ("POST", "/api/v1/connectors/forward")]:
        r = await client.request(method, path, json={} if method == "POST" else None, headers=bad)
        assert r.status_code in (401, 403), (path, r.status_code)


async def test_slack_webhook_route_rejects_unsigned(client):
    r = await client.post("/api/v1/connectors/slack/events",
                          content=b'{"type":"event_callback"}',
                          headers={"Content-Type": "application/json"})
    assert r.status_code == 401


async def test_notion_webhook_route_rejects_bad_token(client):
    r = await client.post("/api/v1/connectors/notion/webhook",
                          json={"type": "page.updated", "verification_token": "wrong"})
    assert r.status_code == 401
