"""BrainService - Central orchestrator for all AI cognitive operations.

The BrainService integrates reasoning, reflection, context compression,
tool selection, skill routing, memory scoring, and adaptive execution
into a unified cognitive pipeline.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.brain.reasoning_engine import (
    ReasoningEngine,
    ReasoningStep,
    ReasoningContext,
)
from dash_backend.brain.reflection_engine import ReflectionEngine
from dash_backend.brain.context_compressor import ContextCompressor
from dash_backend.brain.tool_selector import DynamicToolSelector
from dash_backend.brain.skill_router import BrainSkillRouter
from dash_backend.brain.memory_scorer import MemoryScorer
from dash_backend.brain.summarizer import ConversationSummarizer
from dash_backend.brain.adaptive_executor import AdaptiveExecutor

logger = get_logger(__name__)


class BrainService:
    """Central cognitive service that orchestrates all AI operations.

    Integrates all brain modules into a unified pipeline:
    1. Receive input + context
    2. Prioritize and compress context
    3. Reason with chain-of-thought
    4. Reflect and self-critique
    5. Select tools or skills
    6. Execute adaptively
    7. Summarize and store in memory
    """

    def __init__(self):
        self.reasoning_engine = ReasoningEngine()
        self.reflection_engine = ReflectionEngine()
        self.context_compressor = ContextCompressor()
        self.tool_selector = DynamicToolSelector()
        self.skill_router = BrainSkillRouter()
        self.memory_scorer = MemoryScorer()
        self.summarizer = ConversationSummarizer()
        self.adaptive_executor = AdaptiveExecutor()

    async def process(
        self,
        query: str,
        user_id: str,
        conversation_id: Optional[str] = None,
        memory_context: Optional[str] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        constraints: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Process a user query through the full cognitive pipeline.

        Args:
            query: The user's query or task description
            user_id: The user's ID
            conversation_id: Optional conversation ID
            memory_context: Optional memory context string
            conversation_history: Optional conversation history
            available_tools: Optional list of available tools
            constraints: Optional list of constraints

        Returns:
            Processed result with reasoning, reflection, and execution
        """
        # Step 1: Compress context
        compressed_context = self._prepare_context(
            memory_context or "",
            conversation_history or [],
            available_tools or [],
        )

        # Step 2: Reason
        reasoning_context = ReasoningContext(
            user_id=user_id,
            conversation_id=conversation_id,
            query=query,
            memory_context=compressed_context,
            tool_descriptions=self._format_tools(available_tools or []),
            constraints=constraints or [],
            max_steps=10,
            confidence_threshold=0.7,
        )

        reasoning_steps = await self.reasoning_engine.reason(reasoning_context)

        # Step 3: Extract conclusion and confidence
        conclusion = self.reasoning_engine.extract_conclusion(reasoning_steps)
        confidence = self.reasoning_engine.compute_overall_confidence(reasoning_steps)

        # Step 4: Self-critique the conclusion
        if conclusion:
            critique = await self.reflection_engine.critique_response(
                query=query,
                response=conclusion,
                context=compressed_context[:1000],
            )

            if critique.get("should_regenerate"):
                logger.info("Regenerating response based on critique")
                reasoning_context.max_steps = 5
                reasoning_steps = await self.reasoning_engine.reason(
                    reasoning_context,
                    system_prompt="Provide a revised answer addressing the issues found.",
                )
                conclusion = self.reasoning_engine.extract_conclusion(reasoning_steps)
                confidence = self.reasoning_engine.compute_overall_confidence(reasoning_steps)
        else:
            critique = {"accuracy_score": 0.5, "issues": [], "improvements": []}

        # Step 5: Determine if tool execution is needed
        execution_result = None
        if confidence < 0.8 and available_tools:
            # Try tool execution to gather more information
            execution_result = await self.adaptive_executor.execute_task(
                task_description=query,
                context={
                    "user_id": user_id,
                    "conversation_id": conversation_id,
                    "args": {},
                },
                timeout=30.0,
            )

        return {
            "conclusion": conclusion or "I need to think about this further.",
            "confidence": confidence,
            "reasoning_steps": [s.to_dict() for s in reasoning_steps],
            "critique": critique,
            "execution_result": execution_result,
            "memory_context": compressed_context[:500] if compressed_context else None,
        }

    async def plan_and_execute(
        self,
        goal: str,
        user_id: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """Plan and execute a goal autonomously.

        Args:
            goal: The high-level goal to accomplish
            user_id: The user's ID
            context: Optional execution context

        Returns:
            Execution report with planning and results
        """
        context = context or {}

        # Decompose goal using reasoning
        reasoning_context = ReasoningContext(
            user_id=user_id,
            query=goal,
            memory_context=context.get("memory_context", ""),
            constraints=context.get("constraints", []),
            max_steps=8,
        )

        planning_steps = await self.reasoning_engine.reason(reasoning_context)
        plan = self.reasoning_engine.extract_conclusion(planning_steps)

        if not plan:
            return {"status": "error", "error": "Failed to create plan"}

        # Execute the plan
        result = await self.adaptive_executor.execute_task(
            task_description=plan,
            context=context,
            timeout=context.get("timeout", 60.0),
        )

        return {
            "status": "ok" if result.get("status") == "ok" else "error",
            "goal": goal,
            "plan": plan,
            "execution": result,
            "reasoning_steps": [s.to_dict() for s in planning_steps],
        }

    async def analyze_conversation(
        self,
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Analyze a conversation for insights, summary, and actions.

        Args:
            messages: List of message dicts

        Returns:
            Analysis with summary, topics, action items, sentiment
        """
        summary = await self.summarizer.summarize(messages)
        topics = await self.summarizer.extract_key_topics(messages)
        action_items = await self.summarizer.extract_action_items(messages)
        sentiment = await self.summarizer.analyze_sentiment(messages)

        return {
            "summary": summary,
            "topics": topics,
            "action_items": action_items,
            "sentiment": sentiment,
        }

    async def retrieve_relevant_memories(
        self,
        memories: List[Dict[str, Any]],
        query: str,
        top_k: int = 10,
    ) -> List[Dict[str, Any]]:
        """Retrieve and rank relevant memories using memory scoring.

        Args:
            memories: List of memory dicts
            query: Query for relevance matching
            top_k: Number of top memories to return

        Returns:
            Ranked list of memories with scores
        """
        return self.memory_scorer.rank_memories(
            memories,
            query=query,
            top_k=top_k,
        )

    def _prepare_context(
        self,
        memory_context: str,
        conversation_history: List[Dict[str, str]],
        available_tools: List[Dict[str, Any]],
    ) -> str:
        """Prepare and compress context for the cognitive pipeline."""
        context_parts = []

        if memory_context:
            context_parts.append(("[MEMORY]", memory_context))

        if conversation_history:
            compressed = self.context_compressor.compress_conversation_history(
                conversation_history
            )
            if compressed:
                history_text = "\n".join(
                    f"{m.get('role', 'user')}: {m.get('content', '')[:100]}"
                    for m in compressed[-5:]
                )
                context_parts.append(("[HISTORY]", history_text))

        if available_tools:
            tool_text = self.context_compressor.format_tool_context(available_tools)
            if tool_text:
                context_parts.append(("[TOOLS]", tool_text))

        if not context_parts:
            return ""

        # Prioritize and combine
        contexts = [(content, 0.8 if tag == "[MEMORY]" else 0.5, tag) for tag, content in context_parts]
        return self.context_compressor.prioritize_context(contexts, max_tokens=2000)

    def _format_tools(self, tools: List[Dict[str, Any]]) -> str:
        """Format tools for the reasoning engine."""
        if not tools:
            return ""
        return self.context_compressor.format_tool_context(tools)