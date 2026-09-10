"""Route-level tests for the security endpoints (2FA, biometric, vault,
messenger, anonymization).

Exercises the /features routes in-process so behavior is verified even
when the running backend predates the change.
"""

from __future__ import annotations

import pytest

from tests.conftest import AUTH_HEADERS

pytestmark = pytest.mark.asyncio


async def test_2fa_enroll_verify_enable_flow(client):
    r = await client.post("/api/v1/features/security/2fa/enroll", headers=AUTH_HEADERS)
    assert r.status_code == 200
    d = r.json()
    assert d["ok"] and d["secret"] and d["otpauth_url"].startswith("otpauth://")
    # status reflects enrollment
    s = await client.get("/api/v1/features/security/2fa/status", headers=AUTH_HEADERS)
    assert s.json()["enrolled"] is True


async def test_biometric_flow_via_routes(client):
    a = await client.get("/api/v1/features/security/biometric/availability", headers=AUTH_HEADERS)
    assert a.status_code == 200
    e = await client.post("/api/v1/features/security/biometric/enroll", headers=AUTH_HEADERS)
    assert e.json()["ok"] is True
    ch = await client.post(
        "/api/v1/features/security/biometric/challenge",
        json={"action": "unlock"},
        headers=AUTH_HEADERS,
    )
    assert ch.json()["ok"] is True
    v = await client.post(
        "/api/v1/features/security/biometric/verify",
        json={"challenge": ch.json()["challenge"], "success": True},
        headers=AUTH_HEADERS,
    )
    assert v.json()["ok"] is True
    audit = await client.get("/api/v1/features/security/biometric/audit", headers=AUTH_HEADERS)
    assert len(audit.json()["events"]) >= 2


async def test_vault_crud_via_routes(client):
    add = await client.post(
        "/api/v1/features/vault/entries",
        json={"category": "login", "title": "Test Site", "fields": {"password": "s3cret!"}},
        headers=AUTH_HEADERS,
    )
    assert add.json()["ok"] is True
    entry_id = add.json()["entry"]["id"]

    lst = await client.get("/api/v1/features/vault/entries", headers=AUTH_HEADERS)
    assert any(e["id"] == entry_id for e in lst.json()["entries"])

    get = await client.get(f"/api/v1/features/vault/entries/{entry_id}", headers=AUTH_HEADERS)
    assert get.json()["entry"]["fields"]["password"] == "s3cret!"

    upd = await client.patch(
        f"/api/v1/features/vault/entries/{entry_id}",
        json={"favorite": True},
        headers=AUTH_HEADERS,
    )
    assert upd.json()["entry"]["favorite"] is True

    dele = await client.delete(f"/api/v1/features/vault/entries/{entry_id}", headers=AUTH_HEADERS)
    assert dele.json()["ok"] is True


async def test_anonymize_route_redacts_pii(client):
    r = await client.post(
        "/api/v1/features/privacy/anonymize",
        json={"text": "reach me at secret@corp.com"},
        headers=AUTH_HEADERS,
    )
    d = r.json()
    assert d["found"].get("email") == 1
    assert "secret@corp.com" not in d["redacted"]


async def test_messenger_send_and_list(client):
    send = await client.post(
        "/api/v1/features/messenger/send",
        json={"recipient": "colleague", "content": "private note"},
        headers=AUTH_HEADERS,
    )
    assert send.json()["encrypted"] is True
    convs = await client.get("/api/v1/features/messenger/conversations", headers=AUTH_HEADERS)
    assert any(c["other_user"] == "colleague" for c in convs.json()["conversations"])
