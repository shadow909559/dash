"""Conversation Manager - Conversation state and history management.

Implements comprehensive conversation management:
- Conversation state tracking
- Conversation summarization
- Conversation history with pagination
- Conversation context tracking

Features:
- Multi-conversation support
- Automatic summarization
- Context preservation
- State persistence
- Conversation branching
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ConversationState(str, Enum):
    """States of a conversation."""
    ACTIVE = "active"
    PAUSED = "paused"
    ARCHIVED = "archived"
    CLOSED = "closed"


class MessageRole(str, Enum):
    """Roles for messages."""
    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"
    TOOL = "tool"


@dataclass
class Message:
    """A single message in a conversation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    role: MessageRole = MessageRole.USER
    content: str = ""
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    token_count: int = 0
    model: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
            "metadata": self.metadata,
            "token_count": self.token_count,
            "model": self.model,
        }


@dataclass
class ConversationSummary:
    """Summary of a conversation."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    conversation_id: str = ""
    summary: str = ""
    key_topics: List[str] = field(default_factory=list)
    action_items: List[str] = field(default_factory=list)
    sentiment: str = "neutral"
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    message_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "conversation_id": self.conversation_id,
            "summary": self.summary,
            "key_topics": self.key_topics,
            "action_items": self.action_items,
            "sentiment": self.sentiment,
            "created_at": self.created_at.isoformat(),
            "message_count": self.message_count,
            "metadata": self.metadata,
        }


@dataclass
class Conversation:
    """A conversation with messages and state."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    user_id: str = ""
    title: str = ""
    state: ConversationState = ConversationState.ACTIVE
    messages: List[Message] = field(default_factory=list)
    summary: Optional[ConversationSummary] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    metadata: Dict[str, Any] = field(default_factory=dict)
    model: Optional[str] = None
    parent_conversation_id: Optional[str] = None  # For branching

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "user_id": self.user_id,
            "title": self.title,
            "state": self.state.value,
            "messages": [m.to_dict() for m in self.messages],
            "summary": self.summary.to_dict() if self.summary else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "metadata": self.metadata,
            "model": self.model,
            "parent_conversation_id": self.parent_conversation_id,
        }


class ConversationManager:
    """Conversation state and history management.

    Manages conversations, their messages, summaries, and context.
    """

    def __init__(self):
        self._conversations: Dict[str, Conversation] = {}
        self._user_conversations: Dict[str, List[str]] = {}  # user_id -> conversation_ids
        self._summarization_handler: Optional[Callable] = None
        self._auto_summarize_threshold = 20  # Messages before auto-summarize
        self._max_messages_per_conversation = 1000

    def set_summarization_handler(self, handler: Callable) -> None:
        """Set the summarization handler."""
        self._summarization_handler = handler

    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
        model: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Conversation:
        """Create a new conversation.

        Args:
            user_id: User ID
            title: Optional conversation title
            model: Optional model being used
            metadata: Additional metadata

        Returns:
            The created conversation
        """
        conversation = Conversation(
            user_id=user_id,
            title=title or "New Conversation",
            model=model,
            metadata=metadata or {},
        )

        self._conversations[conversation.id] = conversation

        # Update user index
        if user_id not in self._user_conversations:
            self._user_conversations[user_id] = []
        self._user_conversations[user_id].append(conversation.id)

        logger.info("Created conversation: %s for user: %s", conversation.id, user_id)
        return conversation

    def get_conversation(self, conversation_id: str) -> Optional[Conversation]:
        """Get a conversation by ID."""
        return self._conversations.get(conversation_id)

    def get_user_conversations(
        self,
        user_id: str,
        state: Optional[ConversationState] = None,
        limit: int = 50,
    ) -> List[Conversation]:
        """Get conversations for a user.

        Args:
            user_id: User ID
            state: Optional state filter
            limit: Maximum number of conversations

        Returns:
            List of conversations
        """
        conversation_ids = self._user_conversations.get(user_id, [])
        conversations = [
            self._conversations[cid]
            for cid in conversation_ids
            if cid in self._conversations
        ]

        if state:
            conversations = [c for c in conversations if c.state == state]

        # Sort by updated_at (most recent first)
        conversations.sort(key=lambda c: c.updated_at, reverse=True)

        return conversations[:limit]

    async def add_message(
        self,
        conversation_id: str,
        role: MessageRole,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        model: Optional[str] = None,
    ) -> Message:
        """Add a message to a conversation.

        Args:
            conversation_id: Conversation ID
            role: Message role
            content: Message content
            metadata: Additional metadata
            model: Model used for the message

        Returns:
            The added message
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            raise ValueError(f"Conversation not found: {conversation_id}")

        message = Message(
            role=role,
            content=content,
            metadata=metadata or {},
            model=model or conversation.model,
        )

        conversation.messages.append(message)
        conversation.updated_at = datetime.now(timezone.utc)

        # Check if we should auto-summarize
        if len(conversation.messages) >= self._auto_summarize_threshold:
            await self._auto_summarize(conversation)

        # Check message limit
        if len(conversation.messages) > self._max_messages_per_conversation:
            logger.warning(
                "Conversation %s exceeded message limit, oldest messages may be lost",
                conversation_id,
            )

        logger.debug(
            "Added message to conversation %s: role=%s, length=%d",
            conversation_id,
            role.value,
            len(content),
        )

        return message

    async def _auto_summarize(self, conversation: Conversation) -> None:
        """Automatically summarize a conversation."""
        if not self._summarization_handler:
            return

        try:
            summary = await self._summarization_handler(conversation.messages)
            conversation.summary = ConversationSummary(
                conversation_id=conversation.id,
                summary=summary.get("summary", ""),
                key_topics=summary.get("key_topics", []),
                action_items=summary.get("action_items", []),
                sentiment=summary.get("sentiment", "neutral"),
                message_count=len(conversation.messages),
            )
            logger.info("Auto-summarized conversation: %s", conversation.id)
        except Exception as exc:
            logger.warning("Auto-summarization failed: %s", exc)

    async def update_conversation_state(
        self,
        conversation_id: str,
        state: ConversationState,
    ) -> bool:
        """Update the state of a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return False

        conversation.state = state
        conversation.updated_at = datetime.now(timezone.utc)

        logger.info("Updated conversation %s state to: %s", conversation_id, state.value)
        return True

    async def summarize_conversation(
        self,
        conversation_id: str,
        force: bool = False,
    ) -> Optional[ConversationSummary]:
        """Manually summarize a conversation.

        Args:
            conversation_id: Conversation ID
            force: Force re-summarization even if already summarized

        Returns:
            The conversation summary
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return None

        if conversation.summary and not force:
            return conversation.summary

        if not self._summarization_handler:
            return None

        try:
            summary_data = await self._summarization_handler(conversation.messages)
            conversation.summary = ConversationSummary(
                conversation_id=conversation.id,
                summary=summary_data.get("summary", ""),
                key_topics=summary_data.get("key_topics", []),
                action_items=summary_data.get("action_items", []),
                sentiment=summary_data.get("sentiment", "neutral"),
                message_count=len(conversation.messages),
            )
            conversation.updated_at = datetime.now(timezone.utc)
            return conversation.summary
        except Exception as exc:
            logger.error("Summarization failed: %s", exc)
            return None

    def get_messages(
        self,
        conversation_id: str,
        role: Optional[MessageRole] = None,
        limit: Optional[int] = None,
        offset: int = 0,
    ) -> List[Message]:
        """Get messages from a conversation.

        Args:
            conversation_id: Conversation ID
            role: Optional role filter
            limit: Optional message limit
            offset: Message offset for pagination

        Returns:
            List of messages
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return []

        messages = conversation.messages

        if role:
            messages = [m for m in messages if m.role == role]

        if offset:
            messages = messages[offset:]

        if limit:
            messages = messages[:limit]

        return messages

    def get_conversation_context(
        self,
        conversation_id: str,
        include_summary: bool = True,
        max_messages: int = 20,
    ) -> str:
        """Get the conversation context as a string.

        Args:
            conversation_id: Conversation ID
            include_summary: Whether to include the summary
            max_messages: Maximum number of recent messages

        Returns:
            Formatted context string
        """
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return ""

        parts = []

        if include_summary and conversation.summary:
            parts.append(f"Summary: {conversation.summary.summary}")
            if conversation.summary.key_topics:
                parts.append(f"Topics: {', '.join(conversation.summary.key_topics)}")

        parts.append("Recent messages:")
        recent_messages = conversation.messages[-max_messages:]
        for message in recent_messages:
            parts.append(f"{message.role.value}: {message.content}")

        return "\n".join(parts)

    async def branch_conversation(
        self,
        conversation_id: str,
        title: Optional[str] = None,
    ) -> Optional[Conversation]:
        """Create a branch of a conversation.

        Args:
            conversation_id: Parent conversation ID
            title: Optional title for the branch

        Returns:
            The new branched conversation
        """
        parent = self._conversations.get(conversation_id)
        if not parent:
            return None

        branch = await self.create_conversation(
            user_id=parent.user_id,
            title=title or f"Branch of {parent.title}",
            model=parent.model,
        )

        # Copy messages and metadata
        branch.messages = parent.messages.copy()
        branch.metadata = parent.metadata.copy()
        branch.parent_conversation_id = parent.id

        logger.info("Branched conversation %s from %s", branch.id, conversation_id)
        return branch

    async def delete_conversation(self, conversation_id: str) -> bool:
        """Delete a conversation."""
        conversation = self._conversations.get(conversation_id)
        if not conversation:
            return False

        # Remove from user index
        if conversation.user_id in self._user_conversations:
            self._user_conversations[conversation.user_id] = [
                cid for cid in self._user_conversations[conversation.user_id]
                if cid != conversation_id
            ]

        # Remove from conversations
        del self._conversations[conversation_id]

        logger.info("Deleted conversation: %s", conversation_id)
        return True

    async def archive_conversation(self, conversation_id: str) -> bool:
        """Archive a conversation."""
        return await self.update_conversation_state(conversation_id, ConversationState.ARCHIVED)

    def search_conversations(
        self,
        user_id: str,
        query: str,
        limit: int = 20,
    ) -> List[Conversation]:
        """Search conversations by query.

        Args:
            user_id: User ID
            query: Search query
            limit: Maximum results

        Returns:
            List of matching conversations
        """
        conversations = self.get_user_conversations(user_id, limit=limit * 2)
        query_lower = query.lower()

        results = []
        for conv in conversations:
            # Search in title
            if query_lower in conv.title.lower():
                results.append(conv)
                continue

            # Search in messages
            for message in conv.messages:
                if query_lower in message.content.lower():
                    results.append(conv)
                    break

            # Search in summary
            if conv.summary and query_lower in conv.summary.summary.lower():
                results.append(conv)

        return results[:limit]

    def get_statistics(self) -> Dict[str, Any]:
        """Get conversation manager statistics."""
        return {
            "total_conversations": len(self._conversations),
            "total_users": len(self._user_conversations),
            "total_messages": sum(len(c.messages) for c in self._conversations.values()),
            "by_state": {
                state.value: len([c for c in self._conversations.values() if c.state == state])
                for state in ConversationState
            },
            "summarized_conversations": len([c for c in self._conversations.values() if c.summary]),
        }
