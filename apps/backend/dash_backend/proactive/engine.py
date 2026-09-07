"""Proactive Intelligence engine.

"DASH detects useful context -> DASH proposes useful action."

Guarantees the spec demands (section 5): never annoying. Everything surfaces
through importance thresholds, per-signal cooldowns, deduplication, quiet
hours, and a global disable toggle. Config lives in the user's profile
(preferences.proactive) so it persists and is editable from the UI.
"""

from __future__ import annotations

import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from dash_backend.context.engine import ContextEngine, get_context_engine
from dash_backend.logging_config import get_logger
from dash_backend.predictive.engine import PredictiveEngine, get_predictive_engine
from dash_backend.proactive.signals import Signal, detect_signals
from dash_backend.proactive.state import ProactiveState

logger = get_logger(__name__)

DEFAULT_CONFIG: Dict[str, Any] = {
    "enabled": True,
    "quiet_hours_start": 23,  # 11 PM local
    "quiet_hours_end": 7,  # 7 AM local
    "cooldown_minutes": 120,
    "importance_threshold": 0.55,
}


class ProactiveEngine:
    def __init__(
        self,
        state: Optional[ProactiveState] = None,
        context_engine: Optional[ContextEngine] = None,
        predictive_engine: Optional[PredictiveEngine] = None,
    ):
        self._state = state or ProactiveState()
        self._context_engine = context_engine or get_context_engine()
        self._predictive_engine = predictive_engine

    # -- config (persisted in the profile memory) ----------------------------

    async def load_config(self, session, user_id: str) -> Dict[str, Any]:
        cfg = dict(DEFAULT_CONFIG)
        try:
            from dash_backend.memory import service as memory_service

            mems, _ = await memory_service.get_user_memories(
                session, user_id, limit=1, category="profile"
            )
            for m in mems or []:
                if getattr(m, "source", None) != "personal_profile":
                    continue
                data = _parse_json(m.content)
                prefs = data.get("preferences") or {}
                if isinstance(prefs.get("proactive"), dict):
                    cfg.update(prefs["proactive"])
                break
        except Exception as exc:
            logger.debug("Proactive config load failed, using defaults: %s", exc)
        return cfg

    async def save_config(self, session, user_id: str, updates: Dict[str, Any]) -> Dict[str, Any]:
        from dash_backend.memory import service as memory_service

        cfg = await self.load_config(session, user_id)
        for key in ("enabled", "quiet_hours_start", "quiet_hours_end", "cooldown_minutes", "importance_threshold"):
            if key in updates:
                cfg[key] = updates[key]
        try:
            mems, _ = await memory_service.get_user_memories(session, user_id, limit=1, category="profile")
            profile_mem = next(
                (m for m in mems or [] if getattr(m, "source", None) == "personal_profile"), None
            )
            if profile_mem is not None:
                data = _parse_json(profile_mem.content)
                prefs = data.get("preferences") or {}
                prefs["proactive"] = cfg
                data["preferences"] = prefs
                await memory_service.update_memory(
                    session, profile_mem.id, content=json_dumps(data), importance=0.95
                )
            else:
                await memory_service.save_memory(
                    session,
                    user_id,
                    json_dumps({"preferences": {"proactive": cfg}}),
                    source="personal_profile",
                    category="profile",
                    importance=0.95,
                )
        except Exception as exc:
            logger.debug("Proactive config save failed: %s", exc)
        return cfg

    # -- gating ---------------------------------------------------------------

    @staticmethod
    def in_quiet_hours(cfg: Dict[str, Any]) -> bool:
        start = int(cfg.get("quiet_hours_start", 23))
        end = int(cfg.get("quiet_hours_end", 7))
        hour = datetime.now().hour
        if start <= end:
            return start <= hour < end
        return hour >= start or hour < end  # wraps past midnight

    # -- evaluation -----------------------------------------------------------

    async def evaluate(
        self,
        session=None,
        user_id: Optional[str] = None,
        limit: int = 5,
        config: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Ranked suggestions that pass threshold, dedup and cooldown gates."""
        cfg = config or (await self.load_config(session, user_id) if session is not None and user_id else dict(DEFAULT_CONFIG))
        if not cfg.get("enabled", True):
            return []
        if self.in_quiet_hours(cfg):
            return []

        snap = await self._context_engine.snapshot_async(session=session, user_id=user_id)
        threshold = float(cfg.get("importance_threshold", 0.55))
        cooldown_s = float(cfg.get("cooldown_minutes", 120)) * 60
        now = time.time()

        results: List[Dict[str, Any]] = []
        seen: set = set()
        signals = sorted(detect_signals(snap), key=lambda s: s.importance, reverse=True)
        for sig in signals:
            if sig.importance < threshold or sig.id in seen:
                continue
            seen.add(sig.id)
            last = self._state.last_shown(sig.id)
            if last is not None and (now - last) < cooldown_s:
                continue
            results.append(
                {
                    "id": sig.id,
                    "category": sig.category,
                    "title": sig.title,
                    "message": sig.message,
                    "importance": round(sig.importance, 2),
                    "payload": sig.payload,
                }
            )
            if len(results) >= limit:
                break

        # ── Predictive risk integration ───────────────────────────────────
        # Append high-confidence predictions from the predictive engine as
        # suggestions, respecting the same threshold / cooldown / dedup gates.
        if len(results) < limit:
            results = await self._append_predictive_suggestions(
                results, seen, threshold, cooldown_s, now, limit,
                session=session, user_id=user_id,
            )

        return results

    # -- predictive integration ----------------------------------------------

    _SEVERITY_TO_IMPORTANCE = {
        "high": 0.8,
        "warning": 0.65,
        "info": 0.45,
    }

    async def _append_predictive_suggestions(
        self,
        results: List[Dict[str, Any]],
        seen: set,
        threshold: float,
        cooldown_s: float,
        now: float,
        limit: int,
        *,
        session=None,
        user_id: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """Run the predictive engine and merge qualifying risks into results."""
        try:
            engine = self._predictive_engine or get_predictive_engine()
            analysis = await engine.analyze(session=session, user_id=user_id)
        except Exception as exc:
            logger.debug("Predictive analysis for proactive merge failed: %s", exc)
            return results

        for pred in analysis.get("predictions", []):
            if len(results) >= limit:
                break
            pid = pred.get("id", "")
            stable_id = f"predictive_{pid}"
            if stable_id in seen:
                continue
            importance = self._SEVERITY_TO_IMPORTANCE.get(
                pred.get("severity", "info"), 0.45
            )
            if importance < threshold:
                continue
            last = self._state.last_shown(stable_id)
            if last is not None and (now - last) < cooldown_s:
                continue
            seen.add(stable_id)
            evidence = pred.get("evidence") or []
            evidence_str = "; ".join(evidence[:3]) if evidence else ""
            results.append(
                {
                    "id": stable_id,
                    "category": f"predictive_{pred.get('category', 'unknown')}",
                    "title": pred.get("title", "Predictive risk"),
                    "message": pred.get("message", ""),
                    "importance": round(importance, 2),
                    "payload": {
                        "severity": pred.get("severity"),
                        "likelihood": pred.get("likelihood"),
                        "horizon": pred.get("horizon"),
                        "action": pred.get("action"),
                        "evidence": evidence_str,
                        "confident": pred.get("confident", False),
                    },
                }
            )
        return results

    # -- acknowledgement ------------------------------------------------------

    def record_shown(self, signal_id: str, title: str = "") -> None:
        """Client confirmed the suggestion was displayed -> start cooldown."""
        self._state.record_shown(signal_id, title)

    def history(self, limit: int = 20) -> List[Dict[str, Any]]:
        return self._state.history(limit=limit)


# ---------------------------------------------------------------------------
# JSON helpers (keep imports local to avoid heavy deps at module load)
# ---------------------------------------------------------------------------

def _parse_json(content: Any) -> Dict[str, Any]:
    import json

    if isinstance(content, dict):
        return content
    try:
        data = json.loads(content or "{}")
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def json_dumps(data: Dict[str, Any]) -> str:
    import json

    return json.dumps(data)


_engine: Optional[ProactiveEngine] = None


def get_proactive_engine() -> ProactiveEngine:
    global _engine
    if _engine is None:
        _engine = ProactiveEngine()
    return _engine