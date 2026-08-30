"""NeuralCore — the central AI Brain for DASH.

Everything passes through this single entrypoint: voice, memory, desktop,
browser, coding, research, automation, phone, and plugins.

NeuralCore processes a request through a multi-step cognitive pipeline:

1. Goal Understanding  — infer the underlying goal + sub-goals
2. Multi-Step Reasoning  — break into smaller tasks, estimate complexity/time
3. Confidence Assessment — internal confidence/risk/missing-info scoring
4. Self-Verification    — verify safety before, result after
5. User-Model Learning   — record observations and habits
6. Predictive Engine     — update sequence patterns for future predictions
7. Long-Term Goal Monitor — auto-update tracked goals
8. Prioritization       — classify the request's priority tier
9. Self-Improvement     — record execution outcome for workflow learning
10. Proactive Check      — surface low-risk helpful suggestions

The pipeline is additive and non-breaking: existing pipeline output passes
through unchanged, with neural metadata attached as a sibling key.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.neural.confidence import (
    ConfidenceAssessment,
    ConfidenceEngine,
    get_confidence_engine,
)
from dash_backend.neural.goal_understanding import (
    GoalUnderstandingEngine,
    get_goal_understanding_engine,
)
from dash_backend.neural.verification import get_verification_engine
from dash_backend.neural.user_model import UserModelEngine, get_user_model_engine
from dash_backend.neural.predictive import PredictiveEngine, get_predictive_engine
from dash_backend.neural.proactive import ProactiveEngine, get_proactive_engine
from dash_backend.neural.long_term_goals import (
    LongTermGoalsEngine,
    get_long_term_goals_engine,
)
from dash_backend.neural.prioritization import (
    PrioritizationEngine,
    get_prioritization_engine,
)
from dash_backend.neural.self_improvement import (
    SelfImprovementEngine,
    get_self_improvement_engine,
)
from dash_backend.neural.personality import PersonalityEngine
from dash_backend.neural.context_engine import (
    ContextEngine,
    get_context_engine,
)
from dash_backend.neural.continuity import (
    ContinuityEngine,
    get_continuity_engine,
)
from dash_backend.neural.self_monitoring import (
    SelfMonitoringEngine,
    get_self_monitoring_engine,
)
from dash_backend.neural.error_handling import (
    ErrorHandlingEngine,
    get_error_handling_engine,
)
from dash_backend.neural.project_awareness import (
    ProjectAwarenessEngine,
    get_project_awareness_engine,
)
from dash_backend.neural.multitasking import (
    MultitaskingEngine,
    get_multitasking_engine,
)
from dash_backend.neural.productivity import (
    ProductivityEngine,
    get_productivity_engine,
)
from dash_backend.neural.autonomous_improvement import (
    AutonomousImprovementEngine,
    get_autonomous_improvement_engine,
)

logger = get_logger(__name__)


@dataclass
class NeuralProcessResult:
    """The unified output of the NeuralCore pipeline.

    This is the single object returned by ``NeuralCore.process()``. The
    ``response`` field contains the existing pipeline result; neural metadata is
    additive metadata that the UI may choose to display or hide.
    """

    response: Dict[str, Any]
    understanding: Optional[Dict[str, Any]] = None
    confidence: Optional[Dict[str, Any]] = None
    verification: Optional[Dict[str, Any]] = None
    priority: Optional[Dict[str, Any]] = None
    prediction: Optional[Dict[str, Any]] = None
    proactive: List[Dict[str, Any]] = field(default_factory=list)
    goal_updates: List[Dict[str, Any]] = field(default_factory=list)
    execution_recorded: bool = False
    personality: Optional[Dict[str, Any]] = None
    context: Optional[Dict[str, Any]] = None
    continuity: Optional[Dict[str, Any]] = None
    health: Optional[Dict[str, Any]] = None
    error_explanation: Optional[Dict[str, Any]] = None
    project: Optional[Dict[str, Any]] = None
    productivity: Optional[Dict[str, Any]] = None
    improvements: List[Dict[str, Any]] = field(default_factory=list)
    processing_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Full serializable result (response + additive neural metadata)."""
        return {
            "response": self.response,
            "neural": {
                "understanding": self.understanding,
                "confidence": self.confidence,
                "verification": self.verification,
                "priority": self.priority,
                "prediction": self.prediction,
                "proactive": self.proactive,
                "goal_updates": self.goal_updates,
                "execution_recorded": self.execution_recorded,
                "personality": self.personality,
                "context": self.context,
                "continuity": self.continuity,
                "health": self.health,
                "error_explanation": self.error_explanation,
                "project": self.project,
                "productivity": self.productivity,
                "improvements": self.improvements,
                "processing_ms": round(self.processing_ms, 2),
            },
        }

    @property
    def should_ask_clarification(self) -> bool:
        """Whether the pipeline determined clarification is needed before acting."""
        if not self.confidence:
            return False
        missing_info = self.confidence.get("required_clarification") or []
        return bool(missing_info)


class NeuralCore:
    """Central AI Brain orchestrating all neural engines.

    Designed as a thin, additive wrapper around the existing pipeline so DASH
    behaves like an intelligent entity without breaking existing behavior.
    """

    def __init__(
        self,
        session: Any,
        *,
        confidence_engine: Optional[ConfidenceEngine] = None,
        goal_engine: Optional[GoalUnderstandingEngine] = None,
        verification_engine: Optional[VerificationEngine] = None,
        user_model: Optional[UserModelEngine] = None,
        predictive: Optional[PredictiveEngine] = None,
        proactive: Optional[ProactiveEngine] = None,
        goals: Optional[LongTermGoalsEngine] = None,
        prioritization: Optional[PrioritizationEngine] = None,
        self_improvement: Optional[SelfImprovementEngine] = None,
        context_engine: Optional[ContextEngine] = None,
        continuity: Optional[ContinuityEngine] = None,
        self_monitoring: Optional[SelfMonitoringEngine] = None,
        error_handling: Optional[ErrorHandlingEngine] = None,
        project_awareness: Optional[ProjectAwarenessEngine] = None,
        multitasking: Optional[MultitaskingEngine] = None,
        productivity: Optional[ProductivityEngine] = None,
        autonomous_improvement: Optional[AutonomousImprovementEngine] = None,
    ) -> None:
        self.confidence_engine = confidence_engine or get_confidence_engine()
        self.goal_engine = goal_engine or get_goal_understanding_engine()
        self.verification_engine = verification_engine or get_verification_engine()
        self.user_model = user_model or get_user_model_engine()
        self.predictive = predictive or get_predictive_engine()
        self.proactive = proactive or get_proactive_engine()
        self.goals = goals or get_long_term_goals_engine()
        self.prioritization = prioritization or get_prioritization_engine()
        self.self_improvement = self_improvement or get_self_improvement_engine()
        self.personality = PersonalityEngine(session)
        self.context_engine = context_engine or get_context_engine()
        self.continuity = continuity or get_continuity_engine()
        self.self_monitoring = self_monitoring or get_self_monitoring_engine()
        self.error_handling = error_handling or get_error_handling_engine()
        self.project_awareness = project_awareness or get_project_awareness_engine()
        self.multitasking = multitasking or get_multitasking_engine()
        self.productivity = productivity or get_productivity_engine()
        self.autonomous_improvement = autonomous_improvement or get_autonomous_improvement_engine()

    # ── Primary entrypoint ─────────────────────────────────────────────

    def process(
        self,
        query: str,
        user_id: str,
        *,
        response: Optional[Dict[str, Any]] = None,
        context: Optional[Dict[str, Any]] = None,
        execution_success: Optional[bool] = None,
        execution_error: str = "",
        execution_duration_s: float = 0.0,
    ) -> NeuralProcessResult:
        """Process a user request through the full neural pipeline.

        Args:
            query: The user's raw request.
            user_id: The user's ID.
            response: Optional existing pipeline output to pass through.
            context: Optional execution context (system state, tools, etc.).
            execution_success: Optional outcome to feed self-improvement.
            execution_error: Error string when execution failed.
            execution_duration_s: Execution duration in seconds.

        Returns:
            A ``NeuralProcessResult`` containing the passed-through response
            plus additive neural metadata.
        """
        start = time.perf_counter()
        context = context or {}
        response = response or {}

        # 1. Goal understanding.
        understanding = self._understand(query)

        # 2. Confidence assessment.
        confidence = self._assess(query, understanding)

        # 3. User-model observation + habit learning.
        self._learn(query, user_id, understanding, context)

        # 4. Predictive sequence learning.
        self._observe_sequence(query, user_id, understanding)

        # 5. Long-term goal monitoring.
        goal_updates = self._monitor_goals(query, user_id, understanding)

        # 6. Prioritization.
        priority = self._prioritize(query, understanding, context)

        # 7. Self-improvement execution record.
        execution_recorded = False
        if execution_success is not None:
            self._record_execution(
                query,
                user_id,
                execution_success,
                execution_error=execution_error,
                duration_s=execution_duration_s,
                domain=understanding.get("domains", ["general"])[0],
            )
            execution_recorded = True

        # 8. Proactive suggestions (from system state).
        proactive = self._generate_proactive(context, user_id)

        # 9. Prediction for follow-up offers.
        prediction = self._predict(query, user_id, understanding)

        # 10. Personality learning + style application.
        personality = self._learn_personality(query, user_id, context)

        # 11. Context gathering.
        context_snapshot = self._gather_context(query, user_id, context)

        # 12. Continuity snapshot.
        continuity = self._snapshot_continuity(query, user_id, context)

        # 13. Health check.
        health = self._check_health(context)

        # 14. Error explanation (if execution failed).
        error_explanation = None
        if execution_success is False and execution_error:
            error_explanation = self._explain_error(execution_error)

        # 15. Project awareness.
        project = self._project_awareness(context)

        # 16. Productivity tracking.
        productivity = self._track_productivity(query, user_id, context)

        # 17. Autonomous improvement detection.
        improvements = self._detect_improvements(user_id, context)

        processing_ms = (time.perf_counter() - start) * 1000.0

        return NeuralProcessResult(
            response=response,
            understanding=understanding,
            confidence=confidence,
            verification=self._current_verification(confidence),
            priority=priority,
            prediction=prediction,
            proactive=proactive,
            goal_updates=goal_updates,
            execution_recorded=execution_recorded,
            personality=personality,
            context=context_snapshot,
            continuity=continuity,
            health=health,
            error_explanation=error_explanation,
            project=project,
            productivity=productivity,
            improvements=improvements,
            processing_ms=processing_ms,
        )

    # ── Pipeline stages ────────────────────────────────────────────────

    def _understand(self, query: str) -> Dict[str, Any]:
        try:
            u = self.goal_engine.understand(query)
            return u.to_dict()
        except Exception:
            logger.exception("NeuralCore goal-understanding failed")
            return {"goal": query or "", "category": "general", "sub_goals": []}

    def _assess(self, query: str, understanding: Dict[str, Any]) -> Dict[str, Any]:
        try:
            assessment = self.confidence_engine.assess_query(query)
            # Blend goal-understanding confidence into the final assessment.
            goal_conf = understanding.get("confidence", 0.5) or 0.5
            assessment.confidence = min(0.98, (assessment.confidence * 0.7) + (goal_conf * 0.3))
            return assessment.to_dict()
        except Exception:
            logger.exception("NeuralCore confidence assessment failed")
            return ConfidenceAssessment().to_dict()

    def _learn(
        self,
        query: str,
        user_id: str,
        understanding: Dict[str, Any],
        context: Dict[str, Any],
    ) -> None:
        try:
            self.user_model.observe(
                user_id,
                "command",
                {
                    "command": query,
                    "domains": understanding.get("domains") or [],
                },
            )
            # Record tool/folder usage from context if present.
            tool = context.get("tool") or context.get("used_tool")
            if tool:
                self.user_model.observe(user_id, "tool", {"tool": tool})
            folder = context.get("folder") or context.get("current_folder")
            if folder:
                self.user_model.observe(user_id, "folder", {"folder": folder})
            folder = context.get("contact") or context.get("person")
            if folder:
                self.user_model.observe(user_id, "contact", {"name": folder})
            langs = context.get("languages")
            if langs:
                self.user_model.observe(user_id, "coding", {"languages": langs})
        except Exception:
            logger.exception("NeuralCore user-model learning failed")

    def _observe_sequence(
        self,
        query: str,
        user_id: str,
        understanding: Dict[str, Any],
    ) -> None:
        try:
            action = understanding.get("category") or "general"
            self.predictive.observe(
                user_id,
                action,
                metadata={"query": query[:200]},
            )
        except Exception:
            logger.exception("NeuralCore predictive observation failed")

    def _monitor_goals(
        self,
        query: str,
        user_id: str,
        understanding: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        try:
            progress = self.goals.observe_activity(user_id, query)
            if progress:
                return [progress.to_dict()]
            return []
        except Exception:
            logger.exception("NeuralCore goal monitoring failed")
            return []

    def _prioritize(
        self,
        query: str,
        understanding: Dict[str, Any],
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        try:
            deadline = context.get("deadline")
            if deadline is not None:
                try:
                    deadline = float(deadline)
                except (TypeError, ValueError):
                    deadline = None
            classified = self.prioritization.classify(
                query,
                deadline=deadline,
            )
            out = classified.to_dict()
            # Blend goal-understanding priority.
            gu_priority = understanding.get("priority", "normal")
            if gu_priority == "urgent" and out["tier"] != "urgent":
                out["tier"] = "urgent"
            return out
        except Exception:
            logger.exception("NeuralCore prioritization failed")
            return {"task": query, "tier": "background", "urgency": 0.0, "importance": 0.0}

    def _record_execution(
        self,
        query: str,
        user_id: str,
        success: bool,
        *,
        execution_error: str = "",
        duration_s: float = 0.0,
        domain: str = "general",
    ) -> None:
        try:
            self.self_improvement.record(
                user_id,
                query,
                success,
                duration_s=duration_s,
                error=execution_error,
                strategy=domain,
                domain=domain,
            )
        except Exception:
            logger.exception("NeuralCore self-improvement record failed")

    def _generate_proactive(
        self,
        context: Dict[str, Any],
        user_id: str,
    ) -> List[Dict[str, Any]]:
        try:
            state = context.get("system_state") or context.get("state") or {}
            suggestions = self.proactive.generate(state) if state else []
            return [s.to_dict() for s in suggestions]
        except Exception:
            logger.exception("NeuralCore proactive generation failed")
            return []

    def _predict(
        self,
        query: str,
        user_id: str,
        understanding: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            pred = self.predictive.predict_next(user_id)
            if pred:
                return pred.to_dict()
            return None
        except Exception:
            logger.exception("NeuralCore prediction failed")
            return None

    def _current_verification(self, confidence: Dict[str, Any]) -> Dict[str, Any]:
        """Derive a verification summary from the confidence assessment.

        This is intentional: the actual pre/post verification is performed by
        the executing components. Here we expose a lightweight gate hint so the
        pipeline knows whether to request confirmation.
        """
        required = confidence.get("required_clarification") or []
        risk = confidence.get("risk", 0.0)
        return {
            "pre_verification": {
                "approved": not required,
                "requires_approval": bool(required) or risk >= 0.6,
            },
            "confidence": confidence.get("confidence", 0.5),
        }

    # ── New pipeline stages ────────────────────────────────────────────

    def _learn_personality(
        self,
        query: str,
        user_id: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            response_length = context.get("response_length")
            feedback = context.get("feedback")
            self.personality.observe(
                user_id,
                query,
                response_length=response_length,
                feedback=feedback,
            )
            tool = context.get("tool") or context.get("used_tool")
            if tool:
                self.personality.observe_tool(user_id, str(tool))
            return self.personality.get_profile(user_id).to_dict()
        except Exception:
            logger.exception("NeuralCore personality learning failed")
            return None

    def _gather_context(
        self,
        query: str,
        user_id: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            ce = self.context_engine
            if context.get("project"):
                ce.set_project(user_id, str(context["project"]), str(context.get("repository") or ""))
            if context.get("language"):
                ce.set_language(user_id, str(context["language"]))
            if context.get("folder") or context.get("current_folder"):
                ce.set_folder(user_id, str(context.get("folder") or context.get("current_folder")))
            if context.get("file"):
                ce.add_recent_file(user_id, str(context["file"]))
            if context.get("search"):
                ce.add_recent_search(user_id, str(context["search"]))
            if context.get("browser_tabs"):
                ce.set_browser_tabs(user_id, list(context["browser_tabs"]))
            if context.get("running_services"):
                ce.set_running_services(user_id, list(context["running_services"]))
            ce.set_current_task(user_id, query[:200])
            return ce.get_snapshot(user_id).to_dict()
        except Exception:
            logger.exception("NeuralCore context gathering failed")
            return None

    def _snapshot_continuity(
        self,
        query: str,
        user_id: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            ce = self.continuity
            ce.snapshot(
                user_id,
                conversation_topic=query[:200],
                desktop_state=context.get("desktop_state") or {},
                orb_state=context.get("orb_state") or {},
                voice_state=context.get("voice_state") or {},
                agent_state=context.get("agent_state") or {},
            )
            task = context.get("task")
            if task:
                ce.add_open_task(user_id, task if isinstance(task, dict) else {"name": str(task)})
            return ce.get_state(user_id).to_dict()
        except Exception:
            logger.exception("NeuralCore continuity snapshot failed")
            return None

    def _check_health(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            readings = context.get("health_readings")
            report = self.self_monitoring.check(readings)
            return report.to_dict()
        except Exception:
            logger.exception("NeuralCore health check failed")
            return None

    def _explain_error(self, error: str) -> Optional[Dict[str, Any]]:
        try:
            explanation = self.error_handling.explain(error)
            return explanation.to_dict()
        except Exception:
            logger.exception("NeuralCore error explanation failed")
            return None

    def _project_awareness(self, context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        try:
            root = context.get("project_root") or context.get("repo_root")
            if not root:
                return None
            profile = self.project_awareness.get_or_scan(str(root))
            return profile.to_dict()
        except Exception:
            logger.exception("NeuralCore project awareness failed")
            return None

    def _track_productivity(
        self,
        query: str,
        user_id: str,
        context: Dict[str, Any],
    ) -> Optional[Dict[str, Any]]:
        try:
            pe = self.productivity
            category = context.get("category") or "general"
            if context.get("start_session"):
                pe.start_session(user_id, task=query, category=str(category))
            elif context.get("end_session"):
                pe.end_session(user_id)
            else:
                pe.register_activity(user_id)
            return pe.summary(user_id).to_dict()
        except Exception:
            logger.exception("NeuralCore productivity tracking failed")
            return None

    def _detect_improvements(
        self,
        user_id: str,
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        try:
            observations = context.get("improvement_observations")
            if not observations:
                return []
            opportunities = self.autonomous_improvement.detect(user_id, observations)
            return [o.to_dict() for o in opportunities]
        except Exception:
            logger.exception("NeuralCore improvement detection failed")
            return []

    # ── Proactive helpers for the pipeline ─────────────────────────────

    async def run_proactive_checks(self, user_id: str) -> List[Dict[str, Any]]:
        """Best-effort system-state collection and proactive suggestion."""
        state: Dict[str, Any] = {}
        try:
            import psutil

            battery = getattr(psutil, "sensors_battery", lambda: None)()
            if battery:
                state["battery"] = {
                    "percent": battery.percent,
                    "plugged": bool(battery.power_plugged),
                }
            vm = psutil.virtual_memory()
            state["memory"] = {"percent": vm.percent}
            for part in psutil.disk_partitions():
                try:
                    usage = psutil.disk_usage(part.mountpoint)
                    state["disk"] = {"percent": usage.percent, "mount": part.mountpoint}
                    break
                except Exception:
                    continue
        except ImportError:
            pass
        except Exception:
            logger.debug("Proactive system-state collection skipped")

        if not state:
            return []
        return [s.to_dict() for s in self.proactive.generate(state)]


# Global singleton
_neural_core: Optional[NeuralCore] = None


def get_neural_core() -> NeuralCore:
    """Return the global NeuralCore singleton."""
    global _neural_core
    if _neural_core is None:
        _neural_core = NeuralCore()
    return _neural_core