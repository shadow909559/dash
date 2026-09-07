"""Persistent device-sample history for predictive problem detection.

Predictions need history: a single reading can never show a *trend*. This
store keeps rolling device samples (CPU / RAM / disk) plus per-repository
working-tree observations so DASH can honestly estimate things like
"disk is filling at the current rate" or "these changes have been
uncommitted for 3 days". Nothing here ever fabricates a trend — callers
decide whether the accumulated history is enough.

Stored as a small JSON file next to the identity file (override with
DASH_PREDICTIVE_STATE for tests / multi-user setups).
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

_MAX_SAMPLES = 500          # keep at most this many device samples
_MAX_SAMPLE_AGE_DAYS = 30   # drop samples older than this


def default_state_path() -> Path:
    override = os.environ.get("DASH_PREDICTIVE_STATE")
    if override:
        return Path(override)
    base = os.environ.get("LOCALAPPDATA") or str(Path.home() / "AppData" / "Local")
    return Path(base) / "DASH" / "predictive_state.json"


class SampleStore:
    """Thread-safe-ish JSON persistence for device samples + repo observations."""

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
            logger.debug("Predictive state unreadable (%s); starting fresh", exc)
        return {"samples": [], "repos": {}}

    def _save(self, data: Dict[str, Any]) -> None:
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            fd, tmp = tempfile.mkstemp(dir=str(self._path.parent), suffix=".tmp")
            with os.fdopen(fd, "w", encoding="utf-8") as f:
                json.dump(data, f)
            os.replace(tmp, self._path)
        except Exception as exc:
            logger.debug("Predictive state write failed: %s", exc)

    # -- device samples -----------------------------------------------------

    def append(self, sample: Dict[str, Any]) -> None:
        """Record one device reading: {'ts': float, 'cpu_pct': float|None,
        'ram_pct': float|None, 'disk_pct': float|None, 'disk_free_gb': float|None}."""
        data = self._load()
        samples = data.setdefault("samples", [])
        now = sample.get("ts") or time.time()
        cutoff = now - _MAX_SAMPLE_AGE_DAYS * 86400
        samples = [s for s in samples if (s.get("ts") or 0) >= cutoff]
        samples.append(sample)
        data["samples"] = samples[-_MAX_SAMPLES:]
        self._save(data)

    def samples(self, limit: int = _MAX_SAMPLES) -> List[Dict[str, Any]]:
        data = self._load()
        return list(data.get("samples", []))[-limit:]

    def clear_samples(self) -> None:
        data = self._load()
        data["samples"] = []
        self._save(data)

    # -- repository working-tree observations --------------------------------

    def observe_repo(self, repo: str, branch: str, changed_files: int) -> Optional[Dict[str, Any]]:
        """Record the repo's working-tree state. Returns the previous
        observation (if the repo was seen before) so callers can detect
        how long changes have been outstanding."""
        data = self._load()
        repos = data.setdefault("repos", {})
        now = time.time()
        prev = repos.get(repo)
        current = {"branch": branch, "changed_files": changed_files, "seen_at": now}
        if changed_files > 0:
            if prev and prev.get("branch") == branch and prev.get("changed_files", 0) > 0:
                current["dirty_since"] = prev.get("dirty_since", prev.get("seen_at", now))
            else:
                current["dirty_since"] = now
        repos[repo] = current
        # Bound growth: keep only the most recently seen repos.
        if len(repos) > 50:
            for old in sorted(repos, key=lambda r: repos[r].get("seen_at", 0))[: len(repos) - 50]:
                repos.pop(old, None)
        self._save(data)
        return prev

    def clear(self) -> None:
        self._save({"samples": [], "repos": {}})
