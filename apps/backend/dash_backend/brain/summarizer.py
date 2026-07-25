"""Conversation Summarizer - Generates conversation summaries for memory.

Creates concise summaries of conversations for long-term memory storage
and context preservation.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from dash_backend.logging_config import get_logger
from dash_backend.llm.service import build_chat_messages, collect_streamed_response

logger = get_logger(__name__)


class ConversationSummarizer:
    """Generates summaries of conversations for memory and context.

    Features:
    - Extractive and abstractive summarization
    - Key topics and action items extraction
    - Sentiment analysis
    - Memory extraction (facts to remember)
    - Multiple summary granularity levels
    """

    SUMMARY_LENGTH_SHORT = 100
    SUMMARY_LENGTH_MEDIUM = 300
    SUMMARY_LENGTH_LONG = 600

    @staticmethod
    async def summarize(
        messages: List[Dict[str, str]],
        max_length: int = 300,
    ) -> str:
        """Generate a summary of a conversation.

        Args:
            messages: List of message dicts with 'role' and 'content'
            max_length: Maximum summary length in characters

        Returns:
            Summary string
        """
        if not messages:
            return ""

        # For short conversations, use extractive approach
        if len(messages) <= 4:
            return ConversationSummarizer._extractive_summary(messages, max_length)

        # For longer conversations, use abstractive approach
        return await ConversationSummarizer._abstractive_summary(
            messages, max_length
        )

    @staticmethod
    def _extractive_summary(
        messages: List[Dict[str, str]],
        max_length: int,
    ) -> str:
        """Create extractive summary from short conversations."""
        user_messages = [
            m.get("content", "") for m in messages if m.get("role") == "user"
        ]
        assistant_messages = [
            m.get("content", "") for m in messages if m.get("role") == "assistant"
        ]

        parts = []
        if user_messages:
            parts.append(f"User asked: {user_messages[0][:100]}")

        if assistant_messages:
            parts.append(f"Assistant responded about: {assistant_messages[0][:100]}")

        if len(user_messages) > 1:
            parts.append(f"Follow-up questions: {len(user_messages) - 1}")

        summary = ". ".join(parts)
        if len(summary) > max_length:
            summary = summary[: max_length - 3] + "..."

        return summary

    @staticmethod
    async def _abstractive_summary(
        messages: List[Dict[str, str]],
        max_length: int,
    ) -> str:
        """Create abstractive summary using LLM."""
        conversation_text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')[:200]}"
            for m in messages[-20:]  # Last 20 messages for context
        )

        prompt = (
            f"Summarize this conversation in {max_length} characters or less:\n\n"
            f"{conversation_text}\n\n"
            "Focus on key topics, decisions, and action items."
        )

        messages_list = build_chat_messages(
            system_prompt="You summarize conversations concisely, highlighting key points.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages_list)
            summary = result.strip()

            # Truncate if needed
            if len(summary) > max_length:
                summary = summary[: max_length - 3] + "..."

            return summary
        except Exception as exc:
            logger.warning("Abstractive summary failed: %s", exc)
            return ConversationSummarizer._extractive_summary(messages, max_length)

    @staticmethod
    async def extract_key_topics(
        messages: List[Dict[str, str]],
    ) -> List[str]:
        """Extract key topics discussed in a conversation."""
        conversation_text = "\n".join(
            f"{m.get('role', 'unknown')}: {m.get('content', '')[:100]}"
            for m in messages[-30:]
        )

        prompt = (
            f"Extract up to 5 key topics from this conversation:\n\n"
            f"{conversation_text}\n\n"
            "Return topics as a comma-separated list."
        )

        messages_list = build_chat_messages(
            system_prompt="You extract key discussion topics from conversations.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages_list)
            topics = [t.strip() for t in result.split(",") if t.strip()]
            return topics[:5]
        except Exception as exc:
            logger.warning("Topic extraction failed: %s", exc)
            return []

    @staticmethod
    async def extract_action_items(
        messages: List[Dict[str, str]],
    ) -> List[str]:
        """Extract action items and tasks from a conversation."""
        conversation_text = "\n".join(
            m.get("content", "")[:200] for m in messages[-30:]
        )

        prompt = (
            f"Extract any action items, tasks, or follow-ups from this conversation:\n\n"
            f"{conversation_text}\n\n"
            "Return as a numbered list. If none, return 'None'."
        )

        messages_list = build_chat_messages(
            system_prompt="You extract action items from conversations.",
            user_message=prompt,
        )

        try:
            result = await collect_streamed_response(messages_list)
            if result.strip().lower() == "none":
                return []
            items = [
                line.strip().lstrip("0123456789.- ")
                for line in result.split("\n")
                if line.strip() and (line.strip()[0].isdigit() or line.strip().startswith("-"))
            ]
            return items[:5]
        except Exception as exc:
            logger.warning("Action item extraction failed: %s", exc)
            return []

    @staticmethod
    async def analyze_sentiment(
        messages: List[Dict[str, str]],
    ) -> Dict[str, Any]:
        """Analyze sentiment of a conversation."""
        user_text = " ".join(
            m.get("content", "") for m in messages if m.get("role") == "user"
        )

        if not user_text:
            return {"sentiment": "neutral", "score": 0.5}

        prompt = (
            f"Analyze the sentiment of this user's messages:\n\n{user_text[:500]}\n\n"
            "Return JSON: {\"sentiment\": \"positive\"/\"negative\"/\"neutral\", "
            '"score": 0.0-1.0, "emotions": ["emotion1", "emotion2"]}'
        )

        messages_list = build_chat_messages(
            system_prompt="You analyze sentiment in text.",
            user_message=prompt,
        )

        try:
            import json
            result = await collect_streamed_response(messages_list)
            result = result.strip()
            if result.startswith("```"):
                parts = result.split("```")
                if len(parts) >= 2:
                    result = parts[1].strip()
            parsed = json.loads(result)
            if isinstance(parsed, dict):
                return {
                    "sentiment": str(parsed.get("sentiment", "neutral")),
                    "score": float(parsed.get("score", 0.5)),
                    "emotions": list(parsed.get("emotions", [])),
                }
        except Exception as exc:
            logger.warning("Sentiment analysis failed: %s", exc)

        return {"sentiment": "neutral", "score": 0.5, "emotions": []}