package com.example.data.repository

import android.content.Context
import android.util.Log
import com.example.data.api.DashApiService
import com.example.data.api.NotificationPrefsRequest
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow
import com.example.data.api.CreateMemoryRequest
import com.example.data.local.dao.DashDao
import com.example.data.local.entity.AgentEntity
import com.example.data.local.entity.ApprovalEntity
import com.example.data.local.entity.AuditLogEntity
import com.example.data.local.entity.ChatMessageEntity
import com.example.data.local.entity.NotificationEntity
import com.example.data.local.entity.MemoryEntity
import com.example.data.local.entity.ProjectEntity
import com.example.data.local.entity.TaskItemEntity
import com.example.data.model.AiProviderOption
import com.example.data.model.OrbState
import com.example.data.model.SystemMetrics
import com.example.data.config.AppConfig
import com.example.data.security.SecurityManager
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale

/**
 * DASH Repository — bridges Room (local cache) + DASH backend (REST/WebSocket).
 *
 * Chat messages flow through WebSocket streaming.
 * Memory, projects, notifications, approvals, and system state are fetched from REST.
 * Local Room DB serves as a cache and offline fallback.
 */
class DashRepository(
    private val context: Context,
    private val dao: DashDao
) {
    private companion object {
        const val TAG = "DashRepository"
    }

    private val scope = CoroutineScope(Dispatchers.IO)

    // --- Reactive state ---
    val chatMessages: Flow<List<ChatMessageEntity>> = dao.getAllMessages()
    val activeAgents: Flow<List<AgentEntity>> = dao.getAllAgents()
    val approvals: Flow<List<ApprovalEntity>> = dao.getAllApprovals()
    val memories: Flow<List<MemoryEntity>> = dao.getAllMemories()
    val projects: Flow<List<ProjectEntity>> = dao.getAllProjects()
    val tasks: Flow<List<TaskItemEntity>> = dao.getAllTasks()
    val auditLogs: Flow<List<AuditLogEntity>> = dao.getAllAuditLogs()
    val notifications: Flow<List<NotificationEntity>> = dao.getAllNotifications()
    val unreadNotificationCount: Flow<Int> = dao.getUnreadCount()

    private val _orbState = MutableStateFlow(OrbState.IDLE)
    val orbState: StateFlow<OrbState> = _orbState.asStateFlow()

        private val _notifPrefsProcess = MutableStateFlow(true)
    val notifPrefsProcess = _notifPrefsProcess.asStateFlow()
    private val _notifPrefsError = MutableStateFlow(true)
    val notifPrefsError = _notifPrefsError.asStateFlow()
    private val _notifPrefsSystem = MutableStateFlow(true)
    val notifPrefsSystem = _notifPrefsSystem.asStateFlow()

    private val _systemMetrics = MutableStateFlow(SystemMetrics())
    val systemMetrics: StateFlow<SystemMetrics> = _systemMetrics.asStateFlow()

    private val _selectedProvider = MutableStateFlow("ollama-qwen")
    val selectedProvider: StateFlow<String> = _selectedProvider.asStateFlow()

    private val _isVoiceListening = MutableStateFlow(false)
    val isVoiceListening: StateFlow<Boolean> = _isVoiceListening.asStateFlow()

    private val _voiceTranscript = MutableStateFlow("Tap the microphone to begin...")
    val voiceTranscript: StateFlow<String> = _voiceTranscript.asStateFlow()

    private val _isSafeModeActive = MutableStateFlow(false)
    val isSafeModeActive: StateFlow<Boolean> = _isSafeModeActive.asStateFlow()

    val isAuthenticated: Boolean get() = AppConfig.isAuthenticated

    // --- Streaming state from WebSocket ---
    val chatTokens: StateFlow<String> = WebSocketManager.chatTokens
    val chatDone: StateFlow<Boolean> = WebSocketManager.chatDone
    val toolConfirmation: StateFlow<WebSocketManager.ToolConfirmation?> = WebSocketManager.toolConfirmation
    val desktopNotification: StateFlow<WebSocketManager.DesktopNotification?> = WebSocketManager.desktopNotification

    val availableProviders = listOf(
        AiProviderOption("ollama-qwen", "Ollama Local (Qwen 2.5 Coder)", "LOCAL", "qwen2.5-coder:7b", true, "45ms", "Zero-latency local coding on Windows GPU"),
        AiProviderOption("ollama-llama", "Ollama Local (Llama 3.2)", "LOCAL", "llama3.2:3b", true, "28ms", "On-device memory and fast tool execution")
    )

    // --- Login ---
    suspend fun login(email: String, password: String): Boolean {
        return try {
            val response = DashApiService.login(email, password)
            AppConfig.accessToken = response.access_token
            AppConfig.refreshToken = response.refresh_token
            SecurityManager.saveAuthToken(context, response.access_token)
            WebSocketManager.connect()
            true
        } catch (e: Exception) {
            Log.e(TAG, "Login failed", e)
            false
        }
    }

    /** Reconnect using stored token. Auto-starts connection monitoring. */
    fun connectWithStoredToken() {
        com.example.data.connection.ConnectionStateManager.startMonitoring()
        if (AppConfig.isAuthenticated) {
            WebSocketManager.connect()
            scope.launch { refreshMetrics() }
        }
        // Bridge WebSocket systemState to systemMetrics for real-time updates
        scope.launch {
            WebSocketManager.systemState.collect { state ->
                if (state.desktopOnline) {
                    _systemMetrics.value = _systemMetrics.value.copy(
                        cpuUsage = state.cpuPercent.toInt(),
                        ramUsage = state.ramPercent.toInt(),
                        gpuUsage = state.gpuPercent.toInt(),
                        storageUsage = state.diskPercent.toInt(),
                        pcName = state.hostname.ifEmpty { _systemMetrics.value.pcName },
                        isPcOnline = true
                    )
                }
            }
        }
    }

    // --- Chat (WebSocket streaming) ---
    suspend fun sendMessage(userText: String, voiceMode: Boolean = false) {
        val time = currentTime()

        dao.insertMessage(
            ChatMessageEntity(
                sender = "USER",
                content = userText,
                timeFormatted = time
            )
        )

        _orbState.value = OrbState.THINKING
        WebSocketManager.resetStream()
        WebSocketManager.sendChatMessage(userText, voiceMode = voiceMode)

        val startTime = System.currentTimeMillis()
        var finalContent = ""

        while (System.currentTimeMillis() - startTime < 60_000) {
            val tokens = WebSocketManager.chatTokens.value
            if (tokens.isNotEmpty()) {
                finalContent = tokens
                _orbState.value = OrbState.EXECUTING
            }
            if (WebSocketManager.chatDone.value) {
                break
            }
            delay(100)
        }

        WebSocketManager.resetStream()

        if (finalContent.isNotEmpty()) {
            _orbState.value = OrbState.SPEAKING
            dao.insertMessage(
                ChatMessageEntity(
                    sender = "DASH",
                    content = finalContent,
                    timeFormatted = currentTime()
                )
            )
        } else {
            _orbState.value = OrbState.ERROR
            dao.insertMessage(
                ChatMessageEntity(
                    sender = "DASH",
                    content = "\u26a0 Could not reach DASH backend. Check that the desktop app is running.",
                    timeFormatted = currentTime()
                )
            )
        }

        delay(500)
        _orbState.value = OrbState.IDLE
    }

    // --- Voice ---
    fun startVoiceInteraction() {
        _isVoiceListening.value = true
        _orbState.value = OrbState.LISTENING
        _voiceTranscript.value = "Listening\u2026"
    }

    suspend fun stopVoiceInteraction(transcript: String? = null, voiceMode: Boolean = false) {
        _isVoiceListening.value = false
        val text = transcript ?: "Check system status"
        _voiceTranscript.value = text
        sendMessage(text)
    }

    // --- Memory (REST) ---
    suspend fun fetchAndCacheMemories() {
        try {
            val response = DashApiService.getMemories()
            response.memories.forEach { mem ->
                dao.insertMemory(
                    MemoryEntity(
                        category = mem.type,
                        title = mem.content.take(60),
                        details = mem.content,
                        confidenceScore = 1f,
                        dateAdded = mem.created_at
                    )
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch memories", e)
        }
    }

    suspend fun createMemory(category: String, title: String, details: String) {
        dao.insertMemory(
            MemoryEntity(category = category, title = title, details = details)
        )
        try {
            DashApiService.createMemory(CreateMemoryRequest(content = details, type = category))
        } catch (e: Exception) {
            Log.e(TAG, "Failed to create memory on backend", e)
        }
    }

    suspend fun deleteMemory(id: Long) {
        dao.deleteMemory(id)
    }

    // --- Projects (REST) ---
    suspend fun fetchAndCacheProjects() {
        try {
            val response = DashApiService.getProjects()
            response.projects.forEach { proj ->
                dao.insertProject(
                    ProjectEntity(
                        name = proj.name,
                        description = proj.description,
                        gitBranch = "main"
                    )
                )
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch projects", e)
        }
    }

    // --- Approvals ---
    suspend fun handleToolConfirmation(confirmation: WebSocketManager.ToolConfirmation) {
        dao.insertApproval(
            ApprovalEntity(
                title = confirmation.toolName,
                category = "TOOL EXECUTION",
                reason = confirmation.params.toString(),
                diffOrCommand = confirmation.toolName,
                status = "PENDING"
            )
        )
    }

    suspend fun approveRequest(id: Long, title: String) {
        dao.updateApprovalStatus(id, "APPROVED")
        dao.insertAuditLog(
            AuditLogEntity(
                timeFormatted = "Just now",
                event = "Approved '$title'",
                detail = "Authorization granted",
                actor = "User"
            )
        )
        _orbState.value = OrbState.SUCCESS
        delay(1000)
        _orbState.value = OrbState.IDLE
    }

    suspend fun rejectRequest(id: Long, title: String) {
        dao.updateApprovalStatus(id, "REJECTED")
        dao.insertAuditLog(
            AuditLogEntity(
                timeFormatted = "Just now",
                event = "Rejected '$title'",
                detail = "Operation blocked",
                actor = "User"
            )
        )
    }

    // --- Agents ---
    suspend fun toggleAgentStatus(agent: AgentEntity) {
        val newStatus = if (agent.status == "RUNNING") "PAUSED" else "RUNNING"
        dao.updateAgentStatus(agent.id, newStatus)
    }

    suspend fun createAgent(name: String, goal: String, instructions: String, tools: String, model: String) {
        dao.insertAgent(
            AgentEntity(
                name = name, goal = goal, currentTask = "Initializing\u2026",
                progressPercent = 0, status = "RUNNING", toolsUsed = tools, model = model
            )
        )
    }

    // --- Tasks ---
    suspend fun addTask(title: String, category: String, priority: String) {
        dao.insertTask(TaskItemEntity(title = title, category = category, priority = priority))
    }

    suspend fun toggleTask(task: TaskItemEntity) {
        dao.updateTaskStatus(task.id, !task.isCompleted)
    }

    suspend fun deleteTask(id: Long) {
        dao.deleteTask(id)
    }

    // --- System Metrics ---
    @Suppress("UNCHECKED_CAST")
    suspend fun refreshMetrics() {
        try {
            val overview = DashApiService.getStatusOverview()
            val details = overview.details
            val system = details["system"] as? Map<String, Any>
            val snapshot = system?.get("snapshot") as? Map<String, Any>

            val cpuPercent = (snapshot?.get("cpu_percent") as? Number)?.toInt() ?: 0
            val ramPercent = (snapshot?.get("memory_percent") as? Number)?.toInt() ?: 0
            val diskPercent = (snapshot?.get("disk_percent") as? Number)?.toInt() ?: 0
            val hostname = snapshot?.get("hostname") as? String ?: "Unknown"

            val gpuUsage = (snapshot?.get("gpu_usage") as? Number)?.toInt() ?: 0
            val gpuName = snapshot?.get("gpu_name") as? String ?: ""
            val ramTotal = (snapshot?.get("memory_total_gb") as? Number)?.toFloat() ?: 0f

            _systemMetrics.value = _systemMetrics.value.copy(
                pcName = hostname.ifEmpty { _systemMetrics.value.pcName },
                isPcOnline = true,
                cpuUsage = cpuPercent,
                ramUsage = ramPercent,
                storageUsage = diskPercent,
                gpuUsage = gpuUsage,
                gpuName = gpuName,
                ramTotalGb = ramTotal
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to fetch status overview", e)
            try {
                DashApiService.getHealth()
                _systemMetrics.value = _systemMetrics.value.copy(isPcOnline = true)
            } catch (_: Exception) {
                _systemMetrics.value = _systemMetrics.value.copy(isPcOnline = false)
            }
        }
    }

    // --- Desktop controls (REST) ---
    suspend fun getVolume(): Pair<Float, Boolean> = try {
        val r = DashApiService.getVolume()
        Pair(r.volume, r.muted)
    } catch (_: Exception) { Pair(0f, false) }

    suspend fun setVolume(level: Int) = try { DashApiService.setVolume(level) } catch (_: Exception) {}

    suspend fun getClipboard(): String = try {
        DashApiService.getClipboard().text
    } catch (_: Exception) { "" }

    suspend fun setClipboard(text: String) = try { DashApiService.setClipboard(text) } catch (_: Exception) {}

    // --- Desktop power controls (REST) ---
    suspend fun lockDesktop() = try { DashApiService.lock() } catch (_: Exception) {}
    suspend fun sleepDesktop() = try { DashApiService.sleep() } catch (_: Exception) {}
    suspend fun restartDesktop() = try { DashApiService.restart() } catch (_: Exception) {}
    suspend fun shutdownDesktop() = try { DashApiService.shutdown() } catch (_: Exception) {}

    // --- Window management (REST) ---
    suspend fun listWindows(): String = try {
        val r = DashApiService.listWindows()
        r.details.toString()
    } catch (_: Exception) { "[]" }

    suspend fun focusWindow(title: String) = try { DashApiService.focusWindow(title) } catch (_: Exception) {}
    suspend fun closeWindow(title: String) = try { DashApiService.closeWindow(title) } catch (_: Exception) {}
    suspend fun minimizeWindow(title: String) = try { DashApiService.minimizeWindow(title) } catch (_: Exception) {}
    suspend fun maximizeWindow(title: String) = try { DashApiService.maximizeWindow(title) } catch (_: Exception) {}

    // --- Files (REST) ---
    suspend fun browseFiles(path: String? = null) = try {
        DashApiService.browseFiles(path)
    } catch (e: Exception) {
        Log.e(TAG, "Failed to browse files", e)
        null
    }

    suspend fun searchFiles(query: String) = try {
        DashApiService.searchFiles(query)
    } catch (e: Exception) {
        Log.e(TAG, "Failed to search files", e)
        null
    }

    // --- Applications (REST) ---
    suspend fun searchApplications(query: String) = try {
        DashApiService.searchApplications(query)
    } catch (e: Exception) {
        Log.e(TAG, "Failed to search apps", e)
        emptyList()
    }

    suspend fun launchApplication(name: String) = try { DashApiService.launchApplication(name) } catch (_: Exception) {}
    suspend fun closeApplication(name: String) = try { DashApiService.closeApplication(name) } catch (_: Exception) {}

    // --- Connection testing ---
    @Suppress("UNCHECKED_CAST")
    suspend fun testConnection(host: String, port: String) {
        AppConfig.setServer(host, port)
        DashApiService.reset()
        try {
            val health = DashApiService.getHealth()
            _systemMetrics.value = _systemMetrics.value.copy(
                isPcOnline = health.status == "ok",
                pcName = (health.details["hostname"] as? String) ?: host
            )
        } catch (e: Exception) {
            Log.e(TAG, "Connection test failed", e)
            _systemMetrics.value = _systemMetrics.value.copy(isPcOnline = false)
        }
    }

    fun updateServer(host: String, port: String) {
        AppConfig.setServer(host, port)

        com.example.data.security.SecurityManager.saveServerConfig(context, host, port)

        DashApiService.reset()
    }

    // --- Safe Mode ---
    fun triggerSafeMode() {
        _isSafeModeActive.value = true
        _orbState.value = OrbState.APPROVAL_REQUIRED
    }

    fun disableSafeMode() {
        _isSafeModeActive.value = false
        _orbState.value = OrbState.IDLE
    }

    fun setOrbState(state: OrbState) { _orbState.value = state }
    fun setProvider(providerId: String) { _selectedProvider.value = providerId }

    private fun currentTime(): String =
        SimpleDateFormat("h:mm a", Locale.getDefault()).format(Date())

    // --- Notifications ---
    suspend fun storeNotification(title: String, body: String, appName: String = "") {
        try {
            dao.insertNotification(
                NotificationEntity(
                    title = title,
                    body = body,
                    appName = appName
                )
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to store notification: ${e.message}")
        }
    }

    suspend fun markNotificationRead(id: Long) {
        try {
            dao.markNotificationRead(id)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to mark notification read: ${e.message}")
        }
    }

    suspend fun markAllNotificationsRead() {
        try {
            dao.markAllNotificationsRead()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to mark all notifications read: ${e.message}")
        }
    }

    suspend fun deleteNotification(id: Long) {
        try {
            dao.deleteNotification(id)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to delete notification: ${e.message}")
        }
    }

    suspend fun clearAllNotifications() {
        try {
            dao.clearAllNotifications()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to clear notifications: ${e.message}")
        }
    }

    // --- Notification Preferences ---
    suspend fun loadNotificationPrefs() {
        try {
            val prefs = DashApiService.getNotificationPrefs()
            _notifPrefsProcess.value = prefs.process
            _notifPrefsError.value = prefs.error
            _notifPrefsSystem.value = prefs.system
        } catch (e: Exception) {
            Log.e(TAG, "Failed to load notification prefs: ${e.message}")
        }
    }

    suspend fun toggleNotifCategory(category: String, enabled: Boolean) {
        try {
            val request = when (category) {
                "process" -> NotificationPrefsRequest(process = enabled)
                "error" -> NotificationPrefsRequest(error = enabled)
                "system" -> NotificationPrefsRequest(system = enabled)
                else -> return
            }
            val result = DashApiService.updateNotificationPrefs(request)
            _notifPrefsProcess.value = result.process
            _notifPrefsError.value = result.error
            _notifPrefsSystem.value = result.system
        } catch (e: Exception) {
            Log.e(TAG, "Failed to update notification prefs: ${e.message}")
        }
    }

}