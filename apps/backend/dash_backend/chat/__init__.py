"""Chat service for AI conversations."""

from dash_backend.chat.service import (
    create_conversation,
    get_conversation,
    get_user_conversations,
    search_conversations,
    update_conversation,
    archive_conversation,
    delete_conversation,
    get_conversation_messages,
    add_message,
    save_user_message,
    save_assistant_message,
    get_message,
    update_message,
    delete_message,
    count_messages,
)

__all__ = [
    "create_conversation",
    "get_conversation",
    "get_user_conversations",
    "search_conversations",
    "update_conversation",
    "archive_conversation",
    "delete_conversation",
    "get_conversation_messages",
    "add_message",
    "save_user_message",
    "save_assistant_message",
    "get_message",
    "update_message",
    "delete_message",
    "count_messages",
]
