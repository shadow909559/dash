"""AI Brain - Intelligent Reasoning System.

The Brain orchestrates all cognitive operations for DASH including:
- Goal decomposition and task planning
- Multi-step reasoning with reflection and self-critique
- Context prioritization and compression
- Dynamic tool selection and skill routing
- Autonomous planning with failure recovery
- Memory scoring and conversation summarization
- Adaptive execution based on user preferences
"""

from __future__ import annotations

from dash_backend.brain.reasoning_engine import ReasoningEngine, ReasoningStep, ReasoningContext
from dash_backend.brain.reflection_engine import ReflectionEngine
from dash_backend.brain.context_compressor import ContextCompressor
from dash_backend.brain.tool_selector import DynamicToolSelector
from dash_backend.brain.skill_router import BrainSkillRouter
from dash_backend.brain.memory_scorer import MemoryScorer
from dash_backend.brain.summarizer import ConversationSummarizer
from dash_backend.brain.adaptive_executor import AdaptiveExecutor
from dash_backend.brain.brain_service import BrainService

__all__ = [
    "ReasoningEngine",
    "ReasoningStep",
    "ReasoningContext",
    "ReflectionEngine",
    "ContextCompressor",
    "DynamicToolSelector",
    "BrainSkillRouter",
    "MemoryScorer",
    "ConversationSummarizer",
    "AdaptiveExecutor",
    "BrainService",
]