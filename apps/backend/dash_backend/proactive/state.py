"""Persistent state for proactive suggestions.

Cooldowns and shown-history survive restarts so DASH never re-suggests the
same thing every launch. Stored as a small JSON file next to the identity
file (override with DASH_PROACTIVE_STATE for tests / multi-user setups).
"""

from __future__ import annotations

import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

_MAX_HISTORY = 200


def default_state_path() -> Path:
    override = os.environ.get("DASH_PROACTIVE_STATE")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DASH" / "proactive_state.json"


class ProactiveState:
    """Thread-safe-ish JSON persistence for cooldown timestamps + history."""

    def __init__(self, path: Optional[Path] = None) -> None:
        self._path = Path(path) if path else default_state_path()

    # -- persistence --------------------------------------------------------

    def _load(self) -> Dict[str, Any]:
        try:
            if self._path.exists():
                with open(self._path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    return data
        except Exception as exc:
            logger.debug("Proactive state unreadable (%s); starting fresh", exc)
        return {"cooldowns": {}, "history": []}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
        except Exception as exc:
            logger.debug("Proactive state write failed: %s", exc)

    # -- api ----------------------------------------------------------------

    def last_shown(self, signal_id: str) -> Optional[float]:
        """Unix timestamp the signal was last acknowledged, or None."""
        data = self._load()
        return data.get("cooldowns", {}).get(signal_id)

    def record_shown(self, signal_id: str, title: str = "") -> None:
        """Record that a suggestion was surfaced (starts its cooldown)."""
        data = self._load()
        data.setdefault("cooldowns", {})[signal_id] = time.time()
        history = data.setdefault("history", [])
        history.append(
            {"id": signal_id, "title": title, "shown_at": time.time()}
        )
        data["history"] = history[-_MAX_HISTORY:]
        self._save(data)

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        data = self._load()
        return list(reversed(data.get("history", [])))[:limit]

    def clear(self) -> None:
        self._save({"cooldowns": {}, "history": []})