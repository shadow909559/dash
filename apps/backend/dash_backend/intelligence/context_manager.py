"""Context Manager - Context window management and compression.

Implements intelligent context management:
- Context window tracking and token counting
- Context compression and summarization
- Context prioritization based on importance
- Context retention strategies

Features:
- Automatic context window management
- Smart context compression
- Priority-based context retention
- Context serialization and deserialization
- Multi-conversation context tracking
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class ContextPriority(str, Enum):
    """Priority levels for context items."""
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RetentionStrategy(str, Enum):
    """Strategies for context retention."""
    FIFO = "fifo"  # First-in-first-out
    LRU = "lru"  # Least recently used
    PRIORITY = "priority"  # Priority-based
    HYBRID = "hybrid"  # Combination of strategies


@dataclass
class ContextItem:
    """A single item in the context."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    role: str = "user"  # user, assistant, system
    priority: ContextPriority = ContextPriority.MEDIUM
    tokens: int = 0
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)
    compressed: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "role": self.role,
            "priority": self.priority.value,
            "tokens": self.tokens,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "metadata": self.metadata,
            "compressed": self.compressed,
        }


@dataclass
class ContextWindow:
    """A context window for a conversation."""
    conversation_id: str
    items: List[ContextItem] = field(default_factory=list)
    max_tokens: int = 4000
    current_tokens: int = 0
    retention_strategy: RetentionStrategy = RetentionStrategy.HYBRID
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "items": [item.to_dict() for item in self.items],
            "max_tokens": self.max_tokens,
            "current_tokens": self.current_tokens,
            "retention_strategy": self.retention_strategy.value,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


class ContextManager:
    """Context window management with compression and prioritization.

    Manages context windows for conversations, handles automatic
    compression when limits are reached, and implements smart
    retention strategies.
    """

    def __init__(self):
        self._contexts: Dict[str, ContextWindow] = {}
        self._compression_threshold = 0.8  # Compress at 80% capacity
        self._default_max_tokens = 4000
        self._token_ratio = 4  # Approximate tokens per character

    def create_context(
        self,
        conversation_id: str,
        max_tokens: Optional[int] = None,
        retention_strategy: RetentionStrategy = RetentionStrategy.HYBRID,
    ) -> ContextWindow:
        """Create a new context window."""
        context = ContextWindow(
            conversation_id=conversation_id,
            max_tokens=max_tokens or self._default_max_tokens,
            retention_strategy=retention_strategy,
        )
        self._contexts[conversation_id] = context
        logger.info("Created context for conversation: %s", conversation_id)
        return context

    def get_context(self, conversation_id: str) -> Optional[ContextWindow]:
        """Get context window for a conversation."""
        return self._contexts.get(conversation_id)

    async def add_context_item(
        self,
        conversation_id: str,
        content: str,
        role: str = "user",
        priority: ContextPriority = ContextPriority.MEDIUM,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> ContextItem:
        """Add an item to the context.

        Args:
            conversation_id: Conversation ID
            content: Content to add
            role: Role (user, assistant, system)
            priority: Priority level
            metadata: Additional metadata

        Returns:
            The added context item
        """
        context = self._contexts.get(conversation_id)
        if not context:
            context = self.create_context(conversation_id)

        # Estimate token count
        tokens = self._estimate_tokens(content)

        item = ContextItem(
            content=content,
            role=role,
            priority=priority,
            tokens=tokens,
            metadata=metadata or {},
        )

        # Check if we need to compress first
        if context.current_tokens + tokens > context.max_tokens * self._compression_threshold:
            await self._compress_context(context)

        # Add the item
        context.items.append(item)
        context.current_tokens += tokens
        context.last_updated = datetime.now(timezone.utc)

        # Check if we exceeded the limit and need to prune
        if context.current_tokens > context.max_tokens:
            await self._prune_context(context)

        logger.debug(
            "Added context item to %s: %d tokens (total: %d/%d)",
            conversation_id,
            tokens,
            context.current_tokens,
            context.max_tokens,
        )

        return item

    def _estimate_tokens(self, text: str) -> int:
        """Estimate token count from text."""
        # Simple approximation: ~4 characters per token
        return max(1, len(text) // self._token_ratio)

    async def _compress_context(self, context: ContextWindow) -> None:
        """Compress context items to free up space."""
        logger.info("Compressing context for %s", context.conversation_id)

        # Find items that can be compressed
        compressible = [
            item for item in context.items
            if not item.compressed and item.priority in (ContextPriority.LOW, ContextPriority.MEDIUM)
        ]

        if not compressible:
            return

        # Compress items (simple truncation for now)
        for item in compressible[:len(compressible)//2]:
            if len(item.content) > 200:
                original_length = len(item.content)
                item.content = item.content[:100] + "... [compressed] ..." + item.content[-50:]
                item.compressed = True
                new_tokens = self._estimate_tokens(item.content)
                saved_tokens = item.tokens - new_tokens
                item.tokens = new_tokens
                context.current_tokens -= saved_tokens

        context.last_updated = datetime.now(timezone.utc)

    async def _prune_context(self, context: ContextWindow) -> None:
        """Prune context items based on retention strategy."""
        logger.info("Pruning context for %s", context.conversation_id)

        target_tokens = int(context.max_tokens * 0.7)  # Target 70% capacity

        while context.current_tokens > target_tokens and context.items:
            # Select item to remove based on strategy
            item_to_remove = self._select_item_for_removal(context)

            if item_to_remove:
                context.items.remove(item_to_remove)
                context.current_tokens -= item_to_remove.tokens
            else:
                break

        context.last_updated = datetime.now(timezone.utc)

    def _select_item_for_removal(self, context: ContextWindow) -> Optional[ContextItem]:
        """Select an item to remove based on retention strategy."""
        strategy = context.retention_strategy

        if strategy == RetentionStrategy.FIFO:
            # Remove oldest
            return context.items[0] if context.items else None

        elif strategy == RetentionStrategy.LRU:
            # Remove least recently used
            return min(context.items, key=lambda x: x.last_accessed)

        elif strategy == RetentionStrategy.PRIORITY:
            # Remove lowest priority
            low_priority = [i for i in context.items if i.priority == ContextPriority.LOW]
            if low_priority:
                return min(low_priority, key=lambda x: x.last_accessed)
            medium_priority = [i for i in context.items if i.priority == ContextPriority.MEDIUM]
            if medium_priority:
                return min(medium_priority, key=lambda x: x.last_accessed)
            return None

        elif strategy == RetentionStrategy.HYBRID:
            # Combine priority and recency
            # Score = priority_weight * priority_score + recency_weight * recency_score
            priority_scores = {
                ContextPriority.CRITICAL: 4,
                ContextPriority.HIGH: 3,
                ContextPriority.MEDIUM: 2,
                ContextPriority.LOW: 1,
            }

            def score_item(item: ContextItem) -> float:
                priority_score = priority_scores.get(item.priority, 1)
                # More recent = higher score
                age_hours = (datetime.now(timezone.utc) - item.last_accessed).total_seconds() / 3600
                recency_score = max(0, 10 - age_hours)  # Decay over 10 hours
                return (priority_score * 0.6) + (recency_score * 0.4)

            scored = [(item, score_item(item)) for item in context.items]
            scored.sort(key=lambda x: x[1])  # Lowest score first
            return scored[0][0] if scored else None

        return None

    async def get_context_string(
        self,
        conversation_id: str,
        include_system: bool = True,
        max_tokens: Optional[int] = None,
    ) -> str:
        """Get the context as a formatted string.

        Args:
            conversation_id: Conversation ID
            include_system: Whether to include system messages
            max_tokens: Optional token limit for the output

        Returns:
            Formatted context string
        """
        context = self._contexts.get(conversation_id)
        if not context:
            return ""

        items = context.items

        if not include_system:
            items = [i for i in items if i.role != "system"]

        # Update access times
        now = datetime.now(timezone.utc)
        for item in items:
            item.last_accessed = now
            item.access_count += 1

        # Build context string
        lines = []
        current_tokens = 0
        token_limit = max_tokens or context.max_tokens

        for item in items:
            if current_tokens + item.tokens > token_limit:
                break

            lines.append(f"{item.role}: {item.content}")
            current_tokens += item.tokens

        return "\n".join(lines)

    async def get_context_items(
        self,
        conversation_id: str,
        role: Optional[str] = None,
        priority: Optional[ContextPriority] = None,
        limit: Optional[int] = None,
    ) -> List[ContextItem]:
        """Get context items with optional filtering."""
        context = self._contexts.get(conversation_id)
        if not context:
            return []

        items = context.items

        if role:
            items = [i for i in items if i.role == role]

        if priority:
            items = [i for i in items if i.priority == priority]

        if limit:
            items = items[-limit:]

        return items

    async def update_item_priority(
        self,
        conversation_id: str,
        item_id: str,
        priority: ContextPriority,
    ) -> bool:
        """Update the priority of a context item."""
        context = self._contexts.get(conversation_id)
        if not context:
            return False

        for item in context.items:
            if item.id == item_id:
                item.priority = priority
                context.last_updated = datetime.now(timezone.utc)
                return True

        return False

    async def clear_context(self, conversation_id: str) -> bool:
        """Clear all context items for a conversation."""
        context = self._contexts.get(conversation_id)
        if not context:
            return False

        context.items.clear()
        context.current_tokens = 0
        context.last_updated = datetime.now(timezone.utc)

        logger.info("Cleared context for conversation: %s", conversation_id)
        return True

    async def delete_context(self, conversation_id: str) -> bool:
        """Delete a context window entirely."""
        if conversation_id in self._contexts:
            del self._contexts[conversation_id]
            logger.info("Deleted context for conversation: %s", conversation_id)
            return True
        return False

    async def summarize_context(
        self,
        conversation_id: str,
    ) -> str:
        """Generate a summary of the context."""
        context = self._contexts.get(conversation_id)
        if not context:
            return ""

        if not context.items:
            return "Empty context"

        # Simple summary: count items by role and priority
        role_counts = {}
        priority_counts = {}

        for item in context.items:
            role_counts[item.role] = role_counts.get(item.role, 0) + 1
            priority_counts[item.priority.value] = priority_counts.get(item.priority.value, 0) + 1

        summary_parts = [
            f"Context contains {len(context.items)} items",
            f"Total tokens: {context.current_tokens}/{context.max_tokens}",
            f"Roles: {role_counts}",
            f"Priorities: {priority_counts}",
        ]

        return ". ".join(summary_parts)

    def get_statistics(self) -> Dict[str, Any]:
        """Get context manager statistics."""
        return {
            "total_contexts": len(self._contexts),
            "total_items": sum(len(c.items) for c in self._contexts.values()),
            "total_tokens": sum(c.current_tokens for c in self._contexts.values()),
            "retention_strategies": {
                strategy.value: len([c for c in self._contexts.values() if c.retention_strategy == strategy])
                for strategy in RetentionStrategy
            },
        }

    async def export_context(
        self,
        conversation_id: str,
    ) -> Optional[Dict[str, Any]]:
        """Export context as a serializable dict."""
        context = self._contexts.get(conversation_id)
        if not context:
            return None

        return context.to_dict()

    async def import_context(
        self,
        data: Dict[str, Any],
    ) -> ContextWindow:
        """Import context from a dict."""
        conversation_id = data.get("conversation_id")
        if not conversation_id:
            raise ValueError("conversation_id is required")

        context = ContextWindow(
            conversation_id=conversation_id,
            max_tokens=data.get("max_tokens", self._default_max_tokens),
            retention_strategy=RetentionStrategy(data.get("retention_strategy", "hybrid")),
        )

        # Import items
        for item_data in data.get("items", []):
            item = ContextItem(
                content=item_data.get("content", ""),
                role=item_data.get("role", "user"),
                priority=ContextPriority(item_data.get("priority", "medium")),
                tokens=item_data.get("tokens", 0),
                metadata=item_data.get("metadata", {}),
                compressed=item_data.get("compressed", False),
            )
            context.items.append(item)
            context.current_tokens += item.tokens

        self._contexts[conversation_id] = context
        logger.info("Imported context for conversation: %s", conversation_id)
        return context
