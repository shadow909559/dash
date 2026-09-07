package com.example.data.local.entity

import androidx.room.Entity
import androidx.room.PrimaryKey

@Entity(tableName = "agents")
data class AgentEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val name: String,
    val goal: String,
    val currentTask: String,
    val progressPercent: Int = 0, // 0-100, or -1 for indeterminate
    val status: String = "RUNNING", // "RUNNING", "IDLE", "PAUSED", "COMPLETED", "FAILED"
    val iconType: String = "TERMINAL", // "TERMINAL", "EXPLORE", "SETTINGS", "MONITOR"
    val toolsUsed: String = "AST Parser, Git, TestRunner",
    val permissionLevel: Int = 1,
    val model: String = "qwen2.5-coder",
    val lastUpdated: Long = System.currentTimeMillis()
)

@Entity(tableName = "approvals")
data class ApprovalEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val title: String,
    val category: String, // "HIGH SECURITY", "SYSTEM CONFIG", "PRIVILEGED COMMAND", "FILE SYSTEM"
    val reason: String,
    val diffOrCommand: String,
    val status: String = "PENDING", // "PENDING", "APPROVED", "REJECTED"
    val timeAgo: String = "2m ago",
    val permissionLevel: Int = 2,
    val timestamp: Long = System.currentTimeMillis()
)

@Entity(tableName = "memories")
data class MemoryEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val category: String, // "Personal", "Projects", "Preferences", "Technical", "Tasks", "Important"
    val title: String,
    val details: String,
    val confidenceScore: Float = 0.95f,
    val dateAdded: String = "Aug 2026",
    val timestamp: Long = System.currentTimeMillis()
)

@Entity(tableName = "projects")
data class ProjectEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val name: String,
    val description: String,
    val gitBranch: String = "main",
    val gitStatus: String = "Clean (3 unpushed commits)",
    val backendStatus: String = "FastAPI :8000 ● Online",
    val frontendStatus: String = "Flutter Desktop ● Active",
    val buildStatus: String = "Build #42 Passing",
    val activeIssuesCount: Int = 0,
    val recentActivity: String = "Refactored tool calling orchestration",
    val timestamp: Long = System.currentTimeMillis()
)

@Entity(tableName = "tasks")
data class TaskItemEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val title: String,
    val category: String = "TODAY",
    val isCompleted: Boolean = false,
    val priority: String = "HIGH", // "LOW", "MEDIUM", "HIGH"
    val dueDate: String = "Today, 5:00 PM",
    val timestamp: Long = System.currentTimeMillis()
)

@Entity(tableName = "audit_logs")
data class AuditLogEntity(
    @PrimaryKey(autoGenerate = true)
    val id: Long = 0,
    val timeFormatted: String,
    val event: String,
    val detail: String,
    val actor: String = "DASH",
    val status: String = "SUCCESS",
    val timestamp: Long = System.currentTimeMillis()
)
