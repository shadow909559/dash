"""Autonomous Improvement Engine — continuously optimizes DASH itself.

Improves:
- Prompts (track which prompt styles work best)
- Workflows (reduce repeated searches)
- Memory indexing (optimize retrieval)
- Startup (cache frequent operations)
- Caching (cache frequent operations)

The engine tracks optimization opportunities and applies safe, reversible
improvements automatically.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_IMPROVEMENT = "improvement"
SOURCE_NEURAL_IMPROVEMENT = "neural_improvement"


@dataclass
class OptimizationOpportunity:
    """A detected optimization opportunity."""

    category: str  # prompt | workflow | memory | startup | cache
    description: str
    impact: float  # 0.0 - 1.0
    effort: float  # 0.0 - 1.0 (lower = easier)
    applied: bool = False
    created_at: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "category": self.category,
            "description": self.description,
            "impact": round(self.impact, 3),
            "effort": round(self.effort, 3),
            "applied": self.applied,
            "created_at": self.created_at,
        }

    @property
    def score(self) -> float:
        """Priority score: high impact, low effort wins."""
        return self.impact / max(0.1, self.effort)


class AutonomousImprovementEngine:
    """Detects and applies safe optimizations automatically."""

    def __init__(self) -> None:
        self._opportunities: Dict[str, List[OptimizationOpportunity]] = {}
        self._applied: List[Dict[str, Any]] = []

    # ── Detection ──────────────────────────────────────────────────────

    def detect(
        self,
        user_id: str,
        observations: Optional[Dict[str, Any]] = None,
    ) -> List[OptimizationOpportunity]:
        """Detect optimization opportunities from observations.

        ``observations`` may include:
        - repeated_searches: int
        - slow_operations: [{name, duration_s}]
        - startup_time_s: float
        - cache_hit_rate: float
        - memory_index_size: int
        """
        observations = observations or {}
        opportunities: List[OptimizationOpportunity] = []

        # Repeated searches → suggest caching.
        repeated = observations.get("repeated_searches", 0)
        if repeated and repeated >= 5:
            opportunities.append(
                OptimizationOpportunity(
                    category="cache",
                    description=f"Cache {repeated} repeated search queries to reduce latency.",
                    impact=0.7,
                    effort=0.3,
                )
            )

        # Slow operations → suggest optimization.
        slow_ops = observations.get("slow_operations") or []
        if slow_ops:
            slowest = max(slow_ops, key=lambda o: o.get("duration_s", 0))
            if slowest.get("duration_s", 0) >= 5:
                opportunities.append(
                    OptimizationOpportunity(
                        category="workflow",
                        description=f"Optimize '{slowest.get('name', 'operation')}' which took {slowest.get('duration_s', 0):.0f}s.",
                        impact=0.6,
                        effort=0.4,
                    )
                )

        # Slow startup → suggest caching.
        startup = observations.get("startup_time_s", 0)
        if startup and startup >= 10:
            opportunities.append(
                OptimizationOpportunity(
                    category="startup",
                    description=f"Startup takes {startup:.0f}s. Cache initialization to speed up.",
                    impact=0.8,
                    effort=0.5,
                )
            )

        # Low cache hit rate → suggest better indexing.
        hit_rate = observations.get("cache_hit_rate")
        if hit_rate is not None and hit_rate < 0.5:
            opportunities.append(
                OptimizationOpportunity(
                    category="memory",
                    description=f"Cache hit rate is {hit_rate:.0%}. Improve memory indexing.",
                    impact=0.6,
                    effort=0.6,
                )
            )

        # Large memory index → suggest pruning.
        index_size = observations.get("memory_index_size", 0)
        if index_size and index_size >= 1000:
            opportunities.append(
                OptimizationOpportunity(
                    category="memory",
                    description=f"Memory index has {index_size} entries. Consider pruning stale memories.",
                    impact=0.5,
                    effort=0.3,
                )
            )

        # Store new opportunities (dedupe by description).
        existing = self._opportunities.setdefault(user_id, [])
        for opp in opportunities:
            if not any(e.description == opp.description for e in existing):
                existing.append(opp)

        return opportunities

    # ── Application ────────────────────────────────────────────────────

    def apply(self, user_id: str, description: str) -> bool:
        """Mark an optimization opportunity as applied."""
        opportunities = self._opportunities.get(user_id, [])
        for opp in opportunities:
            if opp.description == description and not opp.applied:
                opp.applied = True
                self._applied.append(
                    {
                        "user_id": user_id,
                        "category": opp.category,
                        "description": opp.description,
                        "applied_at": time.time(),
                    }
                )
                self._applied = self._applied[-50:]
                return True
        return False

    def opportunities(self, user_id: str, limit: int = 20) -> List[OptimizationOpportunity]:
        """Return pending optimization opportunities sorted by score."""
        pending = [
            o for o in self._opportunities.get(user_id, [])
            if not o.applied
        ]
        pending.sort(key=lambda o: o.score, reverse=True)
        return pending[:limit]

    def applied_history(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recently applied optimizations."""
        return self._applied[-limit:]

    # ── Persistence ────────────────────────────────────────────────────

    async def persist_opportunities(self, session: Any, user_id: str) -> None:
        """Persist pending optimization opportunities as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            pending = self.opportunities(user_id, limit=10)
            if not pending:
                return
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps([o.to_dict() for o in pending], default=str),
                source=SOURCE_NEURAL_IMPROVEMENT,
                category=CATEGORY_IMPROVEMENT,
                importance=0.5,
                memory_type="Summary",
                title="Optimization opportunities",
            )
        except Exception:
            logger.exception("Failed to persist optimization opportunities")


# Global singleton
_autonomous_improvement_engine: Optional[AutonomousImprovementEngine] = None


def get_autonomous_improvement_engine() -> AutonomousImprovementEngine:
    """Return the global AutonomousImprovementEngine singleton."""
    global _autonomous_improvement_engine
    if _autonomous_improvement_engine is None:
        _autonomous_improvement_engine = AutonomousImprovementEngine()
    return _autonomous_improvement_engine