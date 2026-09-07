"""Conversation embedding service for semantic search across conversations."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any, Dict, List, Optional

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from dash_backend.db.models.conversation import Conversation
from dash_backend.db.models.message import Message
from dash_backend.db.models.conversation_summary import ConversationSummary
from dash_backend.logging_config import get_logger
from dash_backend.memory.embeddings import get_embedding

logger = get_logger(__name__)


class ConversationEmbeddingService:
    """Service for embedding conversations and enabling semantic search.
    
    This service:
    - Embeds conversation messages for semantic search
    - Embeds conversation summaries
    - Enables finding similar conversations
    - Maintains embedding freshness
    """
    
    def __init__(self):
        self._embedding_batch_size = 10
        
    async def embed_conversation(
        self,
        session: AsyncSession,
        conversation_id: str | uuid.UUID,
    ) -> Optional[List[float]]:
        """Generate and store embedding for a conversation.
        
        Embeds the full conversation text (all messages) for semantic search.
        
        Args:
            session: Database session
            conversation_id: Conversation ID to embed
            
        Returns:
            Embedding vector or None if failed
        """
        cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        
        # Get conversation with messages
        stmt = select(Conversation).where(Conversation.id == cid)
        result = await session.execute(stmt)
        conversation = result.scalar_one_or_none()
        
        if not conversation:
            logger.warning("Conversation %s not found for embedding", cid)
            return None
        
        # Get all messages
        msg_stmt = select(Message).where(
            Message.conversation_id == cid
        ).order_by(Message.created_at)
        msg_result = await session.execute(msg_stmt)
        messages = list(msg_result.scalars().all())
        
        if not messages:
            logger.info("No messages in conversation %s", cid)
            return None
        
        # Build conversation text
        conversation_text = self._build_conversation_text(messages)
        
        # Generate embedding
        embedding = await get_embedding(conversation_text)
        
        if embedding is None:
            logger.warning("Failed to generate embedding for conversation %s", cid)
            return None
        
        # Store embedding in conversation metadata
        try:
            meta = conversation.meta or {}
            meta["embedding"] = embedding
            meta["embedding_updated_at"] = datetime.now(UTC).isoformat()
            
            update_stmt = update(Conversation).where(
                Conversation.id == cid
            ).values(meta=meta)
            
            await session.execute(update_stmt)
            await session.commit()
            
            logger.info("Embedded conversation %s (%d messages)", cid, len(messages))
            return embedding
            
        except Exception as e:
            logger.error("Failed to store embedding for conversation %s: %s", cid, e)
            await session.rollback()
            return None
    
    async def embed_conversation_summary(
        self,
        session: AsyncSession,
        conversation_id: str | uuid.UUID,
    ) -> Optional[List[float]]:
        """Generate and store embedding for conversation summary.
        
        Args:
            session: Database session
            conversation_id: Conversation ID
            
        Returns:
            Embedding vector or None if failed
        """
        cid = uuid.UUID(conversation_id) if isinstance(conversation_id, str) else conversation_id
        
        # Get conversation summary
        stmt = select(ConversationSummary).where(
            ConversationSummary.conversation_id == cid
        )
        result = await session.execute(stmt)
        summary = result.scalar_one_or_none()
        
        if not summary or not summary.summary_text:
            logger.info("No summary found for conversation %s", cid)
            return None
        
        # Generate embedding
        embedding = await get_embedding(summary.summary_text)
        
        if embedding is None:
            logger.warning("Failed to generate embedding for summary %s", cid)
            return None
        
        # Store embedding
        try:
            update_stmt = update(ConversationSummary).where(
                ConversationSummary.conversation_id == cid
            ).values(embedding=embedding)
            
            await session.execute(update_stmt)
            await session.commit()
            
            logger.info("Embedded summary for conversation %s", cid)
            return embedding
            
        except Exception as e:
            logger.error("Failed to store summary embedding for conversation %s: %s", cid, e)
            await session.rollback()
            return None
    
    async def search_similar_conversations(
        self,
        session: AsyncSession,
        user_id: str | uuid.UUID,
        query: str,
        limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search for conversations similar to the query.
        
        Args:
            session: Database session
            user_id: User ID
            query: Search query
            limit: Maximum results
            
        Returns:
            List of similar conversations with similarity scores
        """
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        # Generate query embedding
        query_embedding = await get_embedding(query)
        if query_embedding is None:
            logger.warning("Failed to generate query embedding")
            return []
        
        # Get all user conversations with embeddings
        stmt = select(Conversation).where(
            Conversation.user_id == uid,
            Conversation.meta.isnot(None),
        )
        result = await session.execute(stmt)
        conversations = list(result.scalars().all())
        
        # Calculate similarities
        similar = []
        for conv in conversations:
            conv_embedding = conv.meta.get("embedding") if conv.meta else None
            if not conv_embedding:
                continue
            
            similarity = self._cosine_similarity(query_embedding, conv_embedding)
            if similarity > 0.3:  # Threshold for relevance
                similar.append({
                    "conversation": conv,
                    "similarity": similarity,
                })
        
        # Sort by similarity
        similar.sort(key=lambda x: x["similarity"], reverse=True)
        
        # Return top results
        results = []
        for item in similar[:limit]:
            conv = item["conversation"]
            results.append({
                "id": str(conv.id),
                "title": conv.title,
                "similarity": item["similarity"],
                "created_at": conv.created_at.isoformat() if conv.created_at else None,
                "message_count": conv.message_count,
            })
        
        return results
    
    async def batch_embed_conversations(
        self,
        session: AsyncSession,
        user_id: str | uuid.UUID,
        limit: int = 100,
    ) -> Dict[str, Any]:
        """Batch embed conversations for a user.
        
        Args:
            session: Database session
            user_id: User ID
            limit: Maximum conversations to process
            
        Returns:
            Statistics about the batch operation
        """
        uid = uuid.UUID(user_id) if isinstance(user_id, str) else user_id
        
        # Get conversations without embeddings
        stmt = select(Conversation).where(
            Conversation.user_id == uid,
        ).order_by(Conversation.created_at.desc()).limit(limit)
        
        result = await session.execute(stmt)
        conversations = list(result.scalars().all())
        
        stats = {
            "total": len(conversations),
            "success": 0,
            "failed": 0,
            "skipped": 0,
        }
        
        for conv in conversations:
            # Check if already embedded
            if conv.meta and conv.meta.get("embedding"):
                stats["skipped"] += 1
                continue
            
            # Try to embed
            embedding = await self.embed_conversation(session, conv.id)
            if embedding:
                stats["success"] += 1
            else:
                stats["failed"] += 1
        
        logger.info(
            "Batch embedding complete: %d total, %d success, %d failed, %d skipped",
            stats["total"],
            stats["success"],
            stats["failed"],
            stats["skipped"],
        )
        
        return stats
    
    def _build_conversation_text(self, messages: List[Message]) -> str:
        """Build searchable text from conversation messages."""
        parts = []
        for msg in messages:
            role = msg.role.value if hasattr(msg.role, 'value') else str(msg.role)
            content = msg.content or ""
            parts.append(f"{role}: {content}")
        return "\n".join(parts)
    
    def _cosine_similarity(self, a: List[float], b: List[float]) -> float:
        """Calculate cosine similarity between two vectors."""
        import math
        
        if not a or not b or len(a) != len(b):
            return 0.0
        
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = math.sqrt(sum(x * x for x in a))
        norm_b = math.sqrt(sum(y * y for y in b))
        
        if norm_a == 0 or norm_b == 0:
            return 0.0
        
        return dot / (norm_a * norm_b)


# Singleton
_conversation_embedding_service: Optional[ConversationEmbeddingService] = None


def get_conversation_embedding_service() -> ConversationEmbeddingService:
    global _conversation_embedding_service
    if _conversation_embedding_service is None:
        _conversation_embedding_service = ConversationEmbeddingService()
    return _conversation_embedding_service
