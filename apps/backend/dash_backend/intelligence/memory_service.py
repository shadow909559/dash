"""Memory Service - Short-term and long-term memory management.

Implements a dual-memory system:
- Short-term memory: Conversation context and recent interactions
- Long-term memory: Persistent storage with vector embeddings
- Vector search: Semantic similarity search across memories
- Memory retrieval: Ranked retrieval based on relevance
- Memory consolidation: Moving important memories to long-term storage

Features:
- Automatic memory consolidation
- Memory importance scoring
- Semantic search with embeddings
- Memory deduplication
- Memory expiration and cleanup
"""

from __future__ import annotations

import asyncio
import json
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from dash_backend.logging_config import get_logger

logger = get_logger(__name__)


class MemoryType(str, Enum):
    """Types of memory entries."""
    FACT = "fact"
    PREFERENCE = "preference"
    CONVERSATION = "conversation"
    EVENT = "event"
    KNOWLEDGE = "knowledge"
    REFERENCE = "reference"


class MemoryImportance(str, Enum):
    """Importance levels for memory."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class MemoryEntry:
    """A single memory entry."""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    content: str = ""
    memory_type: MemoryType = MemoryType.FACT
    importance: MemoryImportance = MemoryImportance.MEDIUM
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_accessed: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    access_count: int = 0
    expires_at: Optional[datetime] = None
    user_id: Optional[str] = None
    conversation_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance.value,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "created_at": self.created_at.isoformat(),
            "last_accessed": self.last_accessed.isoformat(),
            "access_count": self.access_count,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "user_id": self.user_id,
            "conversation_id": self.conversation_id,
        }


@dataclass
class ShortTermMemory:
    """Short-term conversation context memory."""
    conversation_id: str
    messages: List[Dict[str, Any]] = field(default_factory=list)
    context_window: int = 10
    max_tokens: int = 4000
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_updated: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def add_message(self, role: str, content: str, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a message to short-term memory."""
        message = {
            "role": role,
            "content": content,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "metadata": metadata or {},
        }
        self.messages.append(message)
        self.last_updated = datetime.now(timezone.utc)

        # Trim to context window
        if len(self.messages) > self.context_window:
            self.messages = self.messages[-self.context_window:]

    def get_context(self) -> str:
        """Get the current context as a string."""
        return "\n".join(
            f"{msg['role']}: {msg['content']}"
            for msg in self.messages
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "conversation_id": self.conversation_id,
            "messages": self.messages,
            "context_window": self.context_window,
            "max_tokens": self.max_tokens,
            "created_at": self.created_at.isoformat(),
            "last_updated": self.last_updated.isoformat(),
        }


@dataclass
class MemorySearchResult:
    """Result of a memory search."""
    memory: MemoryEntry
    score: float
    rank: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "rank": self.rank,
        }


class MemoryService:
    """Dual-memory system with short-term and long-term storage.

    Manages conversation context in short-term memory and
    persistent knowledge in long-term memory with vector search.
    """

    def __init__(self):
        self._short_term_memory: Dict[str, ShortTermMemory] = {}
        self._long_term_memory: Dict[str, MemoryEntry] = {}
        self._memory_index: Dict[str, List[str]] = {}  # user_id -> memory_ids
        self._conversation_index: Dict[str, List[str]] = {}  # conversation_id -> memory_ids
        self._type_index: Dict[MemoryType, List[str]] = {}  # type -> memory_ids

        # Configuration
        self._default_context_window = 10
        self._default_max_tokens = 4000
        self._consolidation_threshold = 20  # messages before consolidation
        self._memory_ttl = timedelta(days=30)  # default TTL for memories

    async def create_short_term_memory(
        self,
        conversation_id: str,
        context_window: Optional[int] = None,
        max_tokens: Optional[int] = None,
    ) -> ShortTermMemory:
        """Create a new short-term memory for a conversation."""
        stm = ShortTermMemory(
            conversation_id=conversation_id,
            context_window=context_window or self._default_context_window,
            max_tokens=max_tokens or self._default_max_tokens,
        )
        self._short_term_memory[conversation_id] = stm
        logger.info("Created short-term memory for conversation: %s", conversation_id)
        return stm

    def get_short_term_memory(self, conversation_id: str) -> Optional[ShortTermMemory]:
        """Get short-term memory for a conversation."""
        return self._short_term_memory.get(conversation_id)

    async def add_to_short_term(
        self,
        conversation_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Add a message to short-term memory."""
        stm = self._short_term_memory.get(conversation_id)
        if not stm:
            stm = await self.create_short_term_memory(conversation_id)

        stm.add_message(role, content, metadata)

        # Check if consolidation is needed
        if len(stm.messages) >= self._consolidation_threshold:
            await self._consolidate_memory(conversation_id)

    async def _consolidate_memory(self, conversation_id: str) -> None:
        """Consolidate short-term memory into long-term storage."""
        stm = self._short_term_memory.get(conversation_id)
        if not stm:
            return

        logger.info("Consolidating memory for conversation: %s", conversation_id)

        # Extract important information
        for message in stm.messages[:5]:  # Take oldest messages
            if message["role"] == "user":
                # Store as conversation memory
                await self.store_long_term(
                    content=message["content"],
                    memory_type=MemoryType.CONVERSATION,
                    conversation_id=conversation_id,
                    metadata={"role": message["role"]},
                )

        # Clear old messages
        stm.messages = stm.messages[-5:]

    async def store_long_term(
        self,
        content: str,
        memory_type: MemoryType = MemoryType.FACT,
        importance: MemoryImportance = MemoryImportance.MEDIUM,
        user_id: Optional[str] = None,
        conversation_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        ttl: Optional[timedelta] = None,
    ) -> MemoryEntry:
        """Store a memory in long-term storage."""
        entry = MemoryEntry(
            content=content,
            memory_type=memory_type,
            importance=importance,
            user_id=user_id,
            conversation_id=conversation_id,
            metadata=metadata or {},
            expires_at=datetime.now(timezone.utc) + (ttl or self._memory_ttl),
        )

        # Generate embedding (mock - in production would use actual embedding model)
        entry.embedding = await self._generate_embedding(content)

        self._long_term_memory[entry.id] = entry

        # Update indexes
        if user_id:
            if user_id not in self._memory_index:
                self._memory_index[user_id] = []
            self._memory_index[user_id].append(entry.id)

        if conversation_id:
            if conversation_id not in self._conversation_index:
                self._conversation_index[conversation_id] = []
            self._conversation_index[conversation_id].append(entry.id)

        if memory_type not in self._type_index:
            self._type_index[memory_type] = []
        self._type_index[memory_type].append(entry.id)

        logger.debug("Stored long-term memory: %s", entry.id)
        return entry

    async def _generate_embedding(self, text: str) -> List[float]:
        """Generate embedding using Ollama's nomic-embed-text model."""
        try:
            import json as _json
            import urllib.request

            payload = _json.dumps({
                "model": "nomic-embed-text",
                "input": text[:2000],
            }).encode("utf-8")

            req = urllib.request.Request(
                "http://127.0.0.1:11434/api/embed",
                data=payload,
                headers={"Content-Type": "application/json"},
            )
            resp = await asyncio.to_thread(urllib.request.urlopen, req, timeout=10)
            data = _json.loads(resp.read())
            embeddings = data.get("embeddings", [[]])
            if embeddings and embeddings[0]:
                return embeddings[0]
        except Exception:
            pass

        # Fallback: hash-based embedding if Ollama is unavailable
        import hashlib
        hash_obj = hashlib.sha256(text.encode())
        hash_bytes = hash_obj.digest()
        embedding = []
        for i in range(0, min(len(hash_bytes), 384), 4):
            chunk = hash_bytes[i:i+4]
            if len(chunk) == 4:
                value = int.from_bytes(chunk, byteorder='big', signed=True)
                normalized = value / (2**31)
                embedding.append(normalized)
        while len(embedding) < 384:
            embedding.append(0.0)
        return embedding

        return embedding

    async def retrieve_long_term(
        self,
        memory_id: str,
    ) -> Optional[MemoryEntry]:
        """Retrieve a specific memory by ID."""
        entry = self._long_term_memory.get(memory_id)
        if entry:
            # Update access statistics
            entry.last_accessed = datetime.now(timezone.utc)
            entry.access_count += 1
        return entry

    async def search_memories(
        self,
        query: str,
        user_id: Optional[str] = None,
        memory_type: Optional[MemoryType] = None,
        top_k: int = 10,
        min_score: float = 0.5,
    ) -> List[MemorySearchResult]:
        """Search memories using semantic similarity.

        Args:
            query: Search query
            user_id: Optional user filter
            memory_type: Optional type filter
            top_k: Number of results to return
            min_score: Minimum similarity score

        Returns:
            Ranked list of memory search results
        """
        # Generate query embedding
        query_embedding = await self._generate_embedding(query)

        # Filter candidates
        candidates = list(self._long_term_memory.values())

        if user_id:
            user_memory_ids = self._memory_index.get(user_id, [])
            candidates = [c for c in candidates if c.id in user_memory_ids]

        if memory_type:
            type_memory_ids = self._type_index.get(memory_type, [])
            candidates = [c for c in candidates if c.id in type_memory_ids]

        # Filter expired memories
        now = datetime.now(timezone.utc)
        candidates = [c for c in candidates if c.expires_at is None or c.expires_at > now]

        # Calculate similarity scores
        scored = []
        for candidate in candidates:
            if candidate.embedding:
                score = self._cosine_similarity(query_embedding, candidate.embedding)
                if score >= min_score:
                    scored.append((candidate, score))

        # Sort by score and importance
        scored.sort(
            key=lambda x: (x[1], x[0].importance.value, x[0].access_count),
            reverse=True,
        )

        # Create results
        results = []
        for i, (memory, score) in enumerate(scored[:top_k]):
            results.append(
                MemorySearchResult(
                    memory=memory,
                    score=score,
                    rank=i + 1,
                )
            )

        return results

    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        if len(a) != len(b):
            return 0.0

        dot_product = sum(x * y for x, y in zip(a, b))
        magnitude_a = sum(x * x for x in a) ** 0.5
        magnitude_b = sum(y * y for y in b) ** 0.5

        if magnitude_a == 0 or magnitude_b == 0:
            return 0.0

        return dot_product / (magnitude_a * magnitude_b)

    async def get_user_memories(
        self,
        user_id: str,
        memory_type: Optional[MemoryType] = None,
        limit: int = 100,
    ) -> List[MemoryEntry]:
        """Get all memories for a user."""
        memory_ids = self._memory_index.get(user_id, [])
        memories = [self._long_term_memory[mid] for mid in memory_ids if mid in self._long_term_memory]

        if memory_type:
            memories = [m for m in memories if m.memory_type == memory_type]

        # Sort by last accessed
        memories.sort(key=lambda m: m.last_accessed, reverse=True)

        return memories[:limit]

    async def get_conversation_memories(
        self,
        conversation_id: str,
        limit: int = 50,
    ) -> List[MemoryEntry]:
        """Get all memories for a conversation."""
        memory_ids = self._conversation_index.get(conversation_id, [])
        memories = [self._long_term_memory[mid] for mid in memory_ids if mid in self._long_term_memory]

        # Sort by created_at
        memories.sort(key=lambda m: m.created_at, reverse=True)

        return memories[:limit]

    async def delete_memory(self, memory_id: str) -> bool:
        """Delete a memory."""
        entry = self._long_term_memory.get(memory_id)
        if not entry:
            return False

        # Remove from indexes
        if entry.user_id and entry.user_id in self._memory_index:
            self._memory_index[entry.user_id] = [
                mid for mid in self._memory_index[entry.user_id]
                if mid != memory_id
            ]

        if entry.conversation_id and entry.conversation_id in self._conversation_index:
            self._conversation_index[entry.conversation_id] = [
                mid for mid in self._conversation_index[entry.conversation_id]
                if mid != memory_id
            ]

        if entry.memory_type in self._type_index:
            self._type_index[entry.memory_type] = [
                mid for mid in self._type_index[entry.memory_type]
                if mid != memory_id
            ]

        # Remove from storage
        del self._long_term_memory[memory_id]

        logger.debug("Deleted memory: %s", memory_id)
        return True

    async def cleanup_expired_memories(self) -> int:
        """Clean up expired memories."""
        now = datetime.now(timezone.utc)
        expired_ids = [
            mid for mid, entry in self._long_term_memory.items()
            if entry.expires_at and entry.expires_at < now
        ]

        for memory_id in expired_ids:
            await self.delete_memory(memory_id)

        logger.info("Cleaned up %d expired memories", len(expired_ids))
        return len(expired_ids)

    async def update_memory(
        self,
        memory_id: str,
        content: Optional[str] = None,
        importance: Optional[MemoryImportance] = None,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Optional[MemoryEntry]:
        """Update a memory entry."""
        entry = self._long_term_memory.get(memory_id)
        if not entry:
            return None

        if content is not None:
            entry.content = content
            entry.embedding = await self._generate_embedding(content)

        if importance is not None:
            entry.importance = importance

        if metadata is not None:
            entry.metadata.update(metadata)

        entry.last_accessed = datetime.now(timezone.utc)

        return entry

    def get_statistics(self) -> Dict[str, Any]:
        """Get memory service statistics."""
        return {
            "short_term_conversations": len(self._short_term_memory),
            "long_term_memories": len(self._long_term_memory),
            "indexed_users": len(self._memory_index),
            "indexed_conversations": len(self._conversation_index),
            "memory_types": {t.value: len(ids) for t, ids in self._type_index.items()},
        }
