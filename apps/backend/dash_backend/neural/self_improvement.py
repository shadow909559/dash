"""Self-Improvement Engine — analyzes failures and successes to improve workflows.

DASH learns from its own execution history:
- Analyze failures (what went wrong, what to avoid)
- Analyze successes (what worked, what to repeat)
- Improve workflows (better planning, better execution)

The engine keeps an in-memory execution log and produces actionable workflow
recommendations. Persistence is additive via the ``memories`` table.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)

CATEGORY_SELF_IMPROVEMENT = "self_improvement"
SOURCE_NEURAL_SELF_IMPROVEMENT = "neural_self_improvement"

# Maximum execution records kept per user.
_MAX_EXECUTION_RECORDS = 200


@dataclass
class ExecutionRecord:
    """A single execution outcome (success or failure)."""

    task: str
    success: bool
    duration_s: float = 0.0
    error: str = ""
    strategy: str = ""
    domain: str = "general"
    ts: float = field(default_factory=time.time)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "task": self.task,
            "success": self.success,
            "duration_s": round(self.duration_s, 2),
            "error": self.error,
            "strategy": self.strategy,
            "domain": self.domain,
            "ts": self.ts,
        }


@dataclass
class WorkflowAnalysis:
    """An analysis of execution history with improvement recommendations."""

    success_rate: float = 0.0
    total_executions: int = 0
    successes: int = 0
    failures: int = 0
    common_failure_patterns: List[str] = field(default_factory=list)
    best_strategies: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "success_rate": round(self.success_rate, 3),
            "total_executions": self.total_executions,
            "successes": self.successes,
            "failures": self.failures,
            "common_failure_patterns": self.common_failure_patterns,
            "best_strategies": self.best_strategies,
            "recommendations": self.recommendations,
        }


class SelfImprovementEngine:
    """Tracks execution outcomes and produces workflow improvements."""

    def __init__(self) -> None:
        self._records: Dict[str, List[ExecutionRecord]] = {}

    # ── Ingestion ──────────────────────────────────────────────────────

    def record(
        self,
        user_id: str,
        task: str,
        success: bool,
        *,
        duration_s: float = 0.0,
        error: str = "",
        strategy: str = "",
        domain: str = "general",
    ) -> None:
        """Record an execution outcome for a user."""
        try:
            record = ExecutionRecord(
                task=task,
                success=bool(success),
                duration_s=float(duration_s or 0.0),
                error=error,
                strategy=strategy,
                domain=domain,
            )
            records = self._records.setdefault(user_id, [])
            records.append(record)
            if len(records) > _MAX_EXECUTION_RECORDS:
                del records[: len(records) - _MAX_EXECUTION_RECORDS]
        except Exception:
            logger.exception("SelfImprovementEngine.record failed")

    # ── Analysis ───────────────────────────────────────────────────────

    def analyze(self, user_id: str, limit: int = 100) -> WorkflowAnalysis:
        """Analyze recent execution history and produce recommendations."""
        records = (self._records.get(user_id) or [])[-limit:]
        if not records:
            return WorkflowAnalysis()

        successes = [r for r in records if r.success]
        failures = [r for r in records if not r.success]
        total = len(records)

        # Failure patterns: group by error keyword.
        failure_patterns: Dict[str, int] = {}
        for r in failures:
            err = (r.error or "").strip().lower()
            if not err:
                err = "unknown error"
            # Use the first meaningful token as a coarse pattern.
            pattern = err.split(":")[0][:60]
            failure_patterns[pattern] = failure_patterns.get(pattern, 0) + 1

        common_failures = sorted(
            failure_patterns.items(),
            key=lambda kv: kv[1],
            reverse=True,
        )[:5]
        common_failure_patterns = [
            f"{pattern} ({count}x)" for pattern, count in common_failures
        ]

        # Best strategies: strategies with high success.
        strategy_stats: Dict[str, Dict[str, float]] = {}
        for r in records:
            if not r.strategy:
                continue
            stats = strategy_stats.setdefault(
                r.strategy,
                {"successes": 0.0, "total": 0.0},
            )
            stats["total"] += 1
            if r.success:
                stats["successes"] += 1

        best_strategies = sorted(
            strategy_stats.items(),
            key=lambda kv: kv[1]["successes"] / max(1.0, kv[1]["total"]),
            reverse=True,
        )[:5]
        best_strategies = [
            f"{strategy} ({int(stats['successes'])}/{int(stats['total'])} ok)"
            for strategy, stats in best_strategies
        ]

        success_rate = len(successes) / total if total else 0.0

        # Recommendations.
        recommendations: List[str] = []
        if success_rate < 0.5:
            recommendations.append("Success rate is low. Consider breaking tasks into smaller, verifiable steps.")
        if common_failures:
            recommendations.append(
                f"Most common failure: '{common_failures[0][0]}'. Add pre-flight checks for this pattern."
            )
        if best_strategies:
            recommendations.append(
                f"Repeat the most successful strategy: '{best_strategies[0]}'."
            )
        slow_successes = [r for r in successes if r.duration_s > 60]
        if slow_successes:
            recommendations.append(
                f"{len(slow_successes)} successful executions took over 60s. Consider parallelizing or caching."
            )
        if not recommendations:
            recommendations.append("Execution history looks healthy. Keep current workflows.")

        return WorkflowAnalysis(
            success_rate=success_rate,
            total_executions=total,
            successes=len(successes),
            failures=len(failures),
            common_failure_patterns=common_failure_patterns,
            best_strategies=best_strategies,
            recommendations=recommendations,
        )

    def recent_records(self, user_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        """Return recent execution records for a user."""
        records = (self._records.get(user_id) or [])[-limit:]
        return [r.to_dict() for r in records]

    # ── Persistence (additive memory writes) ───────────────────────────

    async def persist_analysis(
        self,
        session: Any,
        user_id: str,
    ) -> None:
        """Persist the latest workflow analysis as a memory."""
        try:
            from dash_backend.memory import service as memory_service

            analysis = self.analyze(user_id)
            if analysis.total_executions == 0:
                return
            await memory_service.save_memory(
                session,
                user_id,
                json.dumps(analysis.to_dict(), default=str),
                source=SOURCE_NEURAL_SELF_IMPROVEMENT,
                category=CATEGORY_SELF_IMPROVEMENT,
                importance=0.6,
                memory_type="Summary",
                title="Self-improvement workflow analysis",
            )
        except Exception:
            logger.exception("Failed to persist self-improvement analysis")


# Global singleton
_self_improvement_engine: Optional[SelfImprovementEngine] = None


def get_self_improvement_engine() -> SelfImprovementEngine:
    """Return the global SelfImprovementEngine singleton."""
    global _self_improvement_engine
    if _self_improvement_engine is None:
        _self_improvement_engine = SelfImprovementEngine()
    return _self_improvement_engine