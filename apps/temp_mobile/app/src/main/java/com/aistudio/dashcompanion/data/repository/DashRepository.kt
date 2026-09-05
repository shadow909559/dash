package com.aistudio.dashcompanion.data.repository

import com.aistudio.dashcompanion.data.api.*
import com.aistudio.dashcompanion.data.config.AppConfig
import com.aistudio.dashcompanion.data.datastore.SettingsDataStore
import com.aistudio.dashcompanion.data.model.*
import com.aistudio.dashcompanion.data.websocket.SystemWebSocketManager
import com.aistudio.dashcompanion.data.websocket.WebSocketManager
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.*
import okhttp3.MediaType.Companion.toMediaType
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.asRequestBody

object DashRepository {
    private lateinit var settingsDataStore: SettingsDataStore
    private val webSocketManager = WebSocketManager
    private val apiService = DashApiService
    private val scope = CoroutineScope(Dispatchers.Main)
    
    fun init(context: android.content.Context) {
        settingsDataStore = SettingsDataStore(context)
        webSocketManager.setContext(context)
        
        // Observe and update AppConfig dynamically
        settingsDataStore.serverIp.onEach { AppConfig.SERVER_IP = it }.launchIn(scope)
        settingsDataStore.serverPort.onEach { AppConfig.SERVER_PORT = it }.launchIn(scope)
        settingsDataStore.accessToken.onEach { 
            AppConfig.accessToken = if (it == "placeholder_token") null else it 
        }.launchIn(scope)
    }
    
    private fun ensureInitialized() {
        if (!::settingsDataStore.isInitialized) {
            throw IllegalStateException("DashRepository must be initialized with init(context) before use")
        }
    }

    suspend fun login(email: String, password: String): Result<AuthResponse> {
        ensureInitialized()
        return try {
            val response = apiService.login(email, password)
            settingsDataStore.setAccessToken(response.access_token)
            settingsDataStore.setRefreshToken(response.refresh_token)
            settingsDataStore.setLoggedIn(true)
            AppConfig.accessToken = response.access_token
            AppConfig.refreshToken = response.refresh_token
            Result.success(response)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun logout() {
        ensureInitialized()
        settingsDataStore.setAccessToken(null)
        settingsDataStore.setRefreshToken(null)
        settingsDataStore.setLoggedIn(false)
        AppConfig.accessToken = null
        AppConfig.refreshToken = null
        // Ensure proper disconnection
        try {
            webSocketManager.disconnect()
            SystemWebSocketManager.disconnect()
        } catch (e: Exception) {
            android.util.Log.e("DashRepository", "Error during logout disconnect", e)
        }
    }

    suspend fun connectWebSocket() {
        ensureInitialized()
        val token = settingsDataStore.accessToken.first()
        android.util.Log.d("DashRepository", "Connecting WebSocket with token: ${if (token != null) "present" else "null"}")
        AppConfig.accessToken = token
        webSocketManager.setCredentials(token)
        
        // Connect main WebSocket
        webSocketManager.connect()
        
        // Connect system WebSocket separately for system monitoring
        // This ensures chat and system monitoring use different connections
        try {
            SystemWebSocketManager.connect()
        } catch (e: Exception) {
            android.util.Log.e("DashRepository", "Failed to connect system WebSocket", e)
            // Don't fail the whole connection if system WS fails
        }
    }

    suspend fun getHealth(): Result<StatusResponse> {
        return try {
            android.util.Log.d("DashRepository", "Requesting health status from ${AppConfig.REST_BASE_URL}health")
            val response = apiService.getHealth()
            Result.success(response)
        } catch (e: Exception) {
            android.util.Log.e("DashRepository", "Health check failed", e)
            Result.failure(e)
        }
    }

    fun disconnectWebSocket() {
        try {
            webSocketManager.disconnect()
            SystemWebSocketManager.disconnect()
        } catch (e: Exception) {
            android.util.Log.e("DashRepository", "Error during WebSocket disconnect", e)
        }
    }

    fun getConnectionState() = webSocketManager.connectionState
    fun getSystemState() = webSocketManager.systemState
    fun getChatMessages() = webSocketManager.chatMessages
    fun getCurrentResponse() = webSocketManager.currentResponse

    fun sendChatMessage(content: String, conversationId: String? = null) {
        webSocketManager.sendChatMessage(content, conversationId)
    }

    suspend fun getConversations(): Result<List<Conversation>> {
        return try { Result.success(apiService.getConversations()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun browseFiles(path: String, showHidden: Boolean = false): Result<BrowseResponse> {
        return try { Result.success(apiService.browseFiles(path, showHidden)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun searchFiles(pattern: String, path: String, maxResults: Int = 50): Result<FileSearchResponse> {
        return try { Result.success(apiService.searchFiles(pattern, path, maxResults)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun copyFile(source: String, destination: String): Result<FileOperationResponse> {
        return try { Result.success(apiService.copyFile(source, destination)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun moveFile(source: String, destination: String): Result<FileOperationResponse> {
        return try { Result.success(apiService.moveFile(source, destination)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun renameFile(path: String, newName: String): Result<FileOperationResponse> {
        return try { Result.success(apiService.renameFile(path, newName)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun deleteFile(path: String, permanent: Boolean = false): Result<FileOperationResponse> {
        return try { Result.success(apiService.deleteFile(path, permanent)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun getVolume(): Result<VolumeResponse> {
        return try { Result.success(apiService.getVolume()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun setVolume(level: Int): Result<VolumeResponse> {
        return try { Result.success(apiService.setVolume(level)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun getBrightness(): Result<BrightnessResponse> {
        return try { Result.success(apiService.getBrightness()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun setBrightness(level: Int): Result<BrightnessResponse> {
        return try { Result.success(apiService.setBrightness(level)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun getClipboard(): Result<ClipboardResponse> {
        return try { Result.success(apiService.getClipboard()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun setClipboard(text: String): Result<ClipboardResponse> {
        return try { Result.success(apiService.setClipboard(text)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mouseMove(x: Int, y: Int): Result<StatusResponse> {
        return try { Result.success(apiService.mouseMove(x, y)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mouseClick(button: String = "left", x: Int? = null, y: Int? = null): Result<StatusResponse> {
        return try { Result.success(apiService.mouseClick(button, x, y)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mouseDoubleClick(): Result<StatusResponse> {
        return try { Result.success(apiService.mouseDoubleClick()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mouseScroll(clicks: Int = 1): Result<StatusResponse> {
        return try { Result.success(apiService.mouseScroll(clicks)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mousePosition(): Result<StatusResponse> {
        return try { Result.success(apiService.mousePosition()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun keyboardType(text: String): Result<StatusResponse> {
        return try { Result.success(apiService.keyboardType(text)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun keyboardPress(key: String): Result<StatusResponse> {
        return try { Result.success(apiService.keyboardPress(key)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun keyboardHotkey(keys: List<String>): Result<StatusResponse> {
        return try { Result.success(apiService.keyboardHotkey(keys)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun takeScreenshot(): Result<StatusResponse> {
        return try { Result.success(apiService.takeScreenshot()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun shutdown(force: Boolean = false): Result<PowerResponse> {
        return try { Result.success(apiService.shutdown(force)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun restart(force: Boolean = false): Result<PowerResponse> {
        return try { Result.success(apiService.restart(force)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun lock(): Result<PowerResponse> {
        return try { Result.success(apiService.lock()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun sleep(): Result<PowerResponse> {
        return try { Result.success(apiService.sleep()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun hibernate(): Result<PowerResponse> {
        return try { Result.success(apiService.hibernate()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun logoff(force: Boolean = false): Result<PowerResponse> {
        return try { Result.success(apiService.logoff(force)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun setMute(muted: Boolean = true): Result<VolumeResponse> {
        return try { Result.success(apiService.setMute(muted)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun clipboardClear(): Result<PowerResponse> {
        return try { Result.success(apiService.clipboardClear()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun previewFile(path: String, maxLines: Int = 50): Result<String> {
        return try {
            val result = apiService.previewFile(path, maxLines)
            Result.success(result.content)
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    suspend fun listWindows(): Result<StatusResponse> {
        return try { Result.success(apiService.listWindows()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun focusWindow(title: String): Result<StatusResponse> {
        return try { Result.success(apiService.focusWindow(title)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun closeWindow(title: String): Result<StatusResponse> {
        return try { Result.success(apiService.closeWindow(title)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun minimizeWindow(title: String): Result<StatusResponse> {
        return try { Result.success(apiService.minimizeWindow(title)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun maximizeWindow(title: String): Result<StatusResponse> {
        return try { Result.success(apiService.maximizeWindow(title)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun getActiveWindow(): Result<StatusResponse> {
        return try { Result.success(apiService.getActiveWindow()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun showDesktopNotification(title: String, message: String, duration: Int = 5): Result<PowerResponse> {
        return try { Result.success(apiService.showDesktopNotification(title, message, duration)) } catch (e: Exception) { Result.failure(e) }
    }

    // --- NEW: Screenshot ---
    suspend fun getScreenshot(): Result<ScreenshotResponse> {
        return try { Result.success(apiService.getScreenshot()) } catch (e: Exception) { Result.failure(e) }
    }

    // --- AUTOMATION ---
    suspend fun getAutomationRules(): Result<AutomationRulesResponse> {
        return try { Result.success(apiService.getAutomationRules()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun createAutomationRule(request: AutomationRuleRequest): Result<AutomationRuleResponse> {
        return try { Result.success(apiService.createAutomationRule(request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun updateAutomationRule(id: String, request: AutomationRuleUpdateRequest): Result<AutomationRuleResponse> {
        return try { Result.success(apiService.updateAutomationRule(id, request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun deleteAutomationRule(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.deleteAutomationRule(id)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun enableAutomationRule(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.enableAutomationRule(id)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun disableAutomationRule(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.disableAutomationRule(id)) } catch (e: Exception) { Result.failure(e) }
    }

    // --- NOTIFICATIONS ---
    suspend fun getNotifications(): Result<NotificationsResponse> {
        return try { Result.success(apiService.getNotifications()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun markNotificationsRead(request: NotificationsReadRequest): Result<PowerResponse> {
        return try { Result.success(apiService.markNotificationsRead(request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun clearNotifications(): Result<PowerResponse> {
        return try { Result.success(apiService.clearNotifications()) } catch (e: Exception) { Result.failure(e) }
    }

    // --- MEMORIES ---
    suspend fun getMemories(search: String? = null, type: String? = null): Result<MemoriesResponse> {
        return try { Result.success(apiService.getMemories(search, type)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun createMemory(request: CreateMemoryRequest): Result<MemoryResponse> {
        return try { Result.success(apiService.createMemory(request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun deleteMemory(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.deleteMemory(id)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun pinMemory(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.pinMemory(id)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun unpinMemory(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.unpinMemory(id)) } catch (e: Exception) { Result.failure(e) }
    }

    // --- PROJECTS ---
    suspend fun getProjects(search: String? = null): Result<ProjectsResponse> {
        return try { Result.success(apiService.getProjects(search)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun createProject(request: CreateProjectRequest): Result<ProjectResponse> {
        return try { Result.success(apiService.createProject(request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun updateProject(id: String, request: UpdateProjectRequest): Result<ProjectResponse> {
        return try { Result.success(apiService.updateProject(id, request)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun deleteProject(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.deleteProject(id)) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun syncProject(id: String): Result<PowerResponse> {
        return try { Result.success(apiService.syncProject(id)) } catch (e: Exception) { Result.failure(e) }
    }

    // --- MEDIA ---
    suspend fun getMediaStatus(): Result<MediaStatusResponse> {
        return try { Result.success(apiService.getMediaStatus()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mediaPlay(): Result<PowerResponse> {
        return try { Result.success(apiService.mediaPlay()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mediaPause(): Result<PowerResponse> {
        return try { Result.success(apiService.mediaPause()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mediaNext(): Result<PowerResponse> {
        return try { Result.success(apiService.mediaNext()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mediaPrevious(): Result<PowerResponse> {
        return try { Result.success(apiService.mediaPrevious()) } catch (e: Exception) { Result.failure(e) }
    }

    suspend fun mediaStop(): Result<PowerResponse> {
        return try { Result.success(apiService.mediaStop()) } catch (e: Exception) { Result.failure(e) }
    }

    // --- DASHBOARD STATS ---
    suspend fun getDashboardStats(): Result<DashboardStatsResponse> {
        return try { Result.success(apiService.getDashboardStats()) } catch (e: Exception) { Result.failure(e) }
    }

    fun serverIp(): Flow<String> { ensureInitialized(); return settingsDataStore.serverIp }
    fun serverPort(): Flow<String> { ensureInitialized(); return settingsDataStore.serverPort }
    fun isLoggedIn(): Flow<Boolean> { ensureInitialized(); return settingsDataStore.isLoggedIn }
    fun darkTheme(): Flow<Boolean> { ensureInitialized(); return settingsDataStore.darkTheme }
    fun autoReconnect(): Flow<Boolean> { ensureInitialized(); return settingsDataStore.autoReconnect }
    fun voiceEnabled(): Flow<Boolean> { ensureInitialized(); return settingsDataStore.voiceEnabled }
    fun notificationsEnabled(): Flow<Boolean> { ensureInitialized(); return settingsDataStore.notificationsEnabled }

    /**
     * Check if there is a valid stored JWT session.
     * Returns true if the user has logged in before and has a stored access token.
     */
    suspend fun hasValidSession(): Boolean {
        ensureInitialized()
        val token = settingsDataStore.accessToken.first()
        val loggedIn = settingsDataStore.isLoggedIn.first()
        return loggedIn && !token.isNullOrEmpty() && token != "placeholder_token"
    }

    /**
     * Get the stored access token directly.
     */
    suspend fun getAccessToken(): String? {
        ensureInitialized()
        val token = settingsDataStore.accessToken.first()
        return if (!token.isNullOrEmpty() && token != "placeholder_token") token else null
    }

    suspend fun setServerIp(ip: String) { ensureInitialized(); settingsDataStore.setServerIp(ip) }
    suspend fun setServerPort(port: String) { ensureInitialized(); settingsDataStore.setServerPort(port) }
    suspend fun setDarkTheme(enabled: Boolean) { ensureInitialized(); settingsDataStore.setDarkTheme(enabled) }
    suspend fun setAutoReconnect(enabled: Boolean) { ensureInitialized(); settingsDataStore.setAutoReconnect(enabled) }
    suspend fun setVoiceEnabled(enabled: Boolean) { ensureInitialized(); settingsDataStore.setVoiceEnabled(enabled) }
    suspend fun setNotificationsEnabled(enabled: Boolean) { ensureInitialized(); settingsDataStore.setNotificationsEnabled(enabled) }

    // --- IMAGE UPLOAD & ANALYSIS ---
    suspend fun uploadImage(file: java.io.File, analyze: Boolean = true, ocr: Boolean = true): Result<ImageAnalysisResult> {
        return withContext(Dispatchers.IO) {
            try {
                val requestBody = MultipartBody.Builder()
                    .setType(MultipartBody.FORM)
                    .addFormDataPart("file", file.name, file.asRequestBody("image/*".toMediaType()))
                    .build()

                val response = apiService.uploadImage(requestBody, analyze, ocr)
                Result.success(response.analysis ?: ImageAnalysisResult(summary = "Upload successful, but no analysis result."))
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    suspend fun analyzeImageBase64(imageBase64: String): Result<ImageAnalysisResult> {
        return withContext(Dispatchers.IO) {
            try {
                val response = apiService.analyzeImage(imageBase64)
                Result.success(response)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    // --- FILE TRANSFER ---
    suspend fun transferFileToPhone(path: String): Result<FileTransferResult> {
        return withContext(Dispatchers.IO) {
            try {
                val response = apiService.downloadFile(FileDownloadRequest(path))
                Result.success(response)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    suspend fun transferFileToPc(filename: String, dataBase64: String, destination: String = "downloads"): Result<FileTransferResult> {
        return withContext(Dispatchers.IO) {
            try {
                val request = FileUploadRequest(filename, dataBase64, destination)
                val response = apiService.uploadFileToPc(request)
                Result.success(response)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }

    suspend fun getTransferDestinations(): Result<Map<String, String>> {
        return withContext(Dispatchers.IO) {
            try {
                val response = apiService.getTransferDestinations()
                Result.success(response)
            } catch (e: Exception) {
                Result.failure(e)
            }
        }
    }
}
