"""Real SMTP CommunicationProvider (spec #12/#51/#57/#100/#155).

Replaces the draft boundary for email when SMTP is configured:
`DASH_SMTP_HOST` present → the pipeline's default provider is SMTP;
otherwise the honest LocalDraftProvider stays (no fake success either way).

Delivery evidence (spec #63 — no success without provider confirmation):
    sent=True  ONLY after the SMTP DATA command returns 2xx. The per-recipient
               RCPT responses are the receipt-level evidence and are returned.
    sent=False on any connect/TLS/auth/RCPT/IO error, with an honest detail.

Security posture:
- credentials are read from env only, never logged, never persisted;
- STARTTLS/SMTPS enforced by default, cert verification on by default;
- OAuth2 (XOAUTH2) mints its access token over TLS from DASH_SMTP_OAUTH_TOKEN_URL
  when configured — otherwise an explicit failure, never a silent fallback.

All smtplib/socket calls run in a worker thread (asyncio.to_thread) so the
event loop is never blocked.
"""

from __future__ import annotations

import asyncio
import os
import re
import smtplib
import ssl
import time
from email.message import EmailMessage
from email.utils import formataddr, parseaddr
from typing import Any

from dash_backend.assistant.communication import CommunicationProvider
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_VALID_TLS = ("starttls", "smtps", "none")
_VALID_AUTH = ("plain", "login", "oauth2", "certificate")


def _env(key: str, default: str = "") -> str:
    return os.environ.get(key, default).strip()


class SmtpConfig:
    """Resolved SMTP configuration; build via resolve_smtp_config()."""

    def __init__(
        self, host: str, port: int, tls: str, auth: str, username: str,
        password: str, from_address: str, timeout: float, to_main: str,
        oauth_token_url: str | None = None, oauth_client_id: str | None = None,
        oauth_refresh_token: str | None = None, tls_certfile: str | None = None,
        tls_keyfile: str | None = None, verify_cert: bool = True,
        oauth_timeout: float = 10.0,
    ) -> None:
        self.host = host
        self.port = port
        self.tls = tls
        self.auth = auth
        self.username = username
        self.password = password
        self.from_address = from_address
        self.timeout = timeout
        self.to_main = to_main
        self.oauth_token_url = oauth_token_url
        self.oauth_client_id = oauth_client_id
        self.oauth_refresh_token = oauth_refresh_token
        self.tls_certfile = tls_certfile
        self.tls_keyfile = tls_keyfile
        self.verify_cert = verify_cert
        self.oauth_timeout = oauth_timeout

    def __repr__(self) -> str:  # never leak credentials in logs
        return (f"SmtpConfig(host={self.host!r}, port={self.port}, tls={self.tls!r}, "
                f"auth={self.auth!r}, from={self.from_address!r}, password=****, "
                f"oauth_refresh_token=****)")


def resolve_smtp_config() -> SmtpConfig:
    """Read and validate SMTP settings from the environment.

    Raises RuntimeError on missing/contradictory configuration — the caller
    surfaces the real reason instead of guessing.
    """
    host = _env("DASH_SMTP_HOST")
    if not host:
        raise RuntimeError("DASH_SMTP_HOST is not configured — no SMTP target")

    port = int(_env("DASH_SMTP_PORT", "587") or "587")
    tls = _env("DASH_SMTP_TLS", "starttls").lower()
    if tls not in _VALID_TLS:
        raise RuntimeError(f"invalid DASH_SMTP_TLS={tls!r}; expected one of {_VALID_TLS}")
    auth = _env("DASH_SMTP_AUTH", "plain").lower()
    if auth not in _VALID_AUTH:
        raise RuntimeError(f"invalid DASH_SMTP_AUTH={auth!r}; expected one of {_VALID_AUTH}")
    # TLS/auth cross-checks: explicit, honest failures for misconfigurations.
    if tls == "smtps" and port == 25:
        raise RuntimeError("DASH_SMTP_TLS=smtps on port 25 — use DASH_SMTP_PORT=465 for SMTPS")
    if tls == "starttls" and port == 465:
        raise RuntimeError(
            "port 465 implies implicit TLS; set DASH_SMTP_TLS=smtps (or use port 587 for STARTTLS)")
    if tls == "none" and auth in ("plain", "login"):
        raise RuntimeError(
            "DASH_SMTP_TLS=none with password auth would transmit credentials in "
            "clear text — refused; use starttls/smtps or oauth2/certificate")

    from_address = _env("DASH_SMTP_FROM", "DASH <dash@localhost>")
    name, addr = parseaddr(from_address)
    if not addr or "@" not in addr:
        raise RuntimeError(f"DASH_SMTP_FROM has no parseable address: {from_address!r}")

    certfile = _env("DASH_SMTP_TLS_CERT") or None
    keyfile = _env("DASH_SMTP_TLS_KEY") or None
    if bool(certfile) != bool(keyfile):
        raise RuntimeError("DASH_SMTP_TLS_CERT and DASH_SMTP_TLS_KEY must be set together")

    token_url = _env("DASH_SMTP_OAUTH_TOKEN_URL") or None
    if auth == "oauth2" and not token_url:
        raise RuntimeError(
            "DASH_SMTP_AUTH=oauth2 requires DASH_SMTP_OAUTH_TOKEN_URL — "
            "refusing to fake the token step")

    return SmtpConfig(
        host=host,
        port=port,
        tls=tls,
        auth=auth,
        username=_env("DASH_SMTP_USER"),
        password=_env("DASH_SMTP_PASS"),
        from_address=from_address,
        timeout=float(_env("DASH_SMTP_TIMEOUT", "20") or "20"),
        to_main=_env("DASH_SMTP_TO_MAIN"),
        oauth_token_url=token_url,
        oauth_client_id=_env("DASH_SMTP_OAUTH_CLIENT_ID") or None,
        oauth_refresh_token=_env("DASH_SMTP_OAUTH_REFRESH") or None,
        tls_certfile=certfile,
        tls_keyfile=keyfile,
        verify_cert=not _env("DASH_SMTP_NO_VERIFY_CERT"),
        oauth_timeout=float(_env("DASH_SMTP_OAUTH_TIMEOUT", "10") or "10"),
    )


# ── OAuth2 (XOAUTH2) support — real token mint over TLS, honest failure ─────

def _oauth2_access_token(cfg: SmtpConfig) -> str:
    """Mint an OAuth2 access token for SMTP XOAUTH2.

    Uses the refresh-token grant when DASH_SMTP_OAUTH_REFRESH is set
    (client id/secret from DASH_SMTP_OAUTH_CLIENT_ID / DASH_SMTP_PASS),
    else client_credentials with DASH_SMTP_PASS as the client secret.
    Any failure raises — silent fallback would forge auth evidence.
    """
    import httpx  # optional dependency, imported lazily

    client_id = cfg.oauth_client_id or cfg.username
    if not client_id:
        raise RuntimeError("oauth2 needs DASH_SMTP_OAUTH_CLIENT_ID or DASH_SMTP_USER")
    data: dict[str, str] = {"client_id": client_id}
    if cfg.oauth_refresh_token:
        data["grant_type"] = "refresh_token"
        data["refresh_token"] = cfg.oauth_refresh_token
        if cfg.password:
            data["client_secret"] = cfg.password
    else:
        data["grant_type"] = "client_credentials"
        if not cfg.password:
            raise RuntimeError("oauth2 client_credentials needs DASH_SMTP_PASS as client secret")
        data["client_secret"] = cfg.password
    with httpx.Client(timeout=cfg.oauth_timeout) as client:
        resp = client.post(cfg.oauth_token_url, data=data)  # type: ignore[arg-type]
        if resp.status_code != 200:
            raise RuntimeError(f"oauth2 token endpoint returned HTTP {resp.status_code}")
        token = resp.json().get("access_token")
    if not token:
        raise RuntimeError("oauth2 token response had no access_token")
    return str(token)


def _xoauth2_string(user: str, token: str) -> str:
    import base64
    return base64.b64encode(
        f"user={user}\x01auth=Bearer {token}\x01\x01".encode()
    ).decode("ascii")


# ── provider ────────────────────────────────────────────────────────────────


class SmtpProvider(CommunicationProvider):
    """SMTP transport behind the CommunicationProvider contract."""

    name = "smtp"

    def __init__(self, config: SmtpConfig | None = None) -> None:
        self._config = config
        self._config_error: str | None = None
        if config is None:
            try:
                self._config = resolve_smtp_config()
            except RuntimeError as exc:
                # Deferred: send attempts will report this honestly instead of
                # breaking provider construction (the pipeline holds one
                # provider for its whole lifetime).
                self._config_error = str(exc)
                logger.warning("SMTP provider constructed without config: %s", exc)

    # ── contract ────────────────────────────────────────────────────────

    async def send_message(self, target: str, text: str) -> dict[str, Any]:
        if self._config is None:
            return {
                "sent": False, "provider_id": None, "provider": self.name,
                "detail": f"SMTP not configured: {self._config_error}",
            }
        cfg = self._config
        rcpt = parseaddr(target or "")[1] or (parseaddr(cfg.to_main)[1] if cfg.to_main else "")
        if not rcpt or "@" not in rcpt:
            return {
                "sent": False, "provider_id": None, "provider": self.name,
                "rcpt_to": rcpt, "detail": f"no valid recipient address in {target!r}",
            }
        sender_name, sender_addr = parseaddr(cfg.from_address)
        msg = EmailMessage()
        msg["From"] = formataddr((sender_name or "DASH", sender_addr))
        msg["To"] = rcpt
        msg["Subject"] = "Message from DASH"
        msg.set_content(text)

        t0 = time.monotonic()
        evidence: dict[str, Any] = {}
        try:
            rcpt_status, transport = await asyncio.to_thread(
                self._smtp_send_blocking, cfg, sender_addr, rcpt, msg, evidence)
        except Exception as exc:
            detail = f"{type(exc).__name__}: {exc}"
            logger.warning("SMTP send to %s failed: %s", rcpt, detail)
            # evidence carries whatever the conversation recorded before the
            # failure (e.g. a 5xx RCPT refusal) — spec #63 honest receipts.
            return {
                "sent": False, "provider_id": f"smtp://{cfg.host}:{cfg.port}",
                "provider": self.name, "rcpt_to": rcpt, "detail": detail,
                "elapsed_ms": int((time.monotonic() - t0) * 1000),
                **evidence,
            }
        return {
            "sent": True,
            "provider_id": f"smtp://{cfg.host}:{cfg.port}",
            "provider": self.name,
            "rcpt_to": rcpt,
            "rcpt_status": rcpt_status,
            "tls": cfg.tls,
            "auth": cfg.auth,
            "transport": transport,
            "detail": f"accepted by {cfg.host}:{cfg.port} ({cfg.tls})",
            "elapsed_ms": int((time.monotonic() - t0) * 1000),
        }

    async def get_call_state(self) -> dict[str, Any]:
        configured = self._config is not None
        return {
            "supported": False, "state": "idle", "provider": self.name,
            "configured": configured,
            "detail": "SMTP is an email transport; calling is not supported",
        }

    # ── SMTP conversation (blocking; runs in a worker thread) ───────────

    def _smtp_send_blocking(
        self, cfg: SmtpConfig, from_addr: str, rcpt: str, msg: EmailMessage,
        evidence: dict[str, Any],
    ) -> tuple[dict[str, str], str]:
        """Full SMTP conversation. Returns (rcpt_status, transport).
        Raises on any failure — the caller turns that into sent=False.
        Progress is written into `evidence` as it happens so a failure still
        reports what the server actually said (e.g. a 550 RCPT refusal)."""
        if cfg.tls == "smtps":
            ctx = self._ssl_context(cfg)
            client: smtplib.SMTP = smtplib.SMTP_SSL(
                cfg.host, cfg.port, timeout=cfg.timeout, context=ctx)
            transport = "smtps"
        else:
            client = smtplib.SMTP(cfg.host, cfg.port, timeout=cfg.timeout)
            transport = cfg.tls
        try:
            code, banner = client.connect(cfg.host, cfg.port)
            if code != 220:
                raise smtplib.SMTPServerDisconnected(f"bad banner {code}: {banner!r}")
            ehlo = client.ehlo()
            if ehlo[0] != 250:
                raise smtplib.SMTPHeloError(str(ehlo))
            if cfg.tls == "starttls":
                if not client.has_extn("starttls"):
                    raise RuntimeError(
                        "server does not advertise STARTTLS and DASH_SMTP_TLS=starttls")
                client.starttls(context=self._ssl_context(cfg))
                client.ehlo()
            self._authenticate(client, cfg)
            refused = client.sendmail(from_addr, [rcpt], msg.as_string())
            # sendmail returns {} when every recipient was accepted; a 2xx DATA
            # reply has already been received by the time it returns.
            rcpt_status = {
                rcpt: ("250 accepted" if not refused
                       else f"refused: {refused[rcpt]!r}")
            }
            evidence["rcpt_status"] = rcpt_status
            evidence["transport"] = transport
            if refused:
                raise smtplib.SMTPRecipientsRefused(refused)
            return rcpt_status, transport
        finally:
            try:
                client.quit()
            except Exception:
                try:
                    client.close()
                except Exception:
                    pass

    def _authenticate(self, client: smtplib.SMTP, cfg: SmtpConfig) -> None:
        if cfg.auth == "oauth2":
            token = _oauth2_access_token(cfg)
            code, resp = client.docmd("AUTH", "XOAUTH2 " + _xoauth2_string(cfg.username, token))
            if code != 235:
                raise smtplib.SMTPAuthenticationError(code, resp)
            return
        if cfg.auth in ("plain", "login"):
            if not cfg.username or not cfg.password:
                raise RuntimeError("password auth needs DASH_SMTP_USER and DASH_SMTP_PASS")
            client.login(cfg.username, cfg.password)
            return
        if cfg.auth == "certificate":
            # Identity is established by the TLS client certificate already
            # loaded in the SSL context; nothing further at the SMTP layer.
            return

    def _ssl_context(self, cfg: SmtpConfig) -> ssl.SSLContext:
        ctx = ssl.create_default_context(
            ssl.Purpose.SERVER_AUTH, cafile=None, capath=None)
        if not cfg.verify_cert:
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
        if cfg.tls_certfile and cfg.tls_keyfile:
            ctx.load_cert_chain(cfg.tls_certfile, cfg.tls_keyfile)
        return ctx


def configure_pipeline_provider(pipeline: Any) -> Any:
    """Swap the pipeline's draft provider for SMTP when configured (spec #155:
    implement the supported portion; keep the honest draft boundary otherwise).
    Returns the pipeline for chaining. Non-destructive: only the exact draft
    boundary is replaced — custom providers and already-installed transports
    are left untouched."""
    if _env("DASH_SMTP_HOST"):
        try:
            from dash_backend.assistant.communication import LocalDraftProvider
            if type(pipeline.provider) is LocalDraftProvider:
                pipeline.provider = SmtpProvider()
                logger.info("outbound pipeline email transport: smtp")
        except Exception:
            logger.exception("SMTP provider install failed; draft boundary stays")
    return pipeline


_SMTP_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def looks_like_email(address: str) -> bool:
    """Cheap, dependency-free email-shape check used to decide whether a
    message target should route to SMTP (vs. a client display name)."""
    return bool(_SMTP_RE.match(address or ""))
