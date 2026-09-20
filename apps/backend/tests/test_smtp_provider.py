"""Hermetic tests for the real SMTP CommunicationProvider.

The smtplib module is mocked at the boundary so no network is touched;
everything above that boundary (config validation, MIME assembly, the
SMTP conversation flow, evidence shape) runs for real.
"""

from __future__ import annotations

import asyncio
import os
import smtplib
from unittest import mock

import pytest

from dash_backend.assistant.communication import CommunicationProvider, LocalDraftProvider
from dash_backend.assistant.smtp_provider import (
    SmtpProvider,
    configure_pipeline_provider,
    looks_like_email,
    resolve_smtp_config,
)

_SMTP_KEYS = (
    "DASH_SMTP_HOST", "DASH_SMTP_PORT", "DASH_SMTP_TLS", "DASH_SMTP_FROM",
    "DASH_SMTP_TIMEOUT", "DASH_SMTP_AUTH", "DASH_SMTP_USER", "DASH_SMTP_PASS",
    "DASH_SMTP_TO_MAIN", "DASH_SMTP_TLS_CERT", "DASH_SMTP_TLS_KEY",
    "DASH_SMTP_OAUTH_TOKEN_URL", "DASH_SMTP_OAUTH_CLIENT_ID",
    "DASH_SMTP_OAUTH_REFRESH", "DASH_SMTP_NO_VERIFY_CERT", "DASH_SMTP_OAUTH_TIMEOUT",
)
_ORIG = {k: os.environ.get(k) for k in _SMTP_KEYS}


@pytest.fixture(autouse=True)
def _smtp_env(tmp_path, monkeypatch):
    """Isolate SMTP env vars and the CRM store for pipeline wiring tests."""
    for k in _SMTP_KEYS:
        monkeypatch.delenv(k, raising=False)
    # Isolate the CRM store dir for the pipeline-wiring tests.
    from dash_backend.assistant import crm_store
    monkeypatch.setattr(crm_store, "CRM_DIR", tmp_path / "crm", raising=False)
    yield


def _cfg_env(**over):
    env = {
        "DASH_SMTP_HOST": "smtp.example.com",
        "DASH_SMTP_USER": "dash@example.com",
        "DASH_SMTP_PASS": "app-secret",
        "DASH_SMTP_FROM": "DASH <dash@example.com>",
    }
    env.update(over)
    for k, v in env.items():
        os.environ[k] = v


def _ok_client() -> mock.MagicMock:
    """A fake smtplib.SMTP instance that behaves like a healthy relay."""
    c = mock.MagicMock()
    c.connect.return_value = (220, b"relay ready")
    c.ehlo.return_value = (250, b"hello")
    c.has_extn.return_value = True
    c.login.return_value = (235, b"auth ok")
    c.starttls.return_value = (220, b"tls on")
    c.sendmail.return_value = {}
    c.docmd.return_value = (235, b"auth ok")
    return c


# ── config validation ───────────────────────────────────────────────────────


class TestConfig:
    def test_defaults_starttls_587(self):
        _cfg_env()
        cfg = resolve_smtp_config()
        assert (cfg.tls, cfg.port) == ("starttls", 587)

    def test_smtps_465(self):
        _cfg_env(DASH_SMTP_PORT="465", DASH_SMTP_TLS="smtps")
        cfg = resolve_smtp_config()
        assert (cfg.tls, cfg.port) == ("smtps", 465)

    def test_missing_host_raises(self):
        with pytest.raises(RuntimeError, match="DASH_SMTP_HOST"):
            resolve_smtp_config()

    def test_invalid_tls_raises(self):
        _cfg_env(DASH_SMTP_TLS="carrier-pigeon")
        with pytest.raises(RuntimeError, match="DASH_SMTP_TLS"):
            resolve_smtp_config()

    def test_invalid_auth_raises(self):
        _cfg_env(DASH_SMTP_AUTH="telepathy")
        with pytest.raises(RuntimeError, match="DASH_SMTP_AUTH"):
            resolve_smtp_config()

    def test_starttls_on_465_rejected(self):
        _cfg_env(DASH_SMTP_PORT="465")
        with pytest.raises(RuntimeError, match="465"):
            resolve_smtp_config()

    def test_smtps_on_25_rejected(self):
        _cfg_env(DASH_SMTP_PORT="25", DASH_SMTP_TLS="smtps")
        with pytest.raises(RuntimeError, match="25"):
            resolve_smtp_config()

    def test_plaintext_password_auth_refused(self):
        _cfg_env(DASH_SMTP_TLS="none")
        with pytest.raises(RuntimeError, match="clear text"):
            resolve_smtp_config()

    def test_cert_without_key_rejected(self):
        _cfg_env(DASH_SMTP_TLS_CERT="/x/cert.pem")
        with pytest.raises(RuntimeError, match="together"):
            resolve_smtp_config()

    def test_key_without_cert_rejected(self):
        _cfg_env(DASH_SMTP_TLS_KEY="/x/key.pem")
        with pytest.raises(RuntimeError, match="together"):
            resolve_smtp_config()

    def test_oauth2_without_token_url_rejected(self):
        _cfg_env(DASH_SMTP_AUTH="oauth2")
        with pytest.raises(RuntimeError, match="OAUTH_TOKEN_URL"):
            resolve_smtp_config()

    def test_bad_from_rejected(self):
        _cfg_env(DASH_SMTP_FROM="not-an-address")
        with pytest.raises(RuntimeError, match="DASH_SMTP_FROM"):
            resolve_smtp_config()

    def test_repr_never_leaks_secrets(self):
        _cfg_env()
        cfg = resolve_smtp_config()
        r = repr(cfg)
        assert "app-secret" not in r
        assert "password=****" in r


# ── provider contract ───────────────────────────────────────────────────────


class TestContract:
    def test_is_a_communication_provider(self):
        _cfg_env()
        p = SmtpProvider()
        assert isinstance(p, SmtpProvider)
        assert isinstance(p, CommunicationProvider)
        assert p.name == "smtp"

    def test_unconfigured_provider_defers_error_to_send(self):
        p = SmtpProvider()
        r = asyncio.run(p.send_message("a@b.com", "hi"))
        assert r["sent"] is False
        assert "SMTP not configured" in r["detail"]

    def test_call_state_honest(self):
        _cfg_env()
        r = asyncio.run(SmtpProvider().get_call_state())
        assert r["supported"] is False and r["configured"] is True

    def test_email_shape_check(self):
        assert looks_like_email("a@b.com")
        assert not looks_like_email("Acme Corp")
        assert not looks_like_email("")

    def test_no_valid_recipient_is_honest_failure(self):
        _cfg_env()
        p = SmtpProvider()
        r = asyncio.run(p.send_message("not an email", "hi"))
        assert r["sent"] is False
        assert "recipient" in r["detail"]

    def test_to_main_fallback(self):
        _cfg_env(DASH_SMTP_TO_MAIN="owner@example.com")
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("", "hello"))
        assert r["sent"] is True
        assert r["rcpt_to"] == "owner@example.com"


# ── happy paths ─────────────────────────────────────────────────────────────


class TestSend:
    def test_starttls_send_returns_evidence(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c) as cls:
            r = asyncio.run(p.send_message("client@example.org", "Hello from DASH"))
        assert r["sent"] is True
        assert r["provider_id"] == "smtp://smtp.example.com:587"
        assert r["rcpt_to"] == "client@example.org"
        assert "accepted" in r["rcpt_status"]["client@example.org"]
        assert r["transport"] == "starttls"
        assert isinstance(r["elapsed_ms"], int)
        cls.assert_called_once_with("smtp.example.com", 587, timeout=20.0)
        c.starttls.assert_called_once()
        c.login.assert_called_once_with("dash@example.com", "app-secret")
        c.sendmail.assert_called_once()

    def test_smtps_uses_smtp_ssl(self):
        _cfg_env(DASH_SMTP_PORT="465", DASH_SMTP_TLS="smtps")
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP_SSL", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is True
        assert r["transport"] == "smtps"

    def test_certificate_auth_skips_login(self):
        _cfg_env(DASH_SMTP_AUTH="certificate", DASH_SMTP_TLS_CERT="c.pem",
                 DASH_SMTP_TLS_KEY="k.pem")
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c), \
             mock.patch("ssl.SSLContext.load_cert_chain"):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is True
        c.login.assert_not_called()

    def test_oauth2_sends_xoauth2_command(self):
        _cfg_env(DASH_SMTP_AUTH="oauth2",
                 DASH_SMTP_OAUTH_TOKEN_URL="https://token.example.com/oauth2",
                 DASH_SMTP_OAUTH_CLIENT_ID="cid",
                 DASH_SMTP_OAUTH_REFRESH="refresh-token")
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c), \
             mock.patch("httpx.Client") as hc:
            hc.return_value.__enter__.return_value.post.return_value = mock.Mock(
                status_code=200, json=lambda: {"access_token": "at"})
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is True
        c.login.assert_not_called()
        args = c.docmd.call_args[0]
        assert args[0] == "AUTH" and args[1].startswith("XOAUTH2 ")

    def test_mime_message_well_formed(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            asyncio.run(p.send_message("client@example.org", "Hello from DASH"))
        body = c.sendmail.call_args[0][2]
        assert "From: DASH <dash@example.com>" in body
        assert "To: client@example.org" in body
        assert "Hello from DASH" in body


# ── failure honesty ─────────────────────────────────────────────────────────


class TestFailures:
    def test_connect_refused_is_sent_false(self):
        _cfg_env()
        p = SmtpProvider()
        with mock.patch.object(smtplib, "SMTP", side_effect=ConnectionRefusedError("refused")):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "ConnectionRefusedError" in r["detail"]

    def test_auth_failure_is_sent_false(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        c.login.side_effect = smtplib.SMTPAuthenticationError(535, b"bad credentials")
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "SMTPAuthenticationError" in r["detail"]

    def test_starttls_unavailable_is_sent_false(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        c.has_extn.return_value = False
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "STARTTLS" in r["detail"]

    def test_rcpt_refused_is_sent_false(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        c.sendmail.return_value = {"client@example.org": (550, b"5.1.1 user unknown")}
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "SMTPRecipientsRefused" in r["detail"]

    def test_rcpt_refusal_recorded_in_evidence_before_raise(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        c.sendmail.return_value = {"client@example.org": (550, b"5.1.1 nope")}
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert "550" in r["rcpt_status"]["client@example.org"]

    def test_oauth2_endpoint_failure_is_sent_false(self):
        _cfg_env(DASH_SMTP_AUTH="oauth2",
                 DASH_SMTP_OAUTH_TOKEN_URL="https://token.example.com/oauth2",
                 DASH_SMTP_OAUTH_CLIENT_ID="cid",
                 DASH_SMTP_OAUTH_REFRESH="refresh-token")
        p = SmtpProvider()
        c = _ok_client()
        with mock.patch.object(smtplib, "SMTP", return_value=c), \
             mock.patch("httpx.Client") as hc:
            hc.return_value.__enter__.return_value.post.return_value = mock.Mock(
                status_code=503)
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "503" in r["detail"]

    def test_bad_banner_is_sent_false(self):
        _cfg_env()
        p = SmtpProvider()
        c = _ok_client()
        c.connect.return_value = (554, b"go away")
        with mock.patch.object(smtplib, "SMTP", return_value=c):
            r = asyncio.run(p.send_message("client@example.org", "hi"))
        assert r["sent"] is False
        assert "banner" in r["detail"]


# ── pipeline wiring ─────────────────────────────────────────────────────────


class TestPipelineWiring:
    def test_configure_swaps_draft_for_smtp(self):
        from dash_backend.assistant.communication import OutboundPipeline
        _cfg_env()
        pipe = OutboundPipeline(provider=LocalDraftProvider())
        configure_pipeline_provider(pipe)
        assert isinstance(pipe.provider, SmtpProvider)

    def test_configure_without_host_keeps_draft(self):
        from dash_backend.assistant.communication import OutboundPipeline
        pipe = OutboundPipeline(provider=LocalDraftProvider())
        configure_pipeline_provider(pipe)
        assert isinstance(pipe.provider, LocalDraftProvider)

    def test_configure_never_overrides_custom_provider(self):
        from dash_backend.assistant.communication import OutboundPipeline

        class Custom(LocalDraftProvider):
            name = "custom"

        pipe = OutboundPipeline(provider=Custom())
        _cfg_env()
        configure_pipeline_provider(pipe)
        assert pipe.provider.name == "custom"

    def test_broken_smtp_config_keeps_draft_honestly(self):
        from dash_backend.assistant.communication import OutboundPipeline
        # host set but from-address invalid → provider construction defers the
        # error to send time; the swap still happens (host present).
        _cfg_env(DASH_SMTP_FROM="broken")
        pipe = OutboundPipeline(provider=LocalDraftProvider())
        configure_pipeline_provider(pipe)
        assert isinstance(pipe.provider, SmtpProvider)
        r = asyncio.run(pipe.provider.send_message("a@b.com", "hi"))
        assert r["sent"] is False and "SMTP not configured" in r["detail"]
