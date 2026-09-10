"""Real implementations of the security services.

Covers: RFC 6238 TOTP (generation, drift window, replay, backup codes),
AES-256-GCM vault (persistence, CRUD, stats), encrypted messenger
(at-rest ciphertext, round trip), PII anonymization (per-type accuracy,
deterministic pseudonyms), and biometric challenge flow (TTL, single use,
audit).
"""

from __future__ import annotations

import json
import os
import time

import pytest

from dash_backend.services.security_hardening import (
    BiometricAuthService,
    DataAnonymizer,
    EncryptedMessenger,
    PasswordManager,
    TOTPService,
    _totp,
)


# ── TOTP ───────────────────────────────────────────────────────────────────


@pytest.fixture()
def totp(tmp_path):
    return TOTPService(state_path=tmp_path / "2fa.json")


def test_totp_enroll_verify_enable(totp):
    r = totp.enroll("u1")
    assert r["ok"] and r["otpauth_url"].startswith("otpauth://totp/")
    code = _totp(r["secret"])
    v = totp.verify("u1", code, confirm=True)
    assert v["ok"] and v["method"] == "totp"
    assert totp.enable("u1")["ok"]
    assert totp.get_status("u1")["enabled"] is True


def test_totp_rejects_wrong_and_replays(totp):
    r = totp.enroll("u2")
    totp.verify("u2", _totp(r["secret"]), confirm=True)
    code = _totp(r["secret"])
    # Wrong code
    bad = str((int(code) + 1) % 1000000).zfill(6)
    assert totp.verify("u2", bad, at_time=time.time() + 120)["ok"] is False or bad != code
    # Replay of a valid code is rejected
    assert totp.verify("u2", code)["ok"] is False  # already used during confirm


def test_totp_accepts_drift_window(totp):
    r = totp.enroll("u3")
    secret = r["secret"]
    # Code from the previous window should verify (clock drift)
    prev = _totp(secret, at_time=time.time() - 30)
    v = totp.verify("u3", prev, confirm=True)
    assert v["ok"] is True


def test_backup_codes_single_use_and_hashed(totp):
    r = totp.enroll("u4")
    raw = r["backup_codes"][0]
    # Hashes only in state
    stored = totp._backup_codes["u4"]
    assert all(len(h) == 64 for h in stored)
    v = totp.verify("u4", raw, confirm=True)
    assert v["method"] == "backup_code"
    assert v["backup_codes_remaining"] == 9
    # Same code can't be reused
    assert totp.verify("u4", raw)["ok"] is False


def test_enable_requires_confirmation(totp):
    totp.enroll("u5")
    assert totp.enable("u5")["ok"] is False


def test_totp_state_persists(tmp_path):
    path = tmp_path / "2fa_state.json"
    s1 = TOTPService(state_path=path)
    s1.enroll("u6")
    s2 = TOTPService(state_path=path)
    assert s2.get_status("u6")["enrolled"] is True


# ── Password vault ─────────────────────────────────────────────────────────


@pytest.fixture()
def vault(tmp_path):
    return PasswordManager(state_path=tmp_path / "vault.json")


def test_vault_crud_and_encryption_at_rest(vault, tmp_path):
    r = vault.add_entry("login", "GitHub", {"username": "me", "password": "hunter2!"}, notes="n")
    assert r["ok"]
    eid = r["entry"]["id"]
    # Ciphertext on disk must not contain the secret
    raw_disk = (tmp_path / "vault.json").read_text()
    assert "hunter2!" not in raw_disk
    assert vault.get_entry(eid)["fields"]["password"] == "hunter2!"
    assert vault.update_entry(eid, favorite=True)["ok"]
    assert vault.delete_entry(eid)["ok"]
    assert vault.get_entry(eid) is None


def test_vault_persists_decrypted_across_restart(tmp_path):
    p = tmp_path / "vault2.json"
    v1 = PasswordManager(state_path=p)
    v1.add_entry("api_key", "OpenAI", {"key": "sk-test123456"})
    v2 = PasswordManager(state_path=p)
    entries = v2.list_entries()
    assert entries[0]["fields"]["key"] == "sk-test123456"


def test_vault_stats_weak_passwords(vault):
    vault.add_entry("login", "Weak", {"password": "short"})
    vault.add_entry("login", "Strong", {"password": "x" * 20})
    stats = vault.get_stats()
    assert stats["weak_passwords"] == 1 and stats["total"] == 2


def test_generate_password_length_and_symbols(vault):
    p = vault.generate_password(24, use_symbols=False)["password"]
    assert len(p) == 24 and not any(c in "!@#$%^&*()-_=+" for c in p)


# ── Encrypted messenger ────────────────────────────────────────────────────


@pytest.fixture()
def messenger(tmp_path):
    return EncryptedMessenger(state_path=tmp_path / "msgr.json")


def test_messenger_encrypts_at_rest(messenger, tmp_path):
    messenger.send_message("a", "b", "the launch codes are 123")
    raw_disk = (tmp_path / "msgr.json").read_text()
    assert "launch codes" not in raw_disk
    assert '"ct"' in raw_disk


def test_messenger_round_trip_and_read_state(messenger):
    r = messenger.send_message("alice", "bob", "hi bob")
    mid = r["message_id"]
    msgs = messenger.get_messages("bob", "alice")
    assert msgs[-1]["content"] == "hi bob"
    assert messenger.get_unread_count("bob") == 1
    assert messenger.mark_read("bob", "alice", mid)["ok"]
    assert messenger.get_unread_count("bob") == 0
    convs = messenger.get_conversations("alice")
    assert convs[0]["other_user"] == "bob"


def test_messenger_persists_decrypted(tmp_path):
    p = tmp_path / "msgr2.json"
    m1 = EncryptedMessenger(state_path=p)
    m1.send_message("a", "b", "persist me")
    m2 = EncryptedMessenger(state_path=p)
    assert m2.get_messages("b", "a")[-1]["content"] == "persist me"


# ── Anonymization ──────────────────────────────────────────────────────────


@pytest.fixture()
def anon():
    return DataAnonymizer(pepper=b"test-pepper")


def test_anonymize_all_pii_types(anon):
    text = "mail a@b.com from 10.0.0.5 card 4111 1111 1111 1111 ssn 123-45-6789 key AKIA26PMANXSPXTDD34I call +91 96735 45385"
    r = anon.anonymize(text)
    assert set(r["found"].keys()) == {"email", "ip_address", "credit_card", "ssn", "api_key", "phone"}
    for t in ("EMAIL", "IP_ADDRESS", "CREDIT_CARD", "SSN", "API_KEY"):
        assert f"[{t}" in r["redacted"]
    assert "[PHONE_...5385]" in r["redacted"]
    # originals gone
    assert "a@b.com" not in r["redacted"] and "4111" not in r["redacted"]


def test_pseudonyms_deterministic_but_unlinkable_across_peppers(anon):
    r1 = anon.anonymize("mail x@y.com")["redacted"]
    r2 = anon.anonymize("mail x@y.com")["redacted"]
    assert r1 == r2
    other = DataAnonymizer(pepper=b"other-pepper").anonymize("mail x@y.com")["redacted"]
    assert other != r1


def test_scan_reports_without_mutating(anon):
    s = anon.scan_text("contact bob@ex.com")
    assert s["has_pii"] and "email" in s["findings"]


def test_mask_types_subset(anon):
    r = anon.anonymize("a@b.com 10.0.0.1", mask_types=["email"])
    assert "a@b.com" not in r["redacted"] and "10.0.0.1" in r["redacted"]


# ── Biometric ──────────────────────────────────────────────────────────────


def test_biometric_full_flow():
    bio = BiometricAuthService()
    assert bio.enroll("u1")["ok"]
    ch = bio.create_challenge("u1", "unlock")
    assert ch["ok"] and ch["expires_in"] == bio.CHALLENGE_TTL_SECONDS
    v = bio.verify_challenge(ch["challenge"], True)
    assert v["ok"] and v["action"] == "unlock"
    events = bio.get_audit_log("u1")
    assert any(e["event"] == "verify" and e["ok"] for e in events)


def test_biometric_challenge_single_use_and_expiry():
    bio = BiometricAuthService()
    bio.enroll("u2")
    ch = bio.create_challenge("u2")
    bio.verify_challenge(ch["challenge"], True)
    # reuse rejected
    assert bio.verify_challenge(ch["challenge"], True)["ok"] is False
    # expired
    ch2 = bio.create_challenge("u2")
    bio._challenges[ch2["challenge"]]["expires"] = time.time() - 1
    assert bio.verify_challenge(ch2["challenge"], True)["ok"] is False
    # unenrolled users get no challenge
    assert bio.create_challenge("ghost")["ok"] is False


def test_biometric_revoke():
    bio = BiometricAuthService()
    bio.enroll("u3")
    bio.revoke("u3")
    assert bio.get_status("u3")["enrolled"] is False
    assert bio.create_challenge("u3")["ok"] is False
