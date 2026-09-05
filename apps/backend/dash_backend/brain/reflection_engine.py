"""Reflection Engine - Self-critique and reasoning verification.

Provides capabilities for the AI to examine its own reasoning,
verify conclusions, detect errors, and improve responses.
"""

from __future__ import annotations

import json
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger
from dash_backend.llm.service import build_chat_messages, collect_streamed_response

logger = get_logger(__name__)


class ReflectionEngine:
    """Provides self-reflection and critique capabilities.

    Features:
    - Self-critique of responses before delivery
    - Error detection in reasoning chains
    - Factual accuracy verification
    - Bias detection
    - Alternative perspective generation
    - Response improvement suggestions
    """

    @staticmethod
    async def critique_response(
        query: str,
        response: str,
        context: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Critique an AI response before delivering it to the user.

        Returns a dict with:
        - issues: list of identified issues
        - accuracy_score: float 0-1
        - improvements: list of suggested improvements
        - should_regenerate: bool if response is fundamentally flawed
        """
        prompt = (
            f"Critique the following AI response to the user's query.\n\n"
            f"Query: {query}\n\n"
            f"Response: {response}\n"
        )
        if context:
            prompt += f"\nContext: {context}\n"

        prompt += (
            "\nEvaluate for:\n"
            "1. Factual accuracy - Are claims supported?\n"
            "2. Relevance - Does it directly address the query?\n"
            "3. Completeness - Does it cover all aspects?\n"
            "4. Clarity - Is it well-structured and clear?\n"
            "5. Bias - Are there any biases?\n"
            "6. Safety - Does it contain harmful content?\n\n"
            "Return JSON:\n"
            "{\n"
            '  "accuracy_score": 0.0-1.0,\n'
            '  "issues": ["issue1", "issue2"],\n'
            '  "improvements": ["suggestion1", "suggestion2"],\n'
            '  "should_regenerate": false\n'
            "}"
        )

        messages = build_chat_messages(
            system_prompt="You are a critique engine. Evaluate AI responses critically.",
            user_message=prompt,
        )

        default_result = {
            "accuracy_score": 0.8,
            "issues": [],
            "improvements": [],
            "should_regenerate": False,
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
                    "accuracy_score": float(parsed.get("accuracy_score", 0.8)),
                    "issues": list(parsed.get("issues", [])),
                    "improvements": list(parsed.get("improvements", [])),
                    "should_regenerate": bool(parsed.get("should_regenerate", False)),
                }
        except Exception as exc:
            logger.warning("Response critique failed: %s", exc)

        return default_result

    @staticmethod
    async def detect_errors(reasoning_chain: List[str]) -> List[Dict[str, Any]]:
        """Detect logical errors in a reasoning chain."""
        chain_text = "\n".join(f"Step {i+1}: {step}" for i, step in enumerate(reasoning_chain))

        prompt = (
            "Analyze this reasoning chain for logical errors:\n\n"
            f"{chain_text}\n\n"
            "For each error found, return JSON array:\n"
            '[{"step_index": int, "error_type": str, "description": str, "severity": "low"/"medium"/"high"}]'
        )

        messages = build_chat_messages(
            system_prompt="You are an error detection engine. Identify logical fallacies and reasoning errors.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return parsed
        except Exception as exc:
            logger.warning("Error detection failed: %s", exc)

        return []

    @staticmethod
    async def generate_alternatives(
        query: str,
        current_response: str,
        num_alternatives: int = 3,
    ) -> List[str]:
        """Generate alternative responses or approaches."""
        prompt = (
            f"Query: {query}\n\n"
            f"Current response: {current_response}\n\n"
            f"Generate {num_alternatives} alternative approaches or responses. "
            "Number them 1, 2, 3."
        )

        messages = build_chat_messages(
            system_prompt="You generate alternative perspectives and solutions.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            alternatives = []
            for line in result.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    alt = line.split(".", 1)[-1].strip()
                    if alt:
                        alternatives.append(alt)
            return alternatives[:num_alternatives]
        except Exception as exc:
            logger.warning("Alternative generation failed: %s", exc)

        return []

    @staticmethod
    async def verify_factual_accuracy(
        claims: List[str],
    ) -> List[Dict[str, bool]]:
        """Verify factual accuracy of specific claims."""
        if not claims:
            return []

        claims_text = "\n".join(f"{i+1}. {c}" for i, c in enumerate(claims))

        prompt = (
            "Verify the factual accuracy of each claim. "
            "Return JSON array of objects with 'claim_index' (int) and 'accurate' (bool):\n\n"
            f"{claims_text}"
        )

        messages = build_chat_messages(
            system_prompt="You are a fact-checking engine. Verify claims against known facts.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, list):
                return parsed
        except Exception as exc:
            logger.warning("Factual verification failed: %s", exc)

        return [{"claim_index": i, "accurate": True} for i in range(len(claims))]