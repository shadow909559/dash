"""Memory-aware, planner-aware, and RAG-aware voice conversations.

Integrates voice transcripts with the existing chat/memory/planner/RAG
pipelines so voice interactions are contextually aware.
"""

from __future__ import annotations

from typing import Any, AsyncIterator, Optional

from dash_backend.logging_config import get_logger
from dash_backend.voice_system.streaming import StreamingVoiceProcessor

logger = get_logger(__name__)


class VoiceConversationManager:
    """Manages voice conversations with memory, planner, and RAG context.

    Wraps the StreamingVoiceProcessor and hooks into:
    - Memory system: retrieves relevant memories for context
    - Planner system: informs planner of voice-based goals
    - RAG system: retrieves relevant documents
    """

    def __init__(self, user_id: str):
        self.user_id = user_id
        self.processor = StreamingVoiceProcessor(
            on_transcript=self._on_transcript_callback,
            on_state_change=self._on_state_change,
            on_interrupt=self._on_interrupt,
        )
        self._memory_context: Optional[str] = None
        self._rag_context: Optional[str] = None
        self._planner_context: Optional[str] = None
        self._transcript_history: list[dict[str, str]] = []

    async def load_contexts(self, session, query: str) -> dict[str, Optional[str]]:
        """Load memory, RAG, and planner contexts for a voice query."""
        contexts = {}

        # Load memory context
        try:
            from dash_backend.memory.service import build_memory_context
            memory_ctx = await build_memory_context(session, self.user_id, query=query)
            if memory_ctx:
                self._memory_context = memory_ctx
                contexts["memory"] = memory_ctx
        except Exception:
            logger.exception("Failed to load memory context for voice")

        # Load RAG context
        try:
            from dash_backend.rag.service import retrieve_context
            rag_ctx = await retrieve_context(session, self.user_id, query=query)
            if rag_ctx:
                self._rag_context = rag_ctx
                contexts["rag"] = rag_ctx
        except Exception:
            logger.exception("Failed to load RAG context for voice")

        # Load planner context
        try:
            from dash_backend.executive.planner import get_planner_service
            planner_svc = get_planner_service()
            planner_ctx = await planner_svc.get_context_summary(self.user_id)
            if planner_ctx:
                self._planner_context = planner_ctx
                contexts["planner"] = planner_ctx
        except Exception:
            logger.exception("Failed to load planner context for voice")

        return contexts

    async def process_transcript_with_context(
        self,
        session,
        transcript: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncIterator[Any]:
        """Process a transcript through the chat pipeline with all contexts loaded.

        Yields chat events (tokens, done, errors) similar to handle_chat_send.
        """
        from dash_backend.api.websocket.handlers import handle_chat_send
        from dash_backend.api.websocket.protocol import ChatSendMessage
        import uuid

        # Record transcript
        self._transcript_history.append({"role": "user", "content": transcript})

        # Build contexts
        await self.load_contexts(session, transcript)

        # Create a ChatSendMessage and process through the chat handler
        msg = ChatSendMessage(
            conversation_id=conversation_id,
            message_id=str(uuid.uuid4()),
            content=transcript,
        )

        async for event in handle_chat_send(msg, session=session, user_id=self.user_id):
            yield event

    def _on_transcript_callback(self, text: str):
        """Called when a transcript is ready from the streaming processor."""
        logger.debug("Voice transcript: %s", text[:80])

    def _on_state_change(self, state):
        """Called when the audio stream state changes."""
        logger.debug("Voice state: %s", state.value)

    def _on_interrupt(self):
        """Called when an interrupt is detected."""
        logger.info("Voice conversation interrupted for user %s", self.user_id)

    def get_recent_context(self) -> dict[str, Any]:
        """Get the recent conversation context for debugging or display."""
        return {
            "transcript_count": len(self._transcript_history),
            "has_memory": self._memory_context is not None,
            "has_rag": self._rag_context is not None,
            "has_planner": self._planner_context is not None,
        }

