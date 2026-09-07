"""Update Detector - Detect software updates autonomously."""

from __future__ import annotations

import asyncio
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class UpdateDetector:
    def __init__(self):
        self._running = False

    async def start(self) -> None:
        self._running = True

    async def stop(self) -> None:
        self._running = False

    async def check(self) -> List[Dict[str, Any]]:
        updates = []
        try:
            import subprocess
            r = subprocess.run(["winget", "upgrade"], capture_output=True, text=True, timeout=30)
            for line in r.stdout.splitlines():
                if "|" in line and "Name" not in line:
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 3:
                        updates.append({"name": parts[0], "current": parts[1], "available": parts[2]})
        except Exception:
            pass
        return updates


_update_detector: Optional[UpdateDetector] = None


def get_update_detector() -> UpdateDetector:
    global _update_detector
    if _update_detector is None:
        _update_detector = UpdateDetector()
    return _update_detector
