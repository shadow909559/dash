"""Decision Engine - Decides how to handle each user request.

The decision engine analyzes the user's query, available context, memory,
RAG documents, and tools to determine the optimal path:

1. Direct answer (simple Q&A, greetings, etc.)
2. Memory retrieval + answer
3. RAG retrieval + answer
4. Tool execution (single or chained)
5. Planner decomposition (complex multi-step tasks)
6. Ask clarification (ambiguous queries)
7. Combined (memory + RAG + tools + answer)
"""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger
from dash_backend.llm.service import build_chat_messages, collect_streamed_response

logger = get_logger(__name__)


class DecisionPath(str, Enum):
    """The possible decision paths for handling a request."""

    DIRECT_ANSWER = "direct_answer"
    MEMORY_ONLY = "memory_only"
    RAG_ONLY = "rag_only"
    TOOL_ONLY = "tool_only"
    MEMORY_AND_RAG = "memory_and_rag"
    MEMORY_AND_TOOL = "memory_and_tool"
    RAG_AND_TOOL = "rag_and_tool"
    MEMORY_RAG_TOOL = "memory_rag_tool"
    PLANNER = "planner"
    CLARIFICATION = "clarification"
    COMBINED = "combined"


class DecisionEngine:
    """Analyzes queries and decides the optimal processing path.

    Features:
    - Query complexity analysis
    - Tool requirement detection
    - Memory relevance detection
    - RAG relevance detection
    - Ambiguity detection
    - Confidence scoring for each path
    - Learning from past decisions
    """

    # Keywords that suggest tool usage
    TOOL_KEYWORDS = {
        "open", "close", "launch", "run", "execute", "start", "stop",
        "create", "delete", "move", "copy", "rename", "save",
        "search", "find", "lookup", "browse", "navigate",
        "send", "type", "click", "scroll", "select",
        "screenshot", "capture", "record",
        "shutdown", "restart", "lock", "sleep",
        "install", "uninstall", "update",
        "download", "upload", "export", "import",
    }

    # Keywords that suggest memory retrieval
    MEMORY_KEYWORDS = {
        "remember", "recall", "remind", "forget",
        "what did i", "who am i", "my name", "my preferences",
        "what is my", "where is my", "when did i",
        "do you remember", "you know that",
        "my favorite", "my project", "my goal",
    }

    # Keywords that suggest RAG retrieval
    RAG_KEYWORDS = {
        "document", "file", "pdf", "note", "page",
        "what does it say", "find in", "search in",
        "according to", "refer to", "look up",
        "codebase", "repository", "source code",
    }

    # Patterns that suggest simple direct answers
    DIRECT_ANSWER_PATTERNS = {
        "hello", "hi", "hey", "good morning", "good afternoon",
        "good evening", "how are you", "who are you",
        "what can you do", "help", "thanks", "thank you",
        "bye", "goodbye", "see you",
    }

    @staticmethod
    async def decide(
        query: str,
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[DecisionPath, Dict[str, Any]]:
        """Decide the optimal path for handling a query.

        Args:
            query: The user's query
            memory_context: Available memory context
            rag_context: Available RAG context
            available_tools: List of available tools
            conversation_history: Previous conversation messages
            user_id: The user's ID

        Returns:
            Tuple of (DecisionPath, metadata dict)
        """
        query_lower = query.lower().strip()

        # Quick pattern matching for simple queries
        if any(query_lower.startswith(p) or query_lower == p for p in DecisionEngine.DIRECT_ANSWER_PATTERNS):
            return DecisionPath.DIRECT_ANSWER, {
                "reason": "Simple greeting or help request",
                "confidence": 0.95,
            }

        # Check if query is a simple question that doesn't need tools
        if len(query.split()) <= 5 and not any(kw in query_lower for kw in DecisionEngine.TOOL_KEYWORDS):
            if not any(kw in query_lower for kw in DecisionEngine.MEMORY_KEYWORDS) and \
               not any(kw in query_lower for kw in DecisionEngine.RAG_KEYWORDS):
                return DecisionPath.DIRECT_ANSWER, {
                    "reason": "Simple short query, no tools needed",
                    "confidence": 0.8,
                }

        # Detect tool requirements
        needs_tool = any(kw in query_lower for kw in DecisionEngine.TOOL_KEYWORDS)
        needs_memory = any(kw in query_lower for kw in DecisionEngine.MEMORY_KEYWORDS)
        needs_rag = any(kw in query_lower for kw in DecisionEngine.RAG_KEYWORDS)

        # If query asks about past conversations or user data
        if needs_memory and memory_context:
            if needs_tool:
                return DecisionPath.MEMORY_AND_TOOL, {
                    "reason": "Query requires memory retrieval and tool execution",
                    "memory_query": query,
                    "confidence": 0.85,
                }
            return DecisionPath.MEMORY_ONLY, {
                "reason": "Query requires memory retrieval",
                "memory_query": query,
                "confidence": 0.9,
            }

        # If query references documents
        if needs_rag and rag_context:
            if needs_tool:
                return DecisionPath.RAG_AND_TOOL, {
                    "reason": "Query requires RAG retrieval and tool execution",
                    "rag_query": query,
                    "confidence": 0.85,
                }
            return DecisionPath.RAG_ONLY, {
                "reason": "Query requires document retrieval",
                "rag_query": query,
                "confidence": 0.9,
            }

        # Complex multi-step tasks
        if needs_tool and available_tools:
            # Check if it's a single tool or multi-step task
            if len(query_lower.split(" and ")) > 1 or \
               len(query_lower.split(" then ")) > 1 or \
               len(query_lower.split(",")) > 3:
                return DecisionPath.PLANNER, {
                    "reason": "Complex multi-step task requiring planner",
                    "confidence": 0.85,
                }

            # Check if memory and RAG are also relevant
            if needs_memory and needs_rag:
                return DecisionPath.MEMORY_RAG_TOOL, {
                    "reason": "Query requires memory, RAG, and tools",
                    "memory_query": query,
                    "rag_query": query,
                    "confidence": 0.8,
                }

            return DecisionPath.TOOL_ONLY, {
                "reason": "Query requires tool execution",
                "confidence": 0.9,
            }

        # If ambiguous or uncertain, use LLM to decide
        return await DecisionEngine._llm_decision(
            query, memory_context, rag_context, available_tools,
            conversation_history, user_id,
        )

    @staticmethod
    async def _llm_decision(
        query: str,
        memory_context: Optional[str] = None,
        rag_context: Optional[str] = None,
        available_tools: Optional[List[Dict[str, Any]]] = None,
        conversation_history: Optional[List[Dict[str, str]]] = None,
        user_id: Optional[str] = None,
    ) -> Tuple[DecisionPath, Dict[str, Any]]:
        """Use LLM to decide the optimal path for complex/ambiguous queries."""
        paths = [p.value for p in DecisionPath]
        tools_summary = ", ".join(t.get("name", "?") for t in (available_tools or [])[:10])

        prompt = (
            f"Query: {query}\n\n"
            f"Available tools: [{tools_summary}]\n"
            f"Has memory context: {bool(memory_context)}\n"
            f"Has RAG context: {bool(rag_context)}\n"
            f"Has conversation history: {bool(conversation_history)}\n\n"
            f"Choose the best path from: {', '.join(paths)}\n\n"
            "Rules:\n"
            "- Use 'direct_answer' for simple Q&A, greetings, chit-chat\n"
            "- Use 'memory_only' when query asks about user preferences/history\n"
            "- Use 'rag_only' when query asks about documents/files\n"
            "- Use 'tool_only' when query asks to DO something (open/close/create)\n"
            "- Use 'planner' for complex multi-step tasks\n"
            "- Use 'clarification' when query is ambiguous\n"
            "- Use 'combined' for complex queries needing multiple sources\n\n"
            "Return JSON:\n"
            '{"path": "path_name", "reason": "why this path", "confidence": 0.0-1.0}'
        )

        messages = build_chat_messages(
            system_prompt="You are a decision engine. Choose the optimal path for handling user queries.",
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
            if isinstance(parsed, dict):
                path_str = parsed.get("path", "combined")
                # Validate the path
                for p in DecisionPath:
                    if p.value == path_str:
                        return p, {
                            "reason": parsed.get("reason", "LLM decision"),
                            "confidence": float(parsed.get("confidence", 0.7)),
                        }
                return DecisionPath.COMBINED, {
                    "reason": f"LLM returned invalid path: {path_str}, using combined",
                    "confidence": 0.7,
                }
        except Exception as exc:
            logger.warning("LLM decision failed: %s", exc)

        # Default fallback for uncertain cases
        return DecisionPath.COMBINED, {
            "reason": "Fallback: using combined processing",
            "confidence": 0.6,
        }

    @staticmethod
    def should_ask_clarification(query: str) -> Tuple[bool, float]:
        """Determine if the query is ambiguous enough to ask for clarification."""
        query_lower = query.lower().strip()

        # Very short queries are often ambiguous
        if len(query_lower.split()) <= 2:
            return True, 0.7

        # Questions with vague pronouns
        vague_indicators = ["it", "that", "this", "there", "those", "these"]
        words = query_lower.split()
        if words and words[-1] in vague_indicators:
            return True, 0.6

        # Questions without clear action
        if not any(kw in query_lower for kw in DecisionEngine.TOOL_KEYWORDS) and \
           not any(kw in query_lower for kw in DecisionEngine.MEMORY_KEYWORDS) and \
           not any(kw in query_lower for kw in DecisionEngine.RAG_KEYWORDS) and \
           query_lower.endswith("?"):
            return False, 0.3  # Probably a question, not ambiguous

        return False, 0.0

    @staticmethod
    def estimate_complexity(query: str) -> int:
        """Estimate the complexity of a query (1-10)."""
        score = 1
        query_lower = query.lower()

        # Length factor
        words = query_lower.split()
        if len(words) > 10:
            score += 1
        if len(words) > 20:
            score += 1

        # Multiple steps
        if " and " in query_lower or " then " in query_lower:
            score += 2
        if "," in query_lower:
            score += 1

        # Tool requirements
        tool_matches = sum(1 for kw in DecisionEngine.TOOL_KEYWORDS if kw in query_lower)
        score += min(tool_matches, 3)

        # Memory + RAG
        if any(kw in query_lower for kw in DecisionEngine.MEMORY_KEYWORDS):
            score += 1
        if any(kw in query_lower for kw in DecisionEngine.RAG_KEYWORDS):
            score += 1

        return min(score, 10)


# Global singleton
_engine: Optional[DecisionEngine] = None


def get_decision_engine() -> DecisionEngine:
    """Return the global DecisionEngine singleton."""
    global _engine
    if _engine is None:
        _engine = DecisionEngine()
    return _engine
