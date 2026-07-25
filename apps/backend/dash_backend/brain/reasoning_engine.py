"""Reasoning Engine - Multi-step reasoning with thought decomposition.

Implements chain-of-thought reasoning, self-reflection, and structured
thought decomposition for complex problem solving.
"""

from __future__ import annotations

import json
import uuid
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.llm.service import build_chat_messages, collect_streamed_response

logger = get_logger(__name__)


class ReasoningStepType(str, Enum):
    """Types of reasoning steps in the chain."""
    THOUGHT = "thought"
    OBSERVATION = "observation"
    ACTION = "action"
    RESULT = "result"
    REFLECTION = "reflection"
    CRITIQUE = "critique"
    CONCLUSION = "conclusion"


@dataclass
class ReasoningStep:
    """A single step in the reasoning chain."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    type: ReasoningStepType = ReasoningStepType.THOUGHT
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    confidence: float = 0.5
    metadata: Dict[str, Any] = field(default_factory=dict)
    substeps: List[ReasoningStep] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "metadata": self.metadata,
            "substeps": [s.to_dict() for s in self.substeps],
        }


@dataclass
class ReasoningContext:
    """Context for reasoning operations."""
    user_id: str
    conversation_id: Optional[str] = None
    query: str = ""
    memory_context: str = ""
    tool_descriptions: str = ""
    constraints: List[str] = field(default_factory=list)
    previous_steps: List[ReasoningStep] = field(default_factory=list)
    max_steps: int = 10
    confidence_threshold: float = 0.7


class ReasoningEngine:
    """Multi-step reasoning engine with chain-of-thought and reflection.

    Features:
    - Goal decomposition into reasoning steps
    - Self-reflection and critique at each step
    - Confidence scoring for conclusions
    - Adaptive depth based on problem complexity
    - Integration with memory and tools
    """

    @staticmethod
    async def reason(
        context: ReasoningContext,
        system_prompt: Optional[str] = None,
    ) -> List[ReasoningStep]:
        """Execute multi-step reasoning on the given context.

        Returns a chain of reasoning steps leading to a conclusion.
        """
        steps: List[ReasoningStep] = []
        max_iterations = min(context.max_steps, 20)

        for iteration in range(max_iterations):
            # Build the reasoning prompt with context
            thought = await ReasoningEngine._generate_thought(
                context, steps, system_prompt
            )

            step = ReasoningStep(
                type=ReasoningStepType.THOUGHT,
                content=thought,
                confidence=0.5 + (0.5 * iteration / max_iterations),
                metadata={"iteration": iteration},
            )
            steps.append(step)

            # Reflect on the thought
            reflection = await ReasoningEngine._reflect(step.content, context)
            reflection_step = ReasoningStep(
                type=ReasoningStepType.REFLECTION,
                content=reflection,
                metadata={"parent_step_id": step.id},
            )
            steps.append(reflection_step)

            # Self-critique to check if reasoning is on track
            critique = await ReasoningEngine._self_critique(
                steps, context, iteration
            )
            critique_step = ReasoningStep(
                type=ReasoningStepType.CRITIQUE,
                content=critique.get("feedback", ""),
                confidence=critique.get("confidence", 0.5),
                metadata={"should_continue": critique.get("should_continue", True)},
            )
            steps.append(critique_step)

            # Check if we should stop
            if not critique.get("should_continue", True):
                conclusion = await ReasoningEngine._generate_conclusion(
                    context, steps
                )
                final_step = ReasoningStep(
                    type=ReasoningStepType.CONCLUSION,
                    content=conclusion,
                    confidence=critique.get("confidence", 0.8),
                    metadata={"final": True},
                )
                steps.append(final_step)
                break

            # If confidence is high enough, conclude
            if critique.get("confidence", 0) >= context.confidence_threshold:
                conclusion = await ReasoningEngine._generate_conclusion(
                    context, steps
                )
                final_step = ReasoningStep(
                    type=ReasoningStepType.CONCLUSION,
                    content=conclusion,
                    confidence=critique.get("confidence", 0.8),
                    metadata={"final": True},
                )
                steps.append(final_step)
                break

        return steps

    @staticmethod
    async def _generate_thought(
        context: ReasoningContext,
        previous_steps: List[ReasoningStep],
        system_prompt: Optional[str] = None,
    ) -> str:
        """Generate the next reasoning thought."""
        prompt = system_prompt or (
            "You are a reasoning engine. Think step by step through the problem. "
            "Consider what you know, what you need to find out, and what actions to take."
        )

        context_str = f"Query: {context.query}\n"
        if context.memory_context:
            context_str += f"Memory Context: {context.memory_context}\n"
        if context.tool_descriptions:
            context_str += f"Available Tools: {context.tool_descriptions}\n"
        if context.constraints:
            context_str += f"Constraints: {'; '.join(context.constraints)}\n"

        if previous_steps:
            context_str += "\nPrevious reasoning steps:\n"
            for i, step in enumerate(previous_steps[-5:]):  # Last 5 steps
                context_str += f"  {i+1}. [{step.type.value}] {step.content[:200]}\n"

        context_str += "\nWhat is your next thought or observation?"

        messages = build_chat_messages(
            system_prompt=prompt,
            user_message=context_str,
        )

        try:
            result = await collect_streamed_response(messages)
            return result.strip()
        except Exception as exc:
            logger.warning("Thought generation failed: %s", exc)
            return f"Consider the query: {context.query}"

    @staticmethod
    async def _reflect(thought: str, context: ReasoningContext) -> str:
        """Reflect on a reasoning thought."""
        prompt = (
            "Reflect on this reasoning step. Consider:\n"
            "1. Is this logically sound?\n"
            "2. Are there alternative interpretations?\n"
            "3. What assumptions am I making?\n"
            "4. What evidence supports or contradicts this?\n\n"
            f"Thought: {thought}"
        )

        messages = build_chat_messages(
            system_prompt="You are a reflection engine. Critically examine reasoning steps.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            return result.strip()
        except Exception as exc:
            logger.warning("Reflection failed: %s", exc)
            return "Reflection unavailable."

    @staticmethod
    async def _self_critique(
        steps: List[ReasoningStep],
        context: ReasoningContext,
        iteration: int,
    ) -> Dict[str, Any]:
        """Self-critique the reasoning process so far."""
        steps_text = "\n".join(
            f"{i+1}. [{s.type.value}] {s.content[:150]}"
            for i, s in enumerate(steps)
        )

        prompt = (
            f"Evaluate this reasoning chain (iteration {iteration + 1}):\n\n"
            f"{steps_text}\n\n"
            "Rate from 0.0 to 1.0:\n"
            "- confidence: How confident are you in the conclusion?\n"
            "- should_continue: Should reasoning continue (true/false)?\n"
            "Provide feedback explaining your rating.\n"
            "Return JSON: {\"confidence\": float, \"should_continue\": bool, \"feedback\": str}"
        )

        messages = build_chat_messages(
            system_prompt="You are a critique engine. Evaluate reasoning quality.",
            user_message=prompt,
        )

        default_result = {
            "confidence": min(0.5 + iteration * 0.1, 0.9),
            "should_continue": iteration < context.max_steps - 1,
            "feedback": "Proceeding with reasoning.",
        }

        try:
            result = await collect_streamed_response(messages)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return {
                    "confidence": float(parsed.get("confidence", 0.5)),
                    "should_continue": bool(parsed.get("should_continue", True)),
                    "feedback": str(parsed.get("feedback", "")),
                }
        except Exception as exc:
            logger.warning("Self-critique failed: %s", exc)

        return default_result

    @staticmethod
    async def _generate_conclusion(
        context: ReasoningContext,
        steps: List[ReasoningStep],
    ) -> str:
        """Generate a final conclusion from the reasoning chain."""
        steps_summary = "\n".join(
            f"{i+1}. {s.content[:200]}"
            for i, s in enumerate(steps)
            if s.type in (ReasoningStepType.THOUGHT, ReasoningStepType.CONCLUSION)
        )

        prompt = (
            f"Based on the following reasoning chain, provide a clear conclusion:\n\n"
            f"Query: {context.query}\n\n"
            f"Reasoning:\n{steps_summary}\n\n"
            "Provide a concise conclusion that directly answers the query."
        )

        messages = build_chat_messages(
            system_prompt="You are a conclusion engine. Summarize reasoning into clear answers.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            return result.strip()
        except Exception as exc:
            logger.warning("Conclusion generation failed: %s", exc)
            return "Unable to reach a conclusion."

    @staticmethod
    def extract_conclusion(steps: List[ReasoningStep]) -> Optional[str]:
        """Extract the final conclusion from a reasoning chain."""
        for step in reversed(steps):
            if step.type == ReasoningStepType.CONCLUSION:
                return step.content
            if step.type == ReasoningStepType.CRITIQUE and step.metadata.get("final"):
                return step.content
        return None

    @staticmethod
    def compute_overall_confidence(steps: List[ReasoningStep]) -> float:
        """Compute overall confidence from the reasoning chain."""
        if not steps:
            return 0.0

        critique_steps = [
            s for s in steps if s.type == ReasoningStepType.CRITIQUE
        ]
        if critique_steps:
            avg_confidence = sum(s.confidence for s in critique_steps) / len(critique_steps)
            return avg_confidence

        conclusion_steps = [
            s for s in steps if s.type == ReasoningStepType.CONCLUSION
        ]
        if conclusion_steps:
            return conclusion_steps[-1].confidence

        return steps[-1].confidence if steps else 0.0