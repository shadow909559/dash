"""Predictive Problem Detection engine.

Orchestrates the Part 8 flow: OBSERVE (context snapshot + history sample) ->
IDENTIFY PATTERN -> PREDICT PROBLEM -> EXPLAIN EVIDENCE -> SUGGEST ACTION.

Every prediction is produced by a pure predictor that only fires when it has
real evidence, and every result honestly carries likelihood + evidence so
DASH never presents a prediction as a guaranteed fact. Each predictor runs
inside its own guard so one failure can never take down the whole analysis.
"""

from __future__ import annotations

import time
import uuid as _uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from dash_backend.context.engine import ContextEngine, EnvironmentContext, get_context_engine
from dash_backend.logging_config import get_logger
from dash_backend.predictive.history import SampleStore
from dash_backend.predictive.predictors import (
    Prediction,
    predict_dirty_aging,
    predict_disk_fill,
    predict_ram_exhaustion,
    predict_repo_dormancy,
    predict_stale_branches,
    predict_stalled_goals,
)

logger = get_logger(__name__)

_STALLED_GOAL_DAYS = 3


class PredictiveEngine:
    """Samples the live environment and returns forward-looking risks."""

    def __init__(self, store: Optional[SampleStore] = None, context_engine: Optional[ContextEngine] = None) -> None:
        self._store = store or SampleStore()
        self._context_engine = context_engine or get_context_engine()

    # -- public -------------------------------------------------------------

    async def analyze(self, session=None, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Run all predictors over the live snapshot. Never raises."""
        results: List[Prediction] = []
        try:
            snap = await self._context_engine.snapshot_async(session=session, user_id=user_id)
        except Exception as exc:
            logger.debug("Predictive snapshot failed: %s", exc)
            snap = EnvironmentContext()
        results += self._device_predictions(snap)
        results += self._project_predictions(snap)
        if session is not None and user_id is not None:
            stalled = await self._goal_predictions(session, user_id)
            if stalled is not None:
                results.append(stalled)
        results.sort(key=lambda p: (_SEVERITY_WEIGHT.get(p.severity, 0), p.likelihood), reverse=True)
        return {"count": len(results), "predictions": [p.as_dict() for p in results]}

    # -- device -------------------------------------------------------------

    def _device_predictions(self, snap: EnvironmentContext) -> List[Prediction]:
        dev = snap.device or {}
        sample: Dict[str, Any] = {"ts": time.time()}
        for key in ("cpu_pct", "ram_pct", "disk_pct", "disk_free_gb"):
            if dev.get(key) is not None:
                sample[key] = dev[key]
        if len(sample) > 1:
            self._store.append(sample)
        samples = self._store.samples()
        if not samples:
            return []
        out: List[Prediction] = []
        for pred in (predict_ram_exhaustion(samples), predict_disk_fill(samples)):
            if pred is not None:
                out.append(pred)
        return out

    # -- project ------------------------------------------------------------

    def _project_predictions(self, snap: EnvironmentContext) -> List[Prediction]:
        proj = snap.project or {}
        if not proj:
            return []
        out: List[Prediction] = []
        repo = {
            "repo_name": proj.get("repo_name", "project"),
            "branch": proj.get("branch", "?"),
            "changed_files": proj.get("changed_files", 0),
            "repo_root": proj.get("repo_root"),
        }
        for pred in (
            predict_stale_branches(repo),
            predict_repo_dormancy(repo),
        ):
            if pred is not None:
                out.append(pred)
        # Aging uncommitted work: compare with the previous observation.
        prev = self._store.observe_repo(
            repo["repo_name"], repo["branch"], repo["changed_files"]
        )
        aging = predict_dirty_aging(repo, prev)
        if aging is not None:
            out.append(aging)
        return out

    # -- goals --------------------------------------------------------------

    async def _goal_predictions(self, session, user_id: str) -> Optional[Prediction]:
        try:
            from sqlalchemy import select

            from dash_backend.executive.models import Goal

            # PGUUID columns need a uuid object, not the string id routes hand us.
            user_uuid = _uuid.UUID(str(user_id))
            cutoff = datetime.now(timezone.utc) - timedelta(days=_STALLED_GOAL_DAYS)
            res = await session.execute(
                select(Goal)
                .where(Goal.user_id == user_uuid, Goal.status.in_(["pending", "running"]), Goal.created_at < cutoff)
                .order_by(Goal.created_at.asc())
                .limit(10)
            )
            rows = [
                {
                    "name": g.name,
                    "status": g.status,
                    "created_at": g.created_at.isoformat() if g.created_at else "",
                }
                for g in res.scalars().all()
            ]
        except Exception as exc:
            logger.debug("Stalled-goal query failed: %s", exc)
            return None
        return predict_stalled_goals(rows)


_SEVERITY_WEIGHT = {"high": 3, "warning": 2, "info": 1}


_engine: Optional[PredictiveEngine] = None


def get_predictive_engine() -> PredictiveEngine:
    global _engine
    if _engine is None:
        _engine = PredictiveEngine()
    return _engine
