package com.example.data.local

import android.content.Context
import androidx.room.Database
import androidx.room.Room
import androidx.room.RoomDatabase
import androidx.sqlite.db.SupportSQLiteDatabase
import com.example.data.local.dao.DashDao
import com.example.data.local.entity.AgentEntity
import com.example.data.local.entity.ApprovalEntity
import com.example.data.local.entity.AuditLogEntity
import com.example.data.local.entity.NotificationEntity
import com.example.data.local.entity.ChatMessageEntity
import com.example.data.local.entity.MemoryEntity
import com.example.data.local.entity.ProjectEntity
import com.example.data.local.entity.TaskItemEntity
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Database(
    entities = [
        ChatMessageEntity::class,
        AgentEntity::class,
        ApprovalEntity::class,
        MemoryEntity::class,
        ProjectEntity::class,
        TaskItemEntity::class,
        AuditLogEntity::class,
        NotificationEntity::class
    ],
    version = 2,
    exportSchema = false
)
abstract class DashDatabase : RoomDatabase() {
    abstract fun dashDao(): DashDao

    companion object {
        @Volatile
        private var INSTANCE: DashDatabase? = null

        fun getDatabase(context: Context, scope: CoroutineScope): DashDatabase {
            return INSTANCE ?: synchronized(this) {
                val instance = Room.databaseBuilder(
                    context.applicationContext,
                    DashDatabase::class.java,
                    "dash_companion.db"
                )
                .addCallback(DashDatabaseCallback(scope))
                .fallbackToDestructiveMigration()
                .build()
                INSTANCE = instance
                instance
            }
        }
    }

    private class DashDatabaseCallback(
        private val scope: CoroutineScope
    ) : RoomDatabase.Callback() {
        override fun onCreate(db: SupportSQLiteDatabase) {
            super.onCreate(db)
            INSTANCE?.let { database ->
                scope.launch(Dispatchers.IO) {
                    populateInitialData(database.dashDao())
                }
            }
        }

        suspend fun populateInitialData(dao: DashDao) {
            // Initial Chat
            dao.insertMessage(
                ChatMessageEntity(
                    sender = "USER",
                    content = "Can you review the latest PR and run the test suite?",
                    timeFormatted = "10:42 AM"
                )
            )
            dao.insertMessage(
                ChatMessageEntity(
                    sender = "DASH",
                    content = "I'm on it. Reviewing PR #402 and initializing the test suite. Give me a moment to process the recent commits.",
                    timeFormatted = "10:42 AM",
                    toolExecutionInfo = "✓ Analyzing project dependencies...\n✓ Reviewing PR diffs...\n● Running e2e test suite (All passing)"
                )
            )

            // Initial Agents
            dao.insertAgent(
                AgentEntity(
                    name = "Coding Agent",
                    goal = "Refactor main UI components and optimize AST nodes",
                    currentTask = "Optimizing AST nodes and eliminating layout jitter...",
                    progressPercent = 80,
                    status = "RUNNING",
                    iconType = "TERMINAL",
                    toolsUsed = "AST Parser, Git, Kotlin Compiler",
                    permissionLevel = 1,
                    model = "qwen2.5-coder"
                )
            )
            dao.insertAgent(
                AgentEntity(
                    name = "Research Agent",
                    goal = "Analyze market trends and latest LLM benchmarks for Q3",
                    currentTask = "Searching external technical sources and summarization...",
                    progressPercent = -1,
                    status = "RUNNING",
                    iconType = "EXPLORE",
                    toolsUsed = "Web Scraper, Semantic Search, PDF Parser",
                    permissionLevel = 0,
                    model = "llama3.2:3b"
                )
            )
            dao.insertAgent(
                AgentEntity(
                    name = "System Agent",
                    goal = "Monitor PC temperature, memory leaks, and background daemons",
                    currentTask = "Standing by. Next check in 4 minutes.",
                    progressPercent = 0,
                    status = "IDLE",
                    iconType = "SETTINGS",
                    toolsUsed = "WMI Telemetry, Disk Monitor, Task Manager",
                    permissionLevel = 1,
                    model = "llama3.2:3b"
                )
            )

            // Initial Approvals
            dao.insertApproval(
                ApprovalEntity(
                    title = "Modify project files",
                    category = "HIGH SECURITY",
                    reason = "Fix failing backend tests in auth provider router",
                    diffOrCommand = "- src/api/users.ts\n+ src/api/users.ts (modified lines 42-45)\n  validateTokenExpiry(token, clockDriftMs: 3000)",
                    status = "PENDING",
                    timeAgo = "2m ago",
                    permissionLevel = 2
                )
            )
            dao.insertApproval(
                ApprovalEntity(
                    title = "Update Environment Vars",
                    category = "SYSTEM CONFIG",
                    reason = "Sync with staging PostgreSQL database credentials",
                    diffOrCommand = "POSTGRES_HOST=staging-db.internal.net\nPOSTGRES_PORT=5432\nPOSTGRES_DB=dash_staging",
                    status = "PENDING",
                    timeAgo = "15m ago",
                    permissionLevel = 2
                )
            )
            dao.insertApproval(
                ApprovalEntity(
                    title = "Restart Backend Daemon",
                    category = "PRIVILEGED COMMAND",
                    reason = "Apply kernel patch and reload FastAPI worker processes",
                    diffOrCommand = "systemctl restart dash-backend.service --now",
                    status = "PENDING",
                    timeAgo = "25m ago",
                    permissionLevel = 3
                )
            )

            // Initial Memories
            dao.insertMemory(
                MemoryEntity(
                    category = "Technical",
                    title = "Preferred Tech Stack",
                    details = "Windows Desktop FastAPI backend, Flutter desktop client, Android companion with Jetpack Compose M3.",
                    confidenceScore = 0.98f,
                    dateAdded = "Aug 2026"
                )
            )
            dao.insertMemory(
                MemoryEntity(
                    category = "Projects",
                    title = "DASH Architecture Principle",
                    details = "One personal AI system with multiple interfaces. Android is the mobile control center, Windows is the primary host.",
                    confidenceScore = 0.99f,
                    dateAdded = "Aug 2026"
                )
            )
            dao.insertMemory(
                MemoryEntity(
                    category = "Preferences",
                    title = "Security & Approval Policy",
                    details = "Level 2 & 3 actions (file mutations, privileged system commands) must always ask for user confirmation.",
                    confidenceScore = 0.96f,
                    dateAdded = "Aug 2026"
                )
            )
            dao.insertMemory(
                MemoryEntity(
                    category = "Personal",
                    title = "Daily Focus",
                    details = "AWS architecture certification, DASH AI operating system refinement, and neural interface research.",
                    confidenceScore = 0.92f,
                    dateAdded = "Aug 2026"
                )
            )

            // Initial Projects
            dao.insertProject(
                ProjectEntity(
                    name = "DASH Personal AI OS",
                    description = "Unified personal AI operating system for Windows and Android companion.",
                    gitBranch = "main",
                    gitStatus = "Clean (3 unpushed commits)",
                    backendStatus = "FastAPI :8000 ● Online",
                    frontendStatus = "Compose M3 ● Active",
                    buildStatus = "Passing (CI #128)",
                    activeIssuesCount = 0,
                    recentActivity = "Implemented live 3D Orb shader and device pairing"
                )
            )
            dao.insertProject(
                ProjectEntity(
                    name = "Campus Connect",
                    description = "Distributed university peer network and collaborative workspace.",
                    gitBranch = "feature/chat-sync",
                    gitStatus = "1 modified file (uncommitted)",
                    backendStatus = "Go Fiber :3000 ● Online",
                    frontendStatus = "Flutter Mobile ● Idle",
                    buildStatus = "Passing (CI #89)",
                    activeIssuesCount = 2,
                    recentActivity = "Updated WebRTC signaling channel"
                )
            )
            dao.insertProject(
                ProjectEntity(
                    name = "Deepfake Detection",
                    description = "Multi-modal temporal video forensics using spatial-frequency embeddings.",
                    gitBranch = "model/vit-patch",
                    gitStatus = "Clean",
                    backendStatus = "PyTorch CUDA :5000 ● Idle",
                    frontendStatus = "Next.js Web ● Standby",
                    buildStatus = "Passing",
                    activeIssuesCount = 1,
                    recentActivity = "Trained epoch 45 on FaceForensics++"
                )
            )

            // Initial Tasks
            dao.insertTask(
                TaskItemEntity(
                    title = "Review PR #402 backend authentication patch",
                    category = "TODAY",
                    isCompleted = true,
                    priority = "HIGH",
                    dueDate = "Today, 11:00 AM"
                )
            )
            dao.insertTask(
                TaskItemEntity(
                    title = "Audit AWS S3 delta sync logs in CloudWatch",
                    category = "TODAY",
                    isCompleted = false,
                    priority = "HIGH",
                    dueDate = "Today, 2:00 PM"
                )
            )
            dao.insertTask(
                TaskItemEntity(
                    title = "Calibrate Ollama Qwen2.5-Coder context window",
                    category = "TODAY",
                    isCompleted = false,
                    priority = "MEDIUM",
                    dueDate = "Today, 4:30 PM"
                )
            )
            dao.insertTask(
                TaskItemEntity(
                    title = "Complete AWS Certified Solutions Architect review",
                    category = "UPCOMING",
                    isCompleted = false,
                    priority = "MEDIUM",
                    dueDate = "Tomorrow, 10:00 AM"
                )
            )

            // Initial Audit Logs
            dao.insertAuditLog(
                AuditLogEntity(
                    timeFormatted = "Just now",
                    event = "Coding Agent modified utils.js",
                    detail = "Optimized AST traversal node caching",
                    actor = "Coding Agent"
                )
            )
            dao.insertAuditLog(
                AuditLogEntity(
                    timeFormatted = "2 mins ago",
                    event = "Research Agent found 3 new sources",
                    detail = "Fetched Q3 LLM inference efficiency reports",
                    actor = "Research Agent"
                )
            )
            dao.insertAuditLog(
                AuditLogEntity(
                    timeFormatted = "15 mins ago",
                    event = "System Agent completed routine cleanup",
                    detail = "Freed 1.4 GB temporary build cache",
                    actor = "System Agent"
                )
            )
            dao.insertAuditLog(
                AuditLogEntity(
                    timeFormatted = "1 hour ago",
                    event = "Trusted device paired",
                    detail = "Android Companion handshake verified via ECDSA token",
                    actor = "Security Center"
                )
            )
        }
    }
}
