package com.aistudio.dashcompanion.data.model

import com.squareup.moshi.Json
import com.squareup.moshi.JsonClass

@JsonClass(generateAdapter = true)
data class ChatMessage(
    @Json(name = "id") val id: String = "",
    @Json(name = "conversation_id") val conversationId: String? = null,
    @Json(name = "role") val role: MessageRole = MessageRole.USER,
    @Json(name = "content") val content: String = "",
    @Json(name = "timestamp") val timestamp: Long = System.currentTimeMillis(),
    @Json(name = "is_streaming") val isStreaming: Boolean = false
)

@JsonClass(generateAdapter = true)
enum class MessageRole {
    @Json(name = "user") USER,
    @Json(name = "assistant") ASSISTANT,
    @Json(name = "system") SYSTEM
}

@JsonClass(generateAdapter = true)
data class Conversation(
    @Json(name = "id") val id: String = "",
    @Json(name = "title") val title: String = "",
    @Json(name = "created_at") val createdAt: Long = System.currentTimeMillis(),
    @Json(name = "updated_at") val updatedAt: Long = System.currentTimeMillis()
)

@JsonClass(generateAdapter = true)
data class ChatRequest(
    @Json(name = "type") val type: String = "chat.send",
    @Json(name = "message_id") val messageId: String = "",
    @Json(name = "conversation_id") val conversationId: String? = null,
    @Json(name = "content") val content: String = ""
)

@JsonClass(generateAdapter = true)
data class ChatResponse(
    @Json(name = "type") val type: String = "",
    @Json(name = "message_id") val messageId: String? = null,
    @Json(name = "conversation_id") val conversationId: String? = null,
    @Json(name = "content") val content: String = "",
    @Json(name = "done") val done: Boolean = false
)
