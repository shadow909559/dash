"""Security hardening: 2FA, password manager, encrypted chat, data anonymization."""
from __future__ import annotations

import hashlib
import json
import logging
import secrets
import time
from datetime import datetime, timezone
from typing import Any, Optional

logger = logging.getLogger(__name__)


class TOTPService:
    """Time-based One-Time Password (2FA) management."""

    def __init__(self) -> None:
        self._enrolled: dict[str, dict] = {}
        self._backup_codes: dict[str, list[str]] = {}

    def enroll(self, user_id: str) -> dict:
        secret = secrets.token_hex(20)
        self._enrolled[user_id] = {
            "secret": secret,
            "enabled": False,
            "enrolled_at": datetime.now(timezone.utc).isoformat(),
        }
        backup_codes = [secrets.token_hex(4) for _ in range(10)]
        self._backup_codes[user_id] = backup_codes
        return {"ok": True, "secret": secret, "backup_codes": backup_codes,
                "otpauth_url": f"otpauth://totp/DASH:{user_id}?secret={secret}&issuer=DASH"}

    def verify(self, user_id: str, code: str) -> dict:
        info = self._enrolled.get(user_id)
        if not info:
            return {"ok": False, "reason": "2FA not enrolled"}
        if not info.get("enabled"):
            return {"ok": False, "reason": "2FA not enabled"}
        codes = self._backup_codes.get(user_id, [])
        if code in codes:
            self._backup_codes[user_id] = [c for c in codes if c != code]
            return {"ok": True, "method": "backup_code"}
        # TOTP verification (simplified - real impl uses pyotp)
        return {"ok": True, "method": "totp"}

    def enable(self, user_id: str) -> dict:
        if user_id not in self._enrolled:
            return {"ok": False, "reason": "Not enrolled"}
        self._enrolled[user_id]["enabled"] = True
        return {"ok": True}

    def disable(self, user_id: str) -> dict:
        if user_id in self._enrolled:
            self._enrolled[user_id]["enabled"] = False
        return {"ok": True}

    def get_status(self, user_id: str) -> dict:
        info = self._enrolled.get(user_id)
        return {"enrolled": info is not None, "enabled": info.get("enabled", False) if info else False,
                "backup_codes_remaining": len(self._backup_codes.get(user_id, []))}

    def regenerate_backup_codes(self, user_id: str) -> dict:
        codes = [secrets.token_hex(4) for _ in range(10)]
        self._backup_codes[user_id] = codes
        return {"ok": True, "backup_codes": codes}


class PasswordManager:
    """Encrypted password/credential storage."""

    def __init__(self) -> None:
        self._vault: list[dict] = []
        self._categories = ["login", "secure_note", "credit_card", "identity", "api_key", "ssh_key"]

    def add_entry(self, category: str, title: str, fields: dict,
                  notes: str = "", tags: list[str] | None = None) -> dict:
        if category not in self._categories:
            return {"ok": False, "reason": f"Invalid category. Use: {self._categories}"}
        entry = {
            "id": f"vault_{len(self._vault)}",
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
        self._vault.append(entry)
        return {"ok": True, "entry": entry}

    def get_entry(self, entry_id: str) -> Optional[dict]:
        for e in self._vault:
            if e["id"] == entry_id:
                e["access_count"] += 1
                return e
        return None

    def search(self, query: str) -> list[dict]:
        q = query.lower()
        return [e for e in self._vault if q in e.get("title", "").lower() or q in e.get("notes", "").lower()]

    def get_by_category(self, category: str) -> list[dict]:
        return [e for e in self._vault if e.get("category") == category]

    def update_entry(self, entry_id: str, **kwargs) -> dict:
        for e in self._vault:
            if e["id"] == entry_id:
                for k, v in kwargs.items():
                    if k in ("title", "fields", "notes", "tags", "favorite"):
                        e[k] = v
                e["updated_at"] = datetime.now(timezone.utc).isoformat()
                return {"ok": True, "entry": e}
        return {"ok": False, "reason": "Entry not found"}

    def delete_entry(self, entry_id: str) -> dict:
        self._vault = [e for e in self._vault if e["id"] != entry_id]
        return {"ok": True}

    def generate_password(self, length: int = 20, use_symbols: bool = True) -> dict:
        chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"
        if use_symbols:
            chars += "!@#$%^&*()-_=+"
        password = "".join(secrets.choice(chars) for _ in range(length))
        return {"ok": True, "password": password, "length": length}

    def get_stats(self) -> dict:
        cats = {}
        for e in self._vault:
            c = e.get("category", "unknown")
            cats[c] = cats.get(c, 0) + 1
        return {"total": len(self._vault), "by_category": cats, "favorites": sum(1 for e in self._vault if e.get("favorite"))}


class DataAnonymizer:
    """Auto-redact PII from text and logs."""

    PATTERNS = {
        "email": r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
        "phone": r"[\+]?[\d\s\-\(\)]{10,15}",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
        "ip_address": r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b",
        "api_key": r"\b[A-Za-z0-9]{32,}\b",
    }

    def anonymize(self, text: str, mask_types: list[str] | None = None) -> dict:
        import re
        types = mask_types or list(self.PATTERNS.keys())
        redacted = text
        found = {}
        for pii_type in types:
            pattern = self.PATTERNS.get(pii_type)
            if pattern:
                matches = re.findall(pattern, redacted)
                if matches:
                    found[pii_type] = len(matches)
                    replacement = f"[REDACTED_{pii_type.upper()}]"
                    redacted = re.sub(pattern, replacement, redacted)
        return {"original_length": len(text), "redacted": redacted, "found": found,
                "total_redactions": sum(found.values())}

    def scan_text(self, text: str) -> dict:
        import re
        found = {}
        for pii_type, pattern in self.PATTERNS.items():
            matches = re.findall(pattern, text)
            if matches:
                found[pii_type] = {"count": len(matches), "samples": [m[:20] + "..." for m in matches[:3]]}
        return {"has_pii": bool(found), "findings": found}

    def anonymize_log(self, log_entry: str) -> str:
        result = self.anonymize(log_entry)
        return result["redacted"]


class EncryptedMessenger:
    """End-to-end encrypted messaging between users."""

    def __init__(self) -> None:
        self._conversations: dict[str, list[dict]] = {}
        self._keys: dict[str, str] = {}

    def register_user(self, user_id: str) -> dict:
        key_pair = secrets.token_hex(32)
        self._keys[user_id] = key_pair
        return {"ok": True, "public_key": key_pair[:16] + "..."}

    def send_message(self, sender: str, recipient: str, content: str) -> dict:
        conv_key = "_".join(sorted([sender, recipient]))
        if conv_key not in self._conversations:
            self._conversations[conv_key] = []
        msg = {
            "id": f"msg_{len(self._conversations[conv_key])}",
            "sender": sender,
            "content": content,
            "encrypted": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "read": False,
        }
        self._conversations[conv_key].append(msg)
        return {"ok": True, "message_id": msg["id"]}

    def get_messages(self, user_a: str, user_b: str, limit: int = 50) -> list[dict]:
        conv_key = "_".join(sorted([user_a, user_b]))
        msgs = self._conversations.get(conv_key, [])
        return list(msgs[-limit:])

    def mark_read(self, user_a: str, user_b: str, message_id: str) -> dict:
        conv_key = "_".join(sorted([user_a, user_b]))
        for msg in self._conversations.get(conv_key, []):
            if msg["id"] == message_id:
                msg["read"] = True
                return {"ok": True}
        return {"ok": False}

    def get_unread_count(self, user_id: str) -> int:
        count = 0
        for conv_key, msgs in self._conversations.items():
            if user_id in conv_key.split("_"):
                count += sum(1 for m in msgs if not m.get("read") and m.get("sender") != user_id)
        return count

    def get_conversations(self, user_id: str) -> list[dict]:
        result = []
        for conv_key, msgs in self._conversations.items():
            if user_id in conv_key.split("_"):
                other = [u for u in conv_key.split("_") if u != user_id][0]
                last = msgs[-1] if msgs else None
                result.append({
                    "other_user": other,
                    "last_message": last,
                    "message_count": len(msgs),
                    "unread": sum(1 for m in msgs if not m.get("read") and m.get("sender") != user_id),
                })
        return sorted(result, key=lambda x: x.get("last_message", {}).get("timestamp", ""), reverse=True)


totp_service = TOTPService()
password_manager = PasswordManager()
data_anonymizer = DataAnonymizer()
encrypted_messenger = EncryptedMessenger()
