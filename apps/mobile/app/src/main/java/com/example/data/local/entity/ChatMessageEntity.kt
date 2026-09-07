package com.example.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "chat_messages")
data class ChatMessageEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val sender: String, // "USER" or "DASH"
    val content: String,
    val timestamp: Long = System.currentTimeMillis(),
    val timeFormatted: String = "10:42 AM",
    val toolExecutionInfo: String? = null, // e.g. "✓ Backend  ✓ Flutter  ● Tests"
    val isExecuting: Boolean = false,
    val isCodeSnippet: Boolean = false,
    val codeLanguage: String? = null
)
