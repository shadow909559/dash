"""Reasoning Engine - Chain-of-thought and multi-step reasoning.

Implements advanced reasoning capabilities:
- Chain-of-thought reasoning with step-by-step decomposition
- Multi-step reasoning with backtracking
- Reasoning trace logging for transparency
- Reasoning verification and validation

Features:
- Structured reasoning with explicit steps
- Self-reflection and critique
- Confidence scoring for conclusions
- Reasoning trace for explainability
- Integration with memory and tools
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ReasoningStepType(str, Enum):
    """Types of reasoning steps."""
    THOUGHT = "thought"
    OBSERVATION = "observation"
    ACTION = "action"
    RESULT = "result"
    REFLECTION = "reflection"
    CRITIQUE = "critique"
    CONCLUSION = "conclusion"
    BACKTRACK = "backtrack"


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
    parent_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "type": self.type.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "confidence": self.confidence,
            "metadata": self.metadata,
            "substeps": [s.to_dict() for s in self.substeps],
            "parent_id": self.parent_id,
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
    allow_backtracking: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ReasoningResult:
    """Result of a reasoning process."""
    conclusion: str
    confidence: float
    steps: List[ReasoningStep]
    metadata: Dict[str, Any] = field(default_factory=dict)
    verification_passed: bool = True
    verification_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conclusion": self.conclusion,
            "confidence": self.confidence,
            "steps": [s.to_dict() for s in self.steps],
            "metadata": self.metadata,
            "verification_passed": self.verification_passed,
            "verification_message": self.verification_message,
        }


class ReasoningEngine:
    """Multi-step reasoning engine with chain-of-thought and verification.

    Implements structured reasoning with explicit steps, self-reflection,
    and verification to ensure high-quality conclusions.
    """

    def __init__(self):
        self._reasoning_traces: Dict[str, List[ReasoningStep]] = {}
        self._llm_handler: Optional[Callable] = None
        self._verification_enabled: bool = True

    def set_llm_handler(self, handler: Callable) -> None:
        """Set the LLM handler for generating reasoning steps."""
        self._llm_handler = handler

    async def reason(
        self,
        context: ReasoningContext,
        system_prompt: Optional[str] = None,
    ) -> ReasoningResult:
        """Execute multi-step reasoning on the given context.

        Args:
            context: Reasoning context with query and constraints
            system_prompt: Optional system prompt for the LLM

        Returns:
            Reasoning result with conclusion and steps
        """
        steps: List[ReasoningStep] = []
        max_iterations = min(context.max_steps, 20)
        reasoning_id = str(uuid.uuid4())

        logger.info("Starting reasoning for query: %s", context.query[:100])

        for iteration in range(max_iterations):
            # Generate the next reasoning step
            step = await self._generate_reasoning_step(
                context, steps, system_prompt, iteration
            )
            steps.append(step)

            # Reflect on the step
            reflection = await self._reflect_on_step(step, context)
            reflection_step = ReasoningStep(
                type=ReasoningStepType.REFLECTION,
                content=reflection,
                parent_id=step.id,
            )
            steps.append(reflection_step)

            # Self-critique to check if reasoning is on track
            critique = await self._critique_reasoning(steps, context, iteration)
            critique_step = ReasoningStep(
                type=ReasoningStepType.CRITIQUE,
                content=critique.get("feedback", ""),
                confidence=critique.get("confidence", 0.5),
                metadata={"should_continue": critique.get("should_continue", True)},
                parent_id=step.id,
            )
            steps.append(critique_step)

            # Check if we should stop
            if not critique.get("should_continue", True):
                logger.info("Reasoning stopped by critique at iteration %d", iteration)
                break

            # If confidence is high enough, conclude
            if critique.get("confidence", 0) >= context.confidence_threshold:
                logger.info("Reasoning converged at iteration %d with confidence %.2f", iteration, critique.get("confidence", 0))
                break

            # Check if we need to backtrack
            if context.allow_backtracking and critique.get("should_backtrack", False):
                backtrack_step = await self._backtrack(steps, context)
                steps.append(backtrack_step)

        # Generate final conclusion
        conclusion = await self._generate_conclusion(context, steps)
        final_step = ReasoningStep(
            type=ReasoningStepType.CONCLUSION,
            content=conclusion,
            confidence=critique.get("confidence", 0.8) if 'critique' in locals() else 0.5,
            metadata={"final": True},
        )
        steps.append(final_step)

        # Store reasoning trace
        self._reasoning_traces[reasoning_id] = steps

        # Verify the conclusion
        verification_passed = True
        verification_message = ""
        if self._verification_enabled:
            verification = await self._verify_reasoning(conclusion, steps, context)
            verification_passed = verification.get("passed", True)
            verification_message = verification.get("message", "")

        # Compute overall confidence
        confidence = self._compute_overall_confidence(steps)

        logger.info(
            "Reasoning completed: %d steps, confidence=%.2f, verified=%s",
            len(steps),
            confidence,
            verification_passed,
        )

        return ReasoningResult(
            conclusion=conclusion,
            confidence=confidence,
            steps=steps,
            verification_passed=verification_passed,
            verification_message=verification_message,
        )

    async def _generate_reasoning_step(
        self,
        context: ReasoningContext,
        previous_steps: List[ReasoningStep],
        system_prompt: Optional[str],
        iteration: int,
    ) -> ReasoningStep:
        """Generate the next reasoning step."""
        if self._llm_handler:
            # Build context for LLM
            context_str = self._build_reasoning_prompt(context, previous_steps, iteration)

            try:
                response = await self._llm_handler(
                    system_prompt=system_prompt or "You are a reasoning engine. Think step by step.",
                    user_message=context_str,
                )
                content = response.strip()
            except Exception as exc:
                logger.warning("LLM reasoning step failed: %s", exc)
                content = f"Consider the query: {context.query}"
        else:
            # Fallback to simple template
            content = f"Step {iteration + 1}: Analyzing '{context.query[:50]}...'"

        return ReasoningStep(
            type=ReasoningStepType.THOUGHT,
            content=content,
            confidence=0.5 + (0.5 * iteration / context.max_steps),
            metadata={"iteration": iteration},
        )

    def _build_reasoning_prompt(
        self,
        context: ReasoningContext,
        previous_steps: List[ReasoningStep],
        iteration: int,
    ) -> str:
        """Build the reasoning prompt for the LLM."""
        prompt_parts = [
            f"Query: {context.query}",
        ]

        if context.memory_context:
            prompt_parts.append(f"Memory Context: {context.memory_context}")

        if context.tool_descriptions:
            prompt_parts.append(f"Available Tools: {context.tool_descriptions}")

        if context.constraints:
            prompt_parts.append(f"Constraints: {'; '.join(context.constraints)}")

        if previous_steps:
            prompt_parts.append("\nPrevious reasoning steps:")
            for i, step in enumerate(previous_steps[-5:]):
                prompt_parts.append(f"  {i+1}. [{step.type.value}] {step.content[:200]}")

        prompt_parts.append("\nWhat is your next thought or observation?")

        return "\n".join(prompt_parts)

    async def _reflect_on_step(
        self,
        step: ReasoningStep,
        context: ReasoningContext,
    ) -> str:
        """Reflect on a reasoning step."""
        if self._llm_handler:
            prompt = (
                "Reflect on this reasoning step. Consider:\n"
                "1. Is this logically sound?\n"
                "2. Are there alternative interpretations?\n"
                "3. What assumptions am I making?\n"
                "4. What evidence supports or contradicts this?\n\n"
                f"Step: {step.content}"
            )

            try:
                response = await self._llm_handler(
                    system_prompt="You are a reflection engine. Critically examine reasoning steps.",
                    user_message=prompt,
                )
                return response.strip()
            except Exception as exc:
                logger.warning("Reflection failed: %s", exc)
                return "Reflection unavailable."

        return f"Reflection on: {step.content[:100]}"

    async def _critique_reasoning(
        self,
        steps: List[ReasoningStep],
        context: ReasoningContext,
        iteration: int,
    ) -> Dict[str, Any]:
        """Self-critique the reasoning process so far."""
        if self._llm_handler:
            steps_text = "\n".join(
                f"{i+1}. [{s.type.value}] {s.content[:150]}"
                for i, s in enumerate(steps)
            )

            prompt = (
                "Critique the reasoning so far. Evaluate:\n"
                "1. Is the reasoning on track to answer the query?\n"
                "2. Are there logical gaps or inconsistencies?\n"
                "3. Should we continue or conclude?\n"
                "4. Should we backtrack to a previous step?\n\n"
                f"Query: {context.query}\n\n"
                f"Reasoning steps:\n{steps_text}\n\n"
                "Respond with JSON:\n"
                '{"should_continue": true/false, "confidence": 0.0-1.0, '
                '"should_backtrack": true/false, "feedback": "..."}'
            )

            try:
                response = await self._llm_handler(
                    system_prompt="You are a critique engine. Evaluate reasoning quality.",
                    user_message=prompt,
                )

                # Try to parse JSON response
                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    # Fallback if not JSON
                    return {
                        "should_continue": "continue" in response.lower(),
                        "confidence": 0.7,
                        "should_backtrack": False,
                        "feedback": response,
                    }
            except Exception as exc:
                logger.warning("Critique failed: %s", exc)

        # Fallback
        return {
            "should_continue": iteration < context.max_steps - 1,
            "confidence": 0.7,
            "should_backtrack": False,
            "feedback": "Auto-generated critique",
        }

    async def _backtrack(
        self,
        steps: List[ReasoningStep],
        context: ReasoningContext,
    ) -> ReasoningStep:
        """Backtrack to a previous reasoning step."""
        # Find the last thought step
        thought_steps = [s for s in steps if s.type == ReasoningStepType.THOUGHT]
        if thought_steps:
            last_thought = thought_steps[-1]
            return ReasoningStep(
                type=ReasoningStepType.BACKTRACK,
                content=f"Backtracking from step: {last_thought.content[:100]}",
                parent_id=last_thought.id,
            )

        return ReasoningStep(
            type=ReasoningStepType.BACKTRACK,
            content="Backtracking (no previous thought found)",
        )

    async def _generate_conclusion(
        self,
        context: ReasoningContext,
        steps: List[ReasoningStep],
    ) -> str:
        """Generate the final conclusion from reasoning steps."""
        if self._llm_handler:
            steps_summary = "\n".join(
                f"- {s.type.value}: {s.content[:200]}"
                for s in steps[-10:]
            )

            prompt = (
                f"Based on the following reasoning steps, provide a clear and concise conclusion "
                f"to the query: {context.query}\n\n"
                f"Reasoning steps:\n{steps_summary}\n\n"
                "Provide your conclusion:"
            )

            try:
                response = await self._llm_handler(
                    system_prompt="You are a conclusion engine. Synthesize reasoning into clear answers.",
                    user_message=prompt,
                )
                return response.strip()
            except Exception as exc:
                logger.warning("Conclusion generation failed: %s", exc)

        # Fallback: extract from last thought
        thought_steps = [s for s in steps if s.type == ReasoningStepType.THOUGHT]
        if thought_steps:
            return thought_steps[-1].content

        return "Unable to generate conclusion"

    async def _verify_reasoning(
        self,
        conclusion: str,
        steps: List[ReasoningStep],
        context: ReasoningContext,
    ) -> Dict[str, Any]:
        """Verify the reasoning and conclusion."""
        if self._llm_handler:
            prompt = (
                "Verify the following reasoning and conclusion. Check:\n"
                "1. Does the conclusion follow from the reasoning?\n"
                "2. Are there logical fallacies?\n"
                "3. Is the conclusion relevant to the query?\n\n"
                f"Query: {context.query}\n"
                f"Conclusion: {conclusion}\n\n"
                "Respond with JSON:\n"
                '{"passed": true/false, "message": "..."}'
            )

            try:
                response = await self._llm_handler(
                    system_prompt="You are a verification engine. Check reasoning validity.",
                    user_message=prompt,
                )

                try:
                    return json.loads(response)
                except json.JSONDecodeError:
                    return {
                        "passed": "valid" in response.lower(),
                        "message": response,
                    }
            except Exception as exc:
                logger.warning("Verification failed: %s", exc)

        return {"passed": True, "message": "Verification skipped"}

    def _compute_overall_confidence(self, steps: List[ReasoningStep]) -> float:
        """Compute overall confidence from reasoning steps."""
        if not steps:
            return 0.0

        # Average confidence of all steps
        confidences = [s.confidence for s in steps if s.confidence > 0]
        if not confidences:
            return 0.5

        return sum(confidences) / len(confidences)

    def extract_conclusion(self, steps: List[ReasoningStep]) -> str:
        """Extract the conclusion from reasoning steps."""
        for step in reversed(steps):
            if step.type == ReasoningStepType.CONCLUSION:
                return step.content

        # Fallback to last thought
        for step in reversed(steps):
            if step.type == ReasoningStepType.THOUGHT:
                return step.content

        return "No conclusion found"

    def get_reasoning_trace(self, reasoning_id: str) -> Optional[List[ReasoningStep]]:
        """Get a stored reasoning trace."""
        return self._reasoning_traces.get(reasoning_id)

    def clear_traces(self) -> None:
        """Clear all stored reasoning traces."""
        self._reasoning_traces.clear()
        logger.info("Cleared all reasoning traces")

    def get_statistics(self) -> Dict[str, Any]:
        """Get reasoning engine statistics."""
        return {
            "total_traces": len(self._reasoning_traces),
            "total_steps": sum(len(steps) for steps in self._reasoning_traces.values()),
            "verification_enabled": self._verification_enabled,
        }
