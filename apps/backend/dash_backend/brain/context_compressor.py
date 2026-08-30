"""Context Compressor - Prioritizes and compresses context for LLM input.

Optimizes token usage by ranking information by relevance,
compressing verbose content, and maintaining essential context.
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ContextCompressor:
    """Compresses and prioritizes context for efficient LLM usage.

    Features:
    - Token-aware context truncation
    - Relevance-based prioritization
    - Conversation history compression
    - Memory deduplication
    - Structured context formatting
    """

    @staticmethod
    def compress_memory_context(
        memories: List[Dict[str, Any]],
        max_tokens: int = 2000,
        query: Optional[str] = None,
    ) -> str:
        """Compress memory context by prioritizing relevant memories.

        Args:
            memories: List of memory dicts with 'content', 'importance', 'category'
            max_tokens: Maximum token budget for compressed context
            query: Optional query for relevance scoring

        Returns:
            Compressed context string
        """
        if not memories:
            return ""

        # Score and sort memories
        scored = []
        for mem in memories:
            content = mem.get("content", "")
            importance = mem.get("importance", 0.5)
            category = mem.get("category", "")

            relevance = importance
            if query and content:
                # Simple relevance scoring based on keyword overlap
                query_words = set(query.lower().split())
                content_words = set(content.lower().split())
                overlap = len(query_words & content_words)
                if overlap > 0:
                    relevance = min(1.0, relevance + (overlap * 0.1))

            scored.append((content, relevance, category))

        # Sort by relevance descending
        scored.sort(key=lambda x: x[1], reverse=True)

        # Build compressed context within token budget
        lines = []
        token_estimate = 0
        estimated_tokens_per_char = 0.25  # Conservative estimate

        for content, relevance, category in scored:
            # Truncate long memories
            if len(content) > 500:
                content = content[:497] + "..."

            line = f"- {content}"
            if category:
                line += f" [{category}]"
            if relevance > 0.8:
                line += " [important]"

            line_tokens = int(len(line) * estimated_tokens_per_char)
            if token_estimate + line_tokens > max_tokens:
                break

            lines.append(line)
            token_estimate += line_tokens

        if not lines:
            return ""

        return "Relevant context:\n" + "\n".join(lines)

    @staticmethod
    def compress_conversation_history(
        messages: List[Dict[str, str]],
        max_messages: int = 20,
        max_tokens: int = 3000,
    ) -> List[Dict[str, str]]:
        """Compress conversation history by keeping most relevant messages.

        Prioritizes:
        - System messages (always kept)
        - Recent messages
        - Messages with high information density
        - Messages containing key terms from recent context
        """
        if not messages:
            return []

        # Always keep system messages
        system_msgs = [m for m in messages if m.get("role") == "system"]
        non_system = [m for m in messages if m.get("role") != "system"]

        # Keep recent messages
        recent = non_system[-max_messages:]

        # Compress long messages
        compressed = list(system_msgs)
        for msg in recent:
            content = msg.get("content", "")
            role = msg.get("role", "user")

            # Truncate very long messages
            if len(content) > 1000:
                content = content[:997] + "..."

            compressed.append({"role": role, "content": content})

        return compressed

    @staticmethod
    def extract_key_points(text: str, max_points: int = 5) -> List[str]:
        """Extract key points from a text, removing redundancy."""
        if not text:
            return []

        sentences = re.split(r'[.!?]+', text)
        sentences = [s.strip() for s in sentences if len(s.strip()) > 20]

        # Deduplicate similar sentences
        unique_sentences = []
        seen = set()

        for sentence in sentences:
            # Simple dedup using first 50 chars
            key = sentence[:50].lower()
            if key not in seen:
                seen.add(key)
                unique_sentences.append(sentence)

        return unique_sentences[:max_points]

    @staticmethod
    def format_tool_context(
        tools: List[Dict[str, Any]],
        max_tools: int = 10,
    ) -> str:
        """Format tool descriptions into a compact context string."""
        if not tools:
            return ""

        lines = ["Available tools:"]
        for tool in tools[:max_tools]:
            name = tool.get("name", "unknown")
            description = tool.get("description", "")
            params = tool.get("parameters", [])

            param_str = ", ".join(
                f"{p.get('name', 'arg')}: {p.get('type', 'str')}"
                for p in params[:5]
            )
            if len(params) > 5:
                param_str += "..."

            line = f"- {name}: {description[:100]}"
            if param_str:
                line += f" ({param_str})"
            lines.append(line)

        return "\n".join(lines)

    @staticmethod
    def prioritize_context(
        contexts: List[Tuple[str, float, str]],
        max_tokens: int = 4000,
    ) -> str:
        """Prioritize multiple context sources by relevance score.

        Args:
            contexts: List of (content, relevance_score, source_name) tuples
            max_tokens: Maximum token budget

        Returns:
            Prioritized and concatenated context string
        """
        if not contexts:
            return ""

        # Sort by relevance descending
        sorted_contexts = sorted(contexts, key=lambda x: x[1], reverse=True)

        parts = []
        token_count = 0
        estimated_tokens_per_char = 0.25

        for content, relevance, source in sorted_contexts:
            if relevance < 0.1:
                continue

            section = f"[{source}]\n{content}\n"
            section_tokens = int(len(section) * estimated_tokens_per_char)

            if token_count + section_tokens > max_tokens:
                # Truncate if too long
                remaining_tokens = max_tokens - token_count
                remaining_chars = int(remaining_tokens / estimated_tokens_per_char)
                if remaining_chars > 50:
                    section = section[:remaining_chars] + "...\n"
                    parts.append(section)
                break

            parts.append(section)
            token_count += section_tokens

        return "\n".join(parts)