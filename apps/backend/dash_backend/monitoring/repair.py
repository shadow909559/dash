"""DASH automatic repair routines.

Triggered by the diagnostics service or developer dashboard. Each routine is
best-effort and never crashes the app. Repair actions are logged to the audit
log so they are always traceable.
"""

from __future__ import annotations

import asyncio
import gc
import logging
import shutil
import tempfile
from typing import Any, Callable, Dict, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class RepairRoutine:
    """Runs a set of best-effort repair actions."""

    REPAIR_ACTIONS: Dict[str, Callable[[], Dict[str, Any]]] = {}

    def __init__(self) -> None:
        self._register_defaults()

    def _register_defaults(self) -> None:
        self.REPAIR_ACTIONS = {
            "flush_temp": self._flush_temp,
            "force_gc": self._force_gc,
            "clear_stale_cache": self._clear_stale_cache,
        }

    # ── Repair actions ──────────────────────────────────────────

    def _flush_temp(self) -> Dict[str, Any]:
        """Remove leftover temp files from DASH's temp directory."""
        removed = 0
        try:
            temp_dir = tempfile.gettempdir()
            for entry in shutil.os.scandir(temp_dir):
                try:
                    if entry.name.startswith("dash_") and entry.is_file():
                        entry_path = entry.path
                        shutil.os.remove(entry_path)
                        removed += 1
                except Exception:
                    continue
            return {"action": "flush_temp", "removed": removed, "status": "ok"}
        except Exception as exc:
            return {"action": "flush_temp", "status": "error", "error": str(exc)}

    def _force_gc(self) -> Dict[str, Any]:
        """Trigger Python & (if available) asyncio GC."""
        before = len(gc.get_objects())
        collected = gc.collect()
        return {"action": "force_gc", "collected": collected, "objects_before": before, "status": "ok"}

    def _clear_stale_cache(self) -> Dict[str, Any]:
        """Best-effort stale cache cleanup (only DASH-owned caches)."""
        try:
            from dash_backend.cache import cache_manager  # type: ignore
            if hasattr(cache_manager, "clear_stale"):
                result = cache_manager.clear_stale()
                return {"action": "clear_stale_cache", "status": "ok", "details": result}
            return {"action": "clear_stale_cache", "status": "skipped", "details": "no clear_stale"}
        except Exception as exc:
            return {"action": "clear_stale_cache", "status": "error", "error": str(exc)}

    # ── Public API ──────────────────────────────────────────────

    async def run(self, action: str) -> Dict[str, Any]:
        """Run a single repair action by name."""
        handler = self.REPAIR_ACTIONS.get(action)
        if handler is None:
            return {"action": action, "status": "unknown", "error": f"no repair '{action}'"}

        # Run blocking action in a thread to avoid stalling the event loop.
        result = await asyncio.get_event_loop().run_in_executor(None, handler)
        logger.info("[Repair] Ran repair '%s' -> %s", action, result.get("status"))
        return result

    async def run_all(self) -> Dict[str, Any]:
        """Run every registered repair action."""
        results = {}
        for name in self.REPAIR_ACTIONS:
            try:
                results[name] = await self.run(name)
            except Exception as exc:  # pragma: no cover
                results[name] = {"action": name, "status": "error", "error": str(exc)}
        return results

    def list(self) -> Dict[str, Any]:
        """List available repair actions."""
        return {
            "actions": list(self.REPAIR_ACTIONS.keys()),
            "count": len(self.REPAIR_ACTIONS),
        }


_routine: Optional[RepairRoutine] = None


def get_repair_routine() -> RepairRoutine:
    global _routine
    if _routine is None:
        _routine = RepairRoutine()
    return _routine
