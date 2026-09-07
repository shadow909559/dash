package com.example.ui.viewmodel

import android.app.Application
import androidx.lifecycle.AndroidViewModel
import androidx.lifecycle.viewModelScope
import com.example.data.local.DashDatabase
import com.example.data.local.entity.AgentEntity
import com.example.data.local.entity.ApprovalEntity
import com.example.data.local.entity.AuditLogEntity
import com.example.data.local.entity.ChatMessageEntity
import com.example.data.local.entity.MemoryEntity
import com.example.data.local.entity.NotificationEntity
import com.example.data.local.entity.ProjectEntity
import com.example.data.local.entity.TaskItemEntity
import com.example.data.model.AiProviderOption
import com.example.data.model.OrbState
import com.example.data.model.SystemMetrics
import com.example.data.repository.DashRepository
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.flow.SharingStarted
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.stateIn
import kotlinx.coroutines.launch

class DashViewModel(application: Application) : AndroidViewModel(application) {

    private val repository: DashRepository

    val orbState: StateFlow<OrbState>
    val systemMetrics: StateFlow<SystemMetrics>
    val selectedProvider: StateFlow<String>
    val isVoiceListening: StateFlow<Boolean>
    val voiceTranscript: StateFlow<String>
    val isSafeModeActive: StateFlow<Boolean>
    val connectionState: StateFlow<WebSocketManager.ConnectionState>

    val chatMessages: StateFlow<List<ChatMessageEntity>>
    val chatTokens: StateFlow<String>
    val chatDone: StateFlow<Boolean>
    val activeAgents: StateFlow<List<AgentEntity>>
    val approvals: StateFlow<List<ApprovalEntity>>
    val memories: StateFlow<List<MemoryEntity>>
    val projects: StateFlow<List<ProjectEntity>>
    val tasks: StateFlow<List<TaskItemEntity>>
    val auditLogs: StateFlow<List<AuditLogEntity>>
    val notifications: StateFlow<List<NotificationEntity>>
    val unreadNotificationCount: StateFlow<Int>

    val availableProviders: List<AiProviderOption>

    init {
        val database = DashDatabase.getDatabase(application, viewModelScope)
        repository = DashRepository(application, database.dashDao())

        orbState = repository.orbState
        systemMetrics = repository.systemMetrics
        selectedProvider = repository.selectedProvider
        isVoiceListening = repository.isVoiceListening
        voiceTranscript = repository.voiceTranscript
        isSafeModeActive = repository.isSafeModeActive
        connectionState = WebSocketManager.connectionState
        availableProviders = repository.availableProviders

        chatMessages = repository.chatMessages.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        chatTokens = WebSocketManager.chatTokens
        chatDone = WebSocketManager.chatDone
        activeAgents = repository.activeAgents.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        approvals = repository.approvals.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        memories = repository.memories.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        projects = repository.projects.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        tasks = repository.tasks.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        auditLogs = repository.auditLogs.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        notifications = repository.notifications.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            emptyList()
        )
        unreadNotificationCount = repository.unreadNotificationCount.stateIn(
            viewModelScope,
            SharingStarted.WhileSubscribed(5000),
            0
        )

        // Connect to backend on startup
        repository.connectWithStoredToken()
    }

    fun sendMessage(text: String, voiceMode: Boolean = false) {
        if (text.isBlank()) return
        viewModelScope.launch {
            repository.sendMessage(text, voiceMode)
        }
    }

    fun setOrbState(state: OrbState) {
        repository.setOrbState(state)
    }

    fun setProvider(providerId: String) {
        repository.setProvider(providerId)
    }

    fun startVoiceInteraction() {
        viewModelScope.launch {
            repository.startVoiceInteraction()
        }
    }

    fun stopVoiceInteraction(speech: String? = null, voiceMode: Boolean = false) {
        viewModelScope.launch {
            repository.stopVoiceInteraction(speech, voiceMode)
        }
    }

    fun approveRequest(id: Long, title: String) {
        viewModelScope.launch {
            repository.approveRequest(id, title)
        }
    }

    fun rejectRequest(id: Long, title: String) {
        viewModelScope.launch {
            repository.rejectRequest(id, title)
        }
    }

    fun toggleAgent(agent: AgentEntity) {
        viewModelScope.launch {
            repository.toggleAgentStatus(agent)
        }
    }

    fun createAgent(name: String, goal: String, instructions: String, tools: String, model: String) {
        viewModelScope.launch {
            repository.createAgent(name, goal, instructions, tools, model)
        }
    }

    fun addMemory(category: String, title: String, details: String) {
        viewModelScope.launch {
            repository.createMemory(category, title, details)
        }
    }

    fun deleteMemory(id: Long) {
        viewModelScope.launch {
            repository.deleteMemory(id)
        }
    }

    fun addTask(title: String, category: String, priority: String) {
        viewModelScope.launch {
            repository.addTask(title, category, priority)
        }
    }

    fun toggleTask(task: TaskItemEntity) {
        viewModelScope.launch {
            repository.toggleTask(task)
        }
    }

    fun deleteTask(id: Long) {
        viewModelScope.launch {
            repository.deleteTask(id)
        }
    }

    fun triggerSafeMode() {
        viewModelScope.launch {
            repository.triggerSafeMode()
        }
    }

    fun disableSafeMode() {
        viewModelScope.launch {
            repository.disableSafeMode()
        }
    }

    fun refreshMetrics() {
        viewModelScope.launch {
            repository.refreshMetrics()
        }
    }

    fun testConnection(host: String, port: String) {
        viewModelScope.launch {
            repository.testConnection(host, port)
        }
    }

    fun updateServer(host: String, port: String) {
        repository.updateServer(host, port)
    }

    fun connect() {
        repository.connectWithStoredToken()
    }

    fun login(email: String, password: String) {
        viewModelScope.launch {
            repository.login(email, password)
        }
    }

    // --- Window Management ---
    fun closeWindow(title: String) {
        viewModelScope.launch { repository.closeWindow(title) }
    }

    fun minimizeWindow(title: String) {
        viewModelScope.launch { repository.minimizeWindow(title) }
    }

    fun maximizeWindow(title: String) {
        viewModelScope.launch { repository.maximizeWindow(title) }
    }

    fun focusWindow(title: String) {
        viewModelScope.launch { repository.focusWindow(title) }
    }

    // --- Application Management ---
    fun launchApplication(name: String) {
        viewModelScope.launch { repository.launchApplication(name) }
    }

    fun closeApplication(name: String) {
        viewModelScope.launch { repository.closeApplication(name) }
    }

    // --- Power Controls ---
    fun shutdownDesktop() {
        viewModelScope.launch { repository.shutdownDesktop() }
    }

    // --- Notifications ---
    fun markNotificationRead(id: Long) {
        viewModelScope.launch { repository.markNotificationRead(id) }
    }

    fun markAllNotificationsRead() {
        viewModelScope.launch { repository.markAllNotificationsRead() }
    }

    fun deleteNotification(id: Long) {
        viewModelScope.launch { repository.deleteNotification(id) }
    }

    fun clearAllNotifications() {
        viewModelScope.launch { repository.clearAllNotifications() }
    }

    // --- Notification Preferences ---
    val notifPrefsProcess = repository.notifPrefsProcess
    val notifPrefsError = repository.notifPrefsError
    val notifPrefsSystem = repository.notifPrefsSystem

    fun loadNotificationPrefs() {
        viewModelScope.launch { repository.loadNotificationPrefs() }
    }
    fun toggleNotifCategory(category: String, enabled: Boolean) {
        viewModelScope.launch { repository.toggleNotifCategory(category, enabled) }
    }

}