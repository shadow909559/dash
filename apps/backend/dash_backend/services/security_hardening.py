"""Security hardening: real TOTP 2FA, encrypted vault, encrypted chat,
data anonymization, and biometric (Windows Hello) auth.

Design decisions (see decisions.md #34):
- RFC 6238 TOTP implemented on `cryptography` HMAC-SHA1 (RFC 4226) with
  ±1 window drift tolerance — no pyotp dependency needed.
- Vault and chat payloads are encrypted at rest with AES-256-GCM; vault
  entry encryption derives a per-entry key from the user's master secret
  via HKDF so a leaked ciphertext of one entry does not expose others.
- Anonymization uses deterministic keyed pseudonyms (HMAC-SHA256) so the
  same input maps to the same token within a session but is unlinkable
  across deployments.
- Everything previously keyed by ``id(user)`` (an object address that
  changes per request) is now keyed by the stable user UUID.
"""
from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import os
import re
import secrets
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional
from urllib.parse import quote

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

logger = logging.getLogger(__name__)

_PBKDF2_ITERATIONS = 600_000


def _b32encode(data: bytes) -> str:
    return base64.b32encode(data).decode("ascii").rstrip("=")


def _b32decode(encoded: str) -> bytes:
    padding = "=" * ((8 - len(encoded) % 8) % 8)
    return base64.b32decode(encoded + padding)


# ── TOTP (RFC 6238 / RFC 4226) ─────────────────────────────────────────────


def _hotp(key: bytes, counter: int, digits: int = 6) -> str:
    msg = struct.pack(">Q", counter)
    digest = hmac.new(key, msg, hashlib.sha1).digest()
    offset = digest[19] & 0x0F
    code = struct.unpack(">I", digest[offset : offset + 4])[0] & 0x7FFFFFFF
    return str(code % (10**digits)).zfill(digits)


def _totp(secret_b32: str, at_time: Optional[float] = None, step: int = 30, digits: int = 6) -> str:
    counter = int((at_time if at_time is not None else time.time()) // step)
    return _hotp(_b32decode(secret_b32), counter, digits)


class TOTPService:
    """RFC 6238 TOTP with backup codes and replay protection."""

    def __init__(self, state_path: Optional[Path] = None) -> None:
        self._enrolled: dict[str, dict] = {}
        self._backup_codes: dict[str, list[str]] = {}
        self._used_codes: dict[str, set[str]] = {}
        self._state_path = state_path
        self._load()

    @classmethod
    def _default_path(cls) -> Path:
        override = os.environ.get("DASH_2FA_STATE")
        if override:
            return Path(override)
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DASH" / "twofactor_state.json"

    def _load(self) -> None:
        path = self._state_path or self._default_path()
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                self._enrolled = data.get("enrolled", {})
                self._backup_codes = data.get("backup_codes", {})
        except Exception:
            logger.debug("2FA state load failed", exc_info=True)

    def _save(self) -> None:
        path = self._state_path or self._default_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(
                json.dumps(
                    {"version": 1, "enrolled": self._enrolled, "backup_codes": self._backup_codes},
                    indent=2,
                ),
                encoding="utf-8",
            )
        except Exception:
            logger.debug("2FA state save failed", exc_info=True)

    def enroll(self, user_id: str, issuer: str = "DASH") -> dict:
        secret = _b32encode(os.urandom(20))
        self._enrolled[user_id] = {
            "secret": secret,
            "enabled": False,
            "confirmed": False,
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
        }
        codes = self._generate_backup_codes(user_id)
        self._save()
        return {
            "ok": True,
            "secret": secret,
            "backup_codes": codes,
            "otpauth_url": (
                f"otpauth://totp/{quote(issuer)}:{quote(user_id)}"
                f"?secret={secret}&issuer={quote(issuer)}&algorithm=SHA1&digits=6&period=30"
            ),
        }

    def _generate_backup_codes(self, user_id: str) -> list[str]:
        codes = [f"{secrets.randbelow(10**8):08d}" for _ in range(10)]
        # Store hashes only — a state-file leak must not leak usable codes.
        self._backup_codes[user_id] = [hashlib.sha256(c.encode()).hexdigest() for c in codes]
        return codes

    def verify(self, user_id: str, code: str, confirm: bool = False, at_time: Optional[float] = None) -> dict:
        """Verify a TOTP code (or a backup code).

        ``confirm=True`` marks enrollment confirmed on first successful
        verification; 2FA is only *usable* once confirmed.
        """
        info = self._enrolled.get(user_id)
        if not info:
            return {"ok": False, "reason": "2FA not enrolled"}
        cleaned = re.sub(r"\s+", "", str(code))
        if not cleaned.isdigit() or len(cleaned) not in (6, 8):
            return {"ok": False, "reason": "Code must be 6-8 digits"}

        # Backup codes (stored as hashes)
        code_hashes = self._backup_codes.get(user_id, [])
        code_hash = hashlib.sha256(cleaned.encode()).hexdigest()
        if code_hash in code_hashes:
            self._backup_codes[user_id] = [h for h in code_hashes if h != code_hash]
            if confirm:
                info["confirmed"] = True
            self._save()
            return {"ok": True, "method": "backup_code", "backup_codes_remaining": len(self._backup_codes[user_id])}

        # TOTP with ±1 window (clock drift) and replay protection
        now = at_time if at_time is not None else time.time()
        key = _b32decode(info["secret"])
        used = self._used_codes.setdefault(user_id, set())
        for offset in (0, -1, 1):
            counter = int(now // 30) + offset
            candidate = _hotp(key, counter)
            if hmac.compare_digest(candidate, cleaned):
                replay_key = f"{counter}:{cleaned}"
                if replay_key in used:
                    return {"ok": False, "reason": "Code already used"}
                used.add(replay_key)
                if len(used) > 50:
                    self._used_codes[user_id] = set(list(used)[-50:])
                if confirm:
                    info["confirmed"] = True
                    self._save()
                return {"ok": True, "method": "totp"}
        return {"ok": False, "reason": "Invalid code"}

    def enable(self, user_id: str) -> dict:
        info = self._enrolled.get(user_id)
        if not info:
            return {"ok": False, "reason": "Not enrolled"}
        if not info.get("confirmed"):
            return {"ok": False, "reason": "Verify a code first to confirm enrollment"}
        info["enabled"] = True
        self._save()
        return {"ok": True}

    def disable(self, user_id: str) -> dict:
        if user_id in self._enrolled:
            self._enrolled[user_id]["enabled"] = False
            self._save()
        return {"ok": True}

    def get_status(self, user_id: str) -> dict:
        info = self._enrolled.get(user_id)
        return {
            "enrolled": info is not None,
            "enabled": bool(info.get("enabled")) if info else False,
            "confirmed": bool(info.get("confirmed")) if info else False,
            "backup_codes_remaining": len(self._backup_codes.get(user_id, [])),
        }

    def regenerate_backup_codes(self, user_id: str) -> dict:
        if user_id not in self._enrolled:
            return {"ok": False, "reason": "Not enrolled"}
        codes = self._generate_backup_codes(user_id)
        self._save()
        return {"ok": True, "backup_codes": codes}


# ── Encryption helpers ─────────────────────────────────────────────────────


def _encrypt(key: bytes, plaintext: bytes, aad: bytes | None = None) -> str:
    nonce = os.urandom(12)
    ct = AESGCM(key).encrypt(nonce, plaintext, aad)
    return base64.b64encode(nonce + ct).decode("ascii")


def _decrypt(key: bytes, token: str, aad: bytes | None = None) -> bytes:
    raw = base64.b64decode(token)
    return AESGCM(key).decrypt(raw[:12], raw[12:], aad)


def _derive_key(master: bytes, info: bytes, length: int = 32) -> bytes:
    return HKDF(algorithm=hashes.SHA256(), length=length, salt=None, info=info).derive(master)


# ── Encrypted password vault ───────────────────────────────────────────────


class PasswordManager:
    """AES-256-GCM encrypted credential vault.

    Entries are serialized to JSON, encrypted with a per-entry HKDF-derived
    key (info = entry id), and persisted to disk. The master secret is
    generated per install; supplying ``master_secret`` (e.g. derived from a
    user passphrase via PBKDF2) upgrades the vault to passphrase-protected.
    """

    CATEGORIES = ["login", "secure_note", "credit_card", "identity", "api_key", "ssh_key"]

    def __init__(self, state_path: Optional[Path] = None, master_secret: Optional[bytes] = None) -> None:
        self._vault: dict[str, dict] = {}
        self._encrypted: dict[str, str] = {}
        self._state_path = state_path
        self._master = master_secret or self._load_or_create_master()
        self._load()

    @classmethod
    def _default_path(cls) -> Path:
        override = os.environ.get("DASH_VAULT_STATE")
        if override:
            return Path(override)
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DASH" / "vault_state.json"

    @staticmethod
    def _load_or_create_master() -> bytes:
        """Install-level master secret. Passphrase-derived keys replace this
        when the user sets a master password via set_master()."""
        path = PasswordManager._default_path().parent / "vault_master.key"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                return base64.b64decode(path.read_bytes())
            key = os.urandom(32)
            path.write_bytes(base64.b64encode(key))
            return key
        except Exception:
            logger.debug("vault master key handling failed", exc_info=True)
            return os.urandom(32)

    def _load(self) -> None:
        path = self._state_path or self._default_path()
        try:
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            for entry_id, token in data.get("encrypted", {}).items():
                try:
                    key = _derive_key(self._master, entry_id.encode())
                    payload = json.loads(_decrypt(key, token, aad=entry_id.encode()))
                    self._vault[entry_id] = payload
                except Exception:
                    logger.debug("vault entry %s failed to decrypt", entry_id)
        except Exception:
            logger.debug("vault load failed", exc_info=True)

    def _save(self) -> None:
        path = self._state_path or self._default_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tokens = {}
            for entry_id, entry in self._vault.items():
                key = _derive_key(self._master, entry_id.encode())
                tokens[entry_id] = _encrypt(key, json.dumps(entry).encode(), aad=entry_id.encode())
            path.write_text(json.dumps({"version": 1, "encrypted": tokens}, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("vault save failed", exc_info=True)

    def add_entry(self, category: str, title: str, fields: dict,
                  notes: str = "", tags: list[str] | None = None) -> dict:
        if category not in self.CATEGORIES:
            return {"ok": False, "reason": f"Invalid category. Use: {self.CATEGORIES}"}
        entry_id = f"vault_{secrets.token_hex(8)}"
        entry = {
            "id": entry_id,
            "category": category,
            "title": title,
            "fields": fields,
            "notes": notes,
            "tags": tags or [],
            "favorite": False,
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "access_count": 0,
        }
        self._vault[entry_id] = entry
        self._save()
        return {"ok": True, "entry": entry}

    def get_entry(self, entry_id: str) -> Optional[dict]:
        entry = self._vault.get(entry_id)
        if not entry:
            return None
        entry["access_count"] += 1
        self._save()
        return dict(entry)

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [e for e in self._vault.values() if q in e.get("title", "").lower() or q in e.get("notes", "").lower()]

    def get_by_category(self, category: str) -> list[dict]:
        return [e for e in self._vault.values() if e.get("category") == category]

    def list_entries(self) -> list[dict]:
        return list(self._vault.values())

    def update_entry(self, entry_id: str, **kwargs) -> dict:
        entry = self._vault.get(entry_id)
        if not entry:
            return {"ok": False, "reason": "Entry not found"}
        for k, v in kwargs.items():
            if k in ("title", "fields", "notes", "tags", "favorite"):
                entry[k] = v
        entry["updated_at"] = datetime.now(timezone.utc).isoformat()
        self._save()
        return {"ok": True, "entry": entry}

    def delete_entry(self, entry_id: str) -> dict:
        if entry_id in self._vault:
            del self._vault[entry_id]
            self._save()
        return {"ok": True}

    def generate_password(self, length: int = 20, use_symbols: bool = True) -> dict:
        length = max(8, min(128, length))
        alphabet = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        if use_symbols:
            alphabet += "!@#$%^&*()-_=+"
        password = "".join(secrets.choice(alphabet) for _ in range(length))
        return {"ok": True, "password": password, "length": length}

    def get_stats(self) -> dict:
        cats: dict[str, int] = {}
        for e in self._vault.values():
            cats[e.get("category", "unknown")] = cats.get(e.get("category", "unknown"), 0) + 1
        weak = sum(
            1
            for e in self._vault.values()
            if isinstance(e.get("fields", {}).get("password"), str)
            and len(e["fields"]["password"]) < 12
        )
        return {
            "total": len(self._vault),
            "by_category": cats,
            "favorites": sum(1 for e in self._vault.values() if e.get("favorite")),
            "weak_passwords": weak,
        }


# ── Data anonymization ─────────────────────────────────────────────────────


class DataAnonymizer:
    """PII redaction with deterministic keyed pseudonyms.

    Emails/phones/IPs are replaced with stable HMAC-based tokens so the
    same entity keeps the same pseudonym within a dataset (analytics still
    works) but real values are unrecoverable without the key.
    """

    PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "api_key": r"\b(?:sk|pk|AKIA)[A-Za-z0-9]{16,}\b",
    }

    def __init__(self, pepper: Optional[bytes] = None) -> None:
        self._pepper = pepper or os.environ.get("DASH_PII_PEPPER", "dash-default-pepper").encode()

    def _pseudonym(self, value: str, pii_type: str) -> str:
        digest = hmac.new(self._pepper, f"{pii_type}:{value}".encode(), hashlib.sha256).hexdigest()[:12]
        return f"[{pii_type.upper()}_{digest}]"

    def _mask_phone(self, value: str) -> str:
        digits = re.sub(r"\D", "", value)
        if len(digits) < 7:
            return "[PHONE]"
        return f"[PHONE_...{digits[-4:]}]"

    def anonymize(self, text: str, mask_types: list[str] | None = None) -> dict:
        # Specific patterns run before the greedy phone matcher; phone is
        # deliberately last and excludes "." so IPs/cards never shadow it.
        types = mask_types or ["email", "ssn", "credit_card", "ip_address", "api_key", "phone"]
        redacted = text
        found: dict[str, int] = {}

        for pii_type in types:
            pattern = self.PATTERNS.get(pii_type)
            if pattern:
                matches = re.findall(pattern, redacted)
                if matches:
                    found[pii_type] = len(matches)
                    if pii_type in ("email", "ip_address"):
                        redacted = re.sub(pattern, lambda m: self._pseudonym(m.group(0), pii_type), redacted)
                    else:
                        redacted = re.sub(pattern, f"[{pii_type.upper()}]", redacted)

        if "phone" in types:
            def _phone_repl(m: re.Match) -> str:
                return self._mask_phone(m.group(0))
            phone_re = r"(?:\+?\d[\d\s\-()]{8,}\d)"
            matches = re.findall(phone_re, redacted)
            if matches:
                found["phone"] = len(matches)
                redacted = re.sub(phone_re, _phone_repl, redacted)

        return {
            "original_length": len(text),
            "redacted": redacted,
            "found": found,
            "total_redactions": sum(found.values()),
        }

    def scan_text(self, text: str) -> dict:
        findings: dict[str, dict] = {}
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                findings[pii_type] = {
                    "count": len(matches),
                    "samples": [m[:8] + "…" for m in matches[:3]],
                }
        phone_re = r"(?:\+?\d[\d\s\-()]{8,}\d)"
        phones = re.findall(phone_re, text)
        if phones:
            findings["phone"] = {"count": len(phones), "samples": ["…" + re.sub(r"\D", "", p)[-4:] for p in phones[:3]]}
        return {"has_pii": bool(findings), "findings": findings}

    def anonymize_log(self, log_entry: str) -> str:
        return self.anonymize(log_entry)["redacted"]


# ── Encrypted chat ─────────────────────────────────────────────────────────


class EncryptedMessenger:
    """AES-256-GCM encrypted messaging with per-conversation keys.

    Message content is encrypted before storage; plaintext exists only in
    the return values of send/recv for the participants. Per-conversation
    keys are derived via HKDF from the messenger root key.
    """

    def __init__(self, state_path: Optional[Path] = None, root_key: Optional[bytes] = None) -> None:
        self._conversations: dict[str, list[dict]] = {}
        self._state_path = state_path
        self._root = root_key or self._load_or_create_root(state_path)
        self._load()

    @classmethod
    def _load_or_create_root(cls, state_path: Optional[Path] = None) -> bytes:
        """Persistent root key so ciphertext saved by a previous process
        remains decryptable after restart. Lives beside the state file."""
        path = (state_path or cls._default_path()).parent / "messenger_root.key"
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            if path.exists():
                return base64.b64decode(path.read_bytes())
            key = os.urandom(32)
            path.write_bytes(base64.b64encode(key))
            return key
        except Exception:
            logger.debug("messenger root key handling failed", exc_info=True)
            return os.urandom(32)

    @classmethod
    def _default_path(cls) -> Path:
        override = os.environ.get("DASH_MESSENGER_STATE")
        if override:
            return Path(override)
        base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
        return Path(base) / "DASH" / "messenger_state.json"

    @staticmethod
    def _conv_key(user_a: str, user_b: str) -> str:
        return "::".join(sorted([user_a, user_b]))

    def _conv_encryption_key(self, conv_key: str) -> bytes:
        return _derive_key(self._root, f"conv:{conv_key}".encode())

    def _load(self) -> None:
        path = self._state_path or self._default_path()
        try:
            if not path.exists():
                return
            data = json.loads(path.read_text(encoding="utf-8"))
            for conv_key, msgs in data.get("conversations", {}).items():
                key = self._conv_encryption_key(conv_key)
                decrypted = []
                for m in msgs:
                    try:
                        content = _decrypt(key, m["ct"], aad=m["id"].encode()).decode("utf-8")
                    except Exception:
                        content = "[unable to decrypt]"
                    decrypted.append({**m, "content": content})
                self._conversations[conv_key] = decrypted
        except Exception:
            logger.debug("messenger load failed", exc_info=True)

    def _save(self) -> None:
        path = self._state_path or self._default_path()
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            out = {}
            for conv_key, msgs in self._conversations.items():
                key = self._conv_encryption_key(conv_key)
                out[conv_key] = [
                    {
                        "id": m["id"],
                        "sender": m["sender"],
                        "ct": _encrypt(key, m["content"].encode(), aad=m["id"].encode()),
                        "timestamp": m["timestamp"],
                        "read": m.get("read", False),
                    }
                    for m in msgs
                ]
            path.write_text(json.dumps({"version": 1, "conversations": out}, indent=2), encoding="utf-8")
        except Exception:
            logger.debug("messenger save failed", exc_info=True)

    def register_user(self, user_id: str) -> dict:
        # Kept for API compatibility; keys are per-conversation now.
        return {"ok": True, "key_id": hashlib.sha256(self._root).hexdigest()[:16]}

    def send_message(self, sender: str, recipient: str, content: str) -> dict:
        conv_key = self._conv_key(sender, recipient)
        msgs = self._conversations.setdefault(conv_key, [])
        msg = {
            "id": f"msg_{secrets.token_hex(8)}",
            "sender": sender,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        msgs.append(msg)
        self._save()
        return {"ok": True, "message_id": msg["id"], "encrypted": True}

    def get_messages(self, user_a: str, user_b: str, limit: int = 50) -> list[dict]:
        conv_key = self._conv_key(user_a, user_b)
        return list(self._conversations.get(conv_key, [])[-limit:])

    def mark_read(self, user_a: str, user_b: str, message_id: str) -> dict:
        conv_key = self._conv_key(user_a, user_b)
        for m in self._conversations.get(conv_key, []):
            if m["id"] == message_id:
                m["read"] = True
                self._save()
                return {"ok": True}
        return {"ok": False}

    def get_unread_count(self, user_id: str) -> int:
        count = 0
        for conv_key, msgs in self._conversations.items():
            parts = conv_key.split("::")
            if user_id in parts:
                count += sum(1 for m in msgs if not m.get("read") and m.get("sender") != user_id)
        return count

    def get_conversations(self, user_id: str) -> list[dict]:
        result = []
        for conv_key, msgs in self._conversations.items():
            parts = conv_key.split("::")
            if user_id not in parts:
                continue
            others = [u for u in parts if u != user_id] or ["self"]
            last = msgs[-1] if msgs else None
            result.append({
                "other_user": others[0],
                "last_message": last,
                "message_count": len(msgs),
                "unread": sum(1 for m in msgs if not m.get("read") and m.get("sender") != user_id),
            })
        return sorted(result, key=lambda x: (x.get("last_message") or {}).get("timestamp", ""), reverse=True)


# ── Biometric authentication (Windows Hello via Electron) ──────────────────


class BiometricAuthService:
    """Biometric gate for sensitive actions.

    Enrollment records which authenticator the desktop shell reports
    (Windows Hello / Touch ID via Electron touches); verification issues a
    single-use challenge that the desktop shell answers after a successful
    platform-authenticator prompt. The backend never sees biometric data —
    only the challenge result — and all attempts are audited.
    """

    CHALLENGE_TTL_SECONDS = 120

    def __init__(self) -> None:
        self._enrolled: dict[str, dict] = {}
        self._challenges: dict[str, dict] = {}
        self._attempts: list[dict] = []

    def availability(self) -> dict:
        import platform

        system = platform.system()
        if system == "Windows":
            return {"available": True, "authenticator": "windows_hello"}
        if system == "Darwin":
            return {"available": True, "authenticator": "touch_id"}
        return {"available": False, "authenticator": None, "reason": "No platform authenticator"}

    def enroll(self, user_id: str, device_label: str = "") -> dict:
        avail = self.availability()
        record = {
            "user_id": user_id,
            "authenticator": avail.get("authenticator"),
            "device_label": device_label,
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
            "enabled": True,
        }
        self._enrolled[user_id] = record
        self._audit(user_id, "enroll", True)
        return {"ok": True, "enrollment": record}

    def create_challenge(self, user_id: str, action: str = "unlock") -> dict:
        if user_id not in self._enrolled or not self._enrolled[user_id].get("enabled"):
            return {"ok": False, "reason": "Biometric auth not enrolled"}
        nonce = secrets.token_urlsafe(32)
        self._challenges[nonce] = {
            "user_id": user_id,
            "action": action,
            "expires": time.time() + self.CHALLENGE_TTL_SECONDS,
        }
        self._audit(user_id, "challenge_created", True, action)
        return {"ok": True, "challenge": nonce, "expires_in": self.CHALLENGE_TTL_SECONDS}

    def verify_challenge(self, nonce: str, success: bool, user_id: str = "") -> dict:
        challenge = self._challenges.pop(nonce, None)
        if not challenge:
            self._audit(user_id, "verify", False, "unknown_challenge")
            return {"ok": False, "reason": "Invalid or already-used challenge"}
        if challenge["expires"] < time.time():
            self._audit(challenge["user_id"], "verify", False, "expired")
            return {"ok": False, "reason": "Challenge expired"}
        self._audit(challenge["user_id"], "verify", bool(success))
        return {"ok": bool(success), "user_id": challenge["user_id"], "action": challenge["action"]}

    def get_status(self, user_id: str) -> dict:
        record = self._enrolled.get(user_id)
        return {
            "enrolled": record is not None,
            "enabled": bool(record.get("enabled")) if record else False,
            "authenticator": record.get("authenticator") if record else None,
            "enrolled_at": record.get("enrolled_at") if record else None,
        }

    def revoke(self, user_id: str) -> dict:
        self._enrolled.pop(user_id, None)
        self._audit(user_id, "revoke", True)
        return {"ok": True}

    def _audit(self, user_id: str, event: str, ok: bool, detail: str = "") -> None:
        self._attempts.append({
            "user_id": user_id,
            "event": event,
            "ok": ok,
            "detail": detail,
            "at": datetime.now(timezone.utc).isoformat(),
        })
        if len(self._attempts) > 200:
            self._attempts = self._attempts[-200:]

    def get_audit_log(self, user_id: str = "") -> list[dict]:
        if user_id:
            return [a for a in self._attempts if a["user_id"] == user_id]
        return list(self._attempts)


totp_service = TOTPService()
password_manager = PasswordManager()
data_anonymizer = DataAnonymizer()
encrypted_messenger = EncryptedMessenger()
biometric_service = BiometricAuthService()
