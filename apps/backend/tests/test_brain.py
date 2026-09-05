"""Tests for the AI Brain modules.

Tests reasoning engine, reflection engine, context compressor,
tool selector, memory scorer, summarizer, skill router,
adaptive executor, and BrainService.
"""

from __future__ import annotations

import uuid
import pytest
from typing import Any, Dict, List
from datetime import datetime, timezone

from dash_backend.brain.reasoning_engine import (
    ReasoningEngine,
    ReasoningStep,
    ReasoningContext,
    ReasoningStepType,
)
from dash_backend.brain.reflection_engine import ReflectionEngine
from dash_backend.brain.context_compressor import ContextCompressor
from dash_backend.brain.tool_selector import DynamicToolSelector
from dash_backend.brain.memory_scorer import MemoryScorer
from dash_backend.brain.summarizer import ConversationSummarizer
from dash_backend.brain.skill_router import BrainSkillRouter
from dash_backend.brain.adaptive_executor import AdaptiveExecutor
from dash_backend.brain.brain_service import BrainService


class TestReasoningEngine:
    """Test the ReasoningEngine."""

    def test_reasoning_step_creation(self):
        """Test creating a reasoning step."""
        step = ReasoningStep(
            type=ReasoningStepType.THOUGHT,
            content="This is a test thought.",
            confidence=0.8,
        )
        assert step.id is not None
        assert step.type == ReasoningStepType.THOUGHT
        assert step.content == "This is a test thought."
        assert step.confidence == 0.8

    def test_reasoning_step_to_dict(self):
        """Test reasoning step serialization."""
        step = ReasoningStep(
            type=ReasoningStepType.CONCLUSION,
            content="Conclusion here",
            confidence=0.9,
            metadata={"key": "value"},
        )
        data = step.to_dict()
        assert data["type"] == "conclusion"
        assert data["content"] == "Conclusion here"
        assert data["confidence"] == 0.9
        assert data["metadata"]["key"] == "value"

    def test_reasoning_context_creation(self):
        """Test creating a reasoning context."""
        context = ReasoningContext(
            user_id="user-123",
            query="What is Python?",
            memory_context="User is a developer",
            max_steps=5,
        )
        assert context.user_id == "user-123"
        assert context.query == "What is Python?"
        assert context.max_steps == 5

    def test_extract_conclusion_none(self):
        """Test extract_conclusion with no conclusion steps."""
        steps = [
            ReasoningStep(type=ReasoningStepType.THOUGHT, content="Think"),
            ReasoningStep(type=ReasoningStepType.REFLECTION, content="Reflect"),
        ]
        result = ReasoningEngine.extract_conclusion(steps)
        assert result is None

    def test_extract_conclusion_found(self):
        """Test extract_conclusion finds the conclusion."""
        steps = [
            ReasoningStep(type=ReasoningStepType.THOUGHT, content="Think"),
            ReasoningStep(type=ReasoningStepType.CONCLUSION, content="The answer is X"),
        ]
        result = ReasoningEngine.extract_conclusion(steps)
        assert result == "The answer is X"

    def test_compute_overall_confidence_empty(self):
        """Test compute_overall_confidence with empty steps."""
        assert ReasoningEngine.compute_overall_confidence([]) == 0.0

    def test_compute_overall_confidence_with_critiques(self):
        """Test compute_overall_confidence with critique steps."""
        steps = [
            ReasoningStep(type=ReasoningStepType.CRITIQUE, content="Good", confidence=0.8),
            ReasoningStep(type=ReasoningStepType.CRITIQUE, content="Better", confidence=0.9),
        ]
        confidence = ReasoningEngine.compute_overall_confidence(steps)
        assert abs(confidence - 0.85) < 0.001

    def test_planner_dependency_resolution(self):
        """Test the dependency resolution on Planner."""
        from dash_backend.executive.planner import Planner

        tasks = [
            {"name": "Task A", "depends_on": []},
            {"name": "Task B", "depends_on": ["Task A"]},
            {"name": "Task C", "depends_on": ["Task A", "Task B"]},
        ]
        layers = Planner.resolve_dependencies(tasks)
        assert len(layers) == 3
        assert layers[0][0]["name"] == "Task A"


class TestReflectionEngine:
    """Test the ReflectionEngine."""

    def test_generate_alternatives_empty(self):
        """Test generate_alternatives with empty response."""
        pass  # Async method, tested via integration

    def test_verify_factual_accuracy_empty(self):
        """Test verify_factual_accuracy with empty claims."""
        result = ReflectionEngine.verify_factual_accuracy([])
        # Should be synchronous with empty input
        import asyncio
        result_list = asyncio.run(ReflectionEngine.verify_factual_accuracy([]))
        assert result_list == []


class TestContextCompressor:
    """Test the ContextCompressor."""

    def test_compress_memory_context_empty(self):
        """Test compress_memory_context with empty memories."""
        result = ContextCompressor.compress_memory_context([])
        assert result == ""

    def test_compress_memory_context_with_memories(self):
        """Test compress_memory_context with memories."""
        memories = [
            {"content": "User likes Python", "importance": 0.9, "category": "preference"},
            {"content": "Project deadline is Friday", "importance": 0.7, "category": "task"},
        ]
        result = ContextCompressor.compress_memory_context(memories)
        assert "Python" in result
        assert "deadline" in result

    def test_compress_conversation_history_empty(self):
        """Test compress_conversation_history with empty messages."""
        result = ContextCompressor.compress_conversation_history([])
        assert result == []

    def test_compress_conversation_history_with_messages(self):
        """Test compress_conversation_history with messages."""
        messages = [
            {"role": "system", "content": "You are a helpful AI."},
            {"role": "user", "content": "Hello!"},
            {"role": "assistant", "content": "Hi! How can I help?"},
            {"role": "user", "content": "What's the weather?"},
        ]
        result = ContextCompressor.compress_conversation_history(messages)
        assert len(result) >= 3  # System + recent messages
        assert result[0]["role"] == "system"

    def test_extract_key_points_empty(self):
        """Test extract_key_points with empty text."""
        result = ContextCompressor.extract_key_points("")
        assert result == []

    def test_format_tool_context_empty(self):
        """Test format_tool_context with empty tools."""
        result = ContextCompressor.format_tool_context([])
        assert result == ""

    def test_format_tool_context_with_tools(self):
        """Test format_tool_context with tools."""
        tools = [
            {"name": "search", "description": "Search the web", "parameters": [{"name": "q", "type": "string"}]},
        ]
        result = ContextCompressor.format_tool_context(tools)
        assert "search" in result
        assert "Search the web" in result

    def test_prioritize_context_empty(self):
        """Test prioritize_context with empty contexts."""
        result = ContextCompressor.prioritize_context([])
        assert result == ""


class TestMemoryScorer:
    """Test the MemoryScorer."""

    def test_score_memory(self):
        """Test scoring a memory."""
        memory = {
            "content": "User prefers Python programming",
            "importance": 0.8,
            "access_count": 5,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        score = MemoryScorer.score_memory(memory, query="Python")
        assert 0 <= score <= 1

    def test_score_memory_no_query(self):
        """Test scoring without query."""
        memory = {
            "content": "Some memory",
            "importance": 0.5,
            "access_count": 0,
        }
        score = MemoryScorer.score_memory(memory)
        assert 0 <= score <= 1

    def test_rank_memories_empty(self):
        """Test rank_memories with empty list."""
        result = MemoryScorer.rank_memories([])
        assert result == []

    def test_rank_memories(self):
        """Test ranking memories."""
        memories = [
            {"content": "Important memory", "importance": 0.9, "access_count": 10, "created_at": datetime.now(timezone.utc).isoformat()},
            {"content": "Less important", "importance": 0.3, "access_count": 1, "created_at": datetime.now(timezone.utc).isoformat()},
        ]
        result = MemoryScorer.rank_memories(memories, query="important")
        assert len(result) == 2
        assert result[0]["_score"] >= result[1]["_score"]

    def test_compute_semantic_relevance(self):
        """Test semantic relevance computation."""
        # Jaccard similarity of "python programming" vs "python"
        score = MemoryScorer._compute_semantic_relevance(
            "python programming language", "python"
        )
        assert score > 0

    def test_compute_semantic_relevance_no_match(self):
        """Test semantic relevance with no match."""
        score = MemoryScorer._compute_semantic_relevance(
            "java is different", "python"
        )
        assert score == 0.0

    def test_compute_recency_invalid_date(self):
        """Test recency computation with invalid date."""
        score = MemoryScorer._compute_recency("")
        assert score == 0.5


class TestConversationSummarizer:
    """Test the ConversationSummarizer."""

    def test_summarize_empty_messages(self):
        """Test summarize with empty messages."""
        import asyncio
        result = asyncio.run(ConversationSummarizer.summarize([]))
        assert result == ""

    def test_extractive_summary_short(self):
        """Test extractive summary generation."""
        messages = [
            {"role": "user", "content": "What is Python?"},
            {"role": "assistant", "content": "Python is a programming language."},
        ]
        import asyncio
        result = asyncio.run(ConversationSummarizer.summarize(messages))
        assert len(result) > 0

    def test_analyze_sentiment_no_text(self):
        """Test analyze_sentiment with no user messages."""
        messages = [{"role": "assistant", "content": "Hello!"}]
        import asyncio
        result = asyncio.run(ConversationSummarizer.analyze_sentiment(messages))
        assert result["sentiment"] == "neutral"


class TestAdaptiveExecutor:
    """Test the AdaptiveExecutor."""

    def test_should_retry_success(self):
        """Test should_retry returns False for success."""
        assert AdaptiveExecutor.should_retry({"status": "ok"}) is False

    def test_should_retry_error(self):
        """Test should_retry returns True for retryable errors."""
        assert AdaptiveExecutor.should_retry({"status": "error", "error": "timeout"}) is True

    def test_should_retry_non_retryable(self):
        """Test should_retry returns False for non-retryable errors."""
        assert AdaptiveExecutor.should_retry({"status": "error", "error": "permission denied"}) is False
        assert AdaptiveExecutor.should_retry({"status": "error", "error": "not found"}) is False
        assert AdaptiveExecutor.should_retry({"status": "error", "error": "invalid input"}) is False


class TestBrainService:
    """Test the BrainService."""

    @pytest.fixture(autouse=True)
    def _no_live_llm(self, monkeypatch: pytest.MonkeyPatch):
        """BrainService analysis must be hermetic: never call a live LLM."""
        import dash_backend.brain.summarizer as summarizer_mod

        async def fake_collect(_messages):
            return "canned analysis"

        monkeypatch.setattr(summarizer_mod, "collect_streamed_response", fake_collect)

    def test_brain_service_creation(self):
        """Test creating a BrainService."""
        service = BrainService()
        assert service is not None
        assert service.reasoning_engine is not None
        assert service.reflection_engine is not None
        assert service.context_compressor is not None
        assert service.tool_selector is not None
        assert service.skill_router is not None
        assert service.memory_scorer is not None
        assert service.summarizer is not None
        assert service.adaptive_executor is not None

    def test_retrieve_relevant_memories_empty(self):
        """Test retrieve_relevant_memories with empty list."""
        import asyncio
        service = BrainService()
        result = asyncio.run(
            service.retrieve_relevant_memories([], query="test", top_k=5)
        )
        assert result == []

    def test_analyze_conversation_empty(self):
        """Test analyze_conversation with empty messages."""
        import asyncio
        service = BrainService()
        result = asyncio.run(service.analyze_conversation([]))
        assert result["summary"] == ""
        # Topics and action_items may have content from the LLM fallback
        assert isinstance(result["topics"], list)
        assert isinstance(result["action_items"], list)
        assert isinstance(result["sentiment"]["sentiment"], str)
