"""Neural Core — DASH intelligent entity layer.

The neural package transforms DASH from a command executor into an intelligent
entity that reasons, predicts, adapts, prioritizes, learns, plans, and remembers.

Every module is additive — existing confidence, goal-understanding, and verification
engines are extended, not replaced.
"""

from dash_backend.neural.confidence import (
    ConfidenceAssessment,
    ConfidenceEngine,
    get_confidence_engine,
)
from dash_backend.neural.goal_understanding import (
    GoalUnderstanding,
    GoalUnderstandingEngine,
    get_goal_understanding_engine,
)
from dash_backend.neural.verification import (
    VerificationEngine,
    PreVerificationResult,
    PostVerificationResult,
    get_verification_engine,
)
from dash_backend.neural.user_model import (
    UserModelEngine,
    UserHabits,
    FrequentCommand,
    get_user_model_engine,
)
from dash_backend.neural.predictive import (
    PredictiveEngine,
    Prediction,
    get_predictive_engine,
)
from dash_backend.neural.proactive import (
    ProactiveEngine,
    ProactiveSuggestion,
    get_proactive_engine,
)
from dash_backend.neural.long_term_goals import (
    LongTermGoalsEngine,
    TrackedGoal,
    GoalProgress,
    get_long_term_goals_engine,
)
from dash_backend.neural.prioritization import (
    PrioritizationEngine,
    TaskPriority,
    get_prioritization_engine,
)
from dash_backend.neural.self_improvement import (
    SelfImprovementEngine,
    WorkflowAnalysis,
    get_self_improvement_engine,
)
from dash_backend.neural.personality import (
    PersonalityEngine,
    PersonalityProfile,
    get_personality_engine,
)
from dash_backend.neural.context_engine import (
    ContextEngine,
    ContextSnapshot,
    get_context_engine,
)
from dash_backend.neural.continuity import (
    ContinuityEngine,
    ContinuityState,
    get_continuity_engine,
)
from dash_backend.neural.self_monitoring import (
    SelfMonitoringEngine,
    HealthReport,
    HealthMetric,
    get_self_monitoring_engine,
)
from dash_backend.neural.error_handling import (
    ErrorHandlingEngine,
    ErrorExplanation,
    get_error_handling_engine,
)
from dash_backend.neural.project_awareness import (
    ProjectAwarenessEngine,
    ProjectProfile,
    get_project_awareness_engine,
)
from dash_backend.neural.multitasking import (
    MultitaskingEngine,
    ParallelTask,
    ParallelExecutionResult,
    get_multitasking_engine,
)
from dash_backend.neural.productivity import (
    ProductivityEngine,
    WorkSession,
    ProductivitySummary,
    get_productivity_engine,
)
from dash_backend.neural.autonomous_improvement import (
    AutonomousImprovementEngine,
    OptimizationOpportunity,
    get_autonomous_improvement_engine,
)
from dash_backend.neural.core import (
    NeuralCore,
    NeuralProcessResult,
    get_neural_core,
)

__all__ = [
    # Confidence
    "ConfidenceAssessment",
    "ConfidenceEngine",
    "get_confidence_engine",
    # Goal Understanding
    "GoalUnderstanding",
    "GoalUnderstandingEngine",
    "get_goal_understanding_engine",
    # Verification
    "VerificationEngine",
    "PreVerificationResult",
    "PostVerificationResult",
    "get_verification_engine",
    # User Model
    "UserModelEngine",
    "UserHabits",
    "FrequentCommand",
    "get_user_model_engine",
    # Predictive
    "PredictiveEngine",
    "Prediction",
    "get_predictive_engine",
    # Proactive
    "ProactiveEngine",
    "ProactiveSuggestion",
    "get_proactive_engine",
    # Long-Term Goals
    "LongTermGoalsEngine",
    "TrackedGoal",
    "GoalProgress",
    "get_long_term_goals_engine",
    # Prioritization
    "PrioritizationEngine",
    "TaskPriority",
    "get_prioritization_engine",
    # Self-Improvement
    "SelfImprovementEngine",
    "WorkflowAnalysis",
    "get_self_improvement_engine",
    # Personality
    "PersonalityEngine",
    "PersonalityProfile",
    "get_personality_engine",
    # Context Engine
    "ContextEngine",
    "ContextSnapshot",
    "get_context_engine",
    # Continuity
    "ContinuityEngine",
    "ContinuityState",
    "get_continuity_engine",
    # Self-Monitoring
    "SelfMonitoringEngine",
    "HealthReport",
    "HealthMetric",
    "get_self_monitoring_engine",
    # Error Handling
    "ErrorHandlingEngine",
    "ErrorExplanation",
    "get_error_handling_engine",
    # Project Awareness
    "ProjectAwarenessEngine",
    "ProjectProfile",
    "get_project_awareness_engine",
    # Multitasking
    "MultitaskingEngine",
    "ParallelTask",
    "ParallelExecutionResult",
    "get_multitasking_engine",
    # Productivity
    "ProductivityEngine",
    "WorkSession",
    "ProductivitySummary",
    "get_productivity_engine",
    # Autonomous Improvement
    "AutonomousImprovementEngine",
    "OptimizationOpportunity",
    "get_autonomous_improvement_engine",
    # Neural Core
    "NeuralCore",
    "NeuralProcessResult",
    "get_neural_core",
]