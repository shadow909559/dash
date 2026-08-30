"""Conversation Agent.

Manages conversation state, message history and summarization. It wraps the
existing ``intelligence.conversation_manager`` so the orchestrator can keep
context cohesive across a multi-agent task.
"""

from __future__ import annotations

from typing import Any, Dict, List

from dash_backend.agents.ecosystem.base import (
    AgentDependency,
    AgentPriority,
    AgentSpec,
    BaseAgent,
)
from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


def conversation_agent_spec() -> AgentSpec:
    """The declarative spec for the Conversation Agent."""
    return AgentSpec(
        key="conversation",
        name="Conversation Agent",
        description=(
            "Manages conversation state, message history and summarization."
        ),
        capabilities=[
            "conversation_state",
            "message_history",
            "summarization",
            "context_persistence",
        ],
        priority=AgentPriority.HIGH,
        permissions=["read_conversations", "write_conversations"],
        dependencies=[
            AgentDependency(name="memory", kind="agent", required=False),
        ],
        tools=["append_message", "get_history", "summarize", "reset"],
        memory_access="read_write",
        execution_api="async",
        category="core",
        system_prompt=(
            "You are DASH's Conversation Agent. You hold the thread of the "
            "conversation so the user experiences one seamless AI."
        ),
    )


class ConversationAgent(BaseAgent):
    """Runtime for the Conversation Agent."""

    def __init__(self) -> None:
        super().__init__(conversation_agent_spec())
        self._history: List[Dict[str, str]] = []

    async def _run(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        action = payload.get("action", "history")
        logger.info("Conversation Agent action=%s", action)

        if action == "append":
            role = payload.get("role", "user")
            content = payload.get("content", "")
            self._history.append({"role": role, "content": content})
            return {"added": True, "length": len(self._history)}
        if action == "history":
            return {"history": self._history}
        if action == "summarize":
            return {"summary": self._summarize()}
        if action == "reset":
            self._history = []
            return {"reset": True}
        return {"status": "ok", "agent": "conversation"}

    def _summarize(self) -> str:
        """Produce a lightweight summary of the conversation."""
        if not self._history:
            return ""
        # Basic summary: last exchange + word count
        last = self._history[-1].get("content", "")
        total_words = sum(len(m.get("content", "").split()) for m in self._history)
        return f"{len(self._history)} messages, {total_words} words. Last: {last[:120]}"


_conversation_agent: ConversationAgent | None = None


def get_conversation_agent() -> ConversationAgent:
    """Return the Conversation Agent singleton."""
    global _conversation_agent
    if _conversation_agent is None:
        _conversation_agent = ConversationAgent()
    return _conversation_agent
