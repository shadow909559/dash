"""Secrets Manager - Secure storage and retrieval of API keys and tokens."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, Optional

from cryptography.fernet import Fernet

logger = logging.getLogger(__name__)


class SecretsManager:
    def __init__(self, secrets_path: Optional[str] = None):
        self._path = Path(secrets_path or Path.home() / ".dash" / "secrets.json")
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._key = self._load_or_create_key()
        self._cipher = Fernet(self._key)
        self._secrets: Dict[str, str] = {}
        self._load()

    def _load_or_create_key(self) -> bytes:
        key_path = self._path.parent / ".key"
        if key_path.exists():
            return key_path.read_bytes()
        key = Fernet.generate_key()
        key_path.write_bytes(key)
        return key

    def _load(self) -> None:
        if self._path.exists():
            try:
                encrypted = self._path.read_bytes()
                decrypted = self._cipher.decrypt(encrypted)
                self._secrets = json.loads(decrypted.decode())
            except Exception:
                self._secrets = {}

    def _save(self) -> None:
        data = json.dumps(self._secrets).encode()
        encrypted = self._cipher.encrypt(data)
        self._path.write_bytes(encrypted)

    def set(self, key: str, value: str) -> None:
        self._secrets[key] = value
        self._save()

    def get(self, key: str) -> Optional[str]:
        return self._secrets.get(key)

    def delete(self, key: str) -> bool:
        result = self._secrets.pop(key, None) is not None
        if result:
            self._save()
        return result

    def list_keys(self) -> list:
        return list(self._secrets.keys())


_secrets_manager: Optional[SecretsManager] = None


def get_secrets_manager() -> SecretsManager:
    global _secrets_manager
    if _secrets_manager is None:
        _secrets_manager = SecretsManager()
    return _secrets_manager
