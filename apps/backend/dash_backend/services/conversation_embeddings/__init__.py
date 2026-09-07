"""Conversation embedding service for semantic search across conversations."""

from dash_backend.services.conversation_embeddings.service import (
    ConversationEmbeddingService,
    get_conversation_embedding_service,
)

__all__ = ["ConversationEmbeddingService", "get_conversation_embedding_service"]
