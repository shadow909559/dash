package com.aistudio.dashcompanion.data.websocket

import android.content.Context
import android.content.Intent
import android.net.Uri
import android.util.Log
import com.aistudio.dashcompanion.DashApplication
import com.aistudio.dashcompanion.data.config.AppConfig
import com.aistudio.dashcompanion.data.model.ChatMessage
import com.aistudio.dashcompanion.data.model.ChatResponse
import com.aistudio.dashcompanion.data.model.SystemState
import com.aistudio.dashcompanion.data.provider.PhoneDataProvider
import com.aistudio.dashcompanion.services.AudioPlayerManager
import com.aistudio.dashcompanion.services.DesktopEventMonitor
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlin.math.pow
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI as JavaURI
import java.util.UUID

object WebSocketManager {
    private const val TAG = "WebSocketManager"
    private val coroutineScope = CoroutineScope(Dispatchers.IO)

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    private val chatResponseAdapter = moshi.adapter(ChatResponse::class.java)
    private val systemStateAdapter = moshi.adapter(SystemState::class.java)

    private var webSocketClient: WebSocketClient? = null
    private var isConnected = false
    private var isAuthenticated = false
    private var heartbeatJob: Job? = null
    private var phoneStateBroadcastJob: Job? = null
    private var phoneDataProvider: PhoneDataProvider? = null
    
    // Reconnection management
    private var reconnectJob: Job? = null
    private var reconnectAttempts = 0
    private var isIntentionalDisconnect = false
    private var connectionLock = java.util.concurrent.locks.ReentrantLock()

    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    private val _systemState = MutableStateFlow<SystemState?>(null)
    val systemState: StateFlow<SystemState?> = _systemState.asStateFlow()

    private val _chatMessages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val chatMessages: StateFlow<List<ChatMessage>> = _chatMessages.asStateFlow()

    private val _currentResponse = MutableStateFlow<String>("")
    val currentResponse: StateFlow<String> = _currentResponse.asStateFlow()

    private val _isTtsSpeaking = MutableStateFlow(false)
    val isTtsSpeaking: StateFlow<Boolean> = _isTtsSpeaking.asStateFlow()

    fun setCredentials(token: String?) {
        AppConfig.accessToken = token
    }

    fun setContext(context: Context) {
        this.phoneDataProvider = PhoneDataProvider(context)
    }

    fun connect() {
        connectionLock.lock()
        try {
            if (isConnected) {
                Log.d(TAG, "Already connected to ${AppConfig.WEBSOCKET_URL}")
                return
            }
            
            // Cancel any existing reconnection attempts
            reconnectJob?.cancel()
            reconnectAttempts = 0
            isIntentionalDisconnect = false

            // Validate that we have a token before attempting connection
            val token = AppConfig.accessToken
            if (token.isNullOrEmpty() || token == "placeholder_token") {
                Log.e(TAG, "No valid JWT token available. Cannot connect WebSocket.")
                _connectionState.value = ConnectionState.Error("Authentication required")
                return
            }

            Log.d(TAG, "Attempting to connect to WebSocket: ${AppConfig.WEBSOCKET_URL}")
            try {
                webSocketClient = object : WebSocketClient(JavaURI(AppConfig.WEBSOCKET_URL)) {
                override fun onOpen(handshake: ServerHandshake?) {
                    Log.d(TAG, "WebSocket opened successfully")
                    isConnected = true
                    _connectionState.value = ConnectionState.Connected
                    authenticate()
                    startHeartbeat()
                    startPhoneStateBroadcast()
                }
                override fun onMessage(message: String?) { 
                    Log.v(TAG, "Received message: $message")
                    message?.let { handleMessage(it) } 
                }
                override fun onClose(code: Int, reason: String?, remote: Boolean) {
                    val disconnectReason = "WebSocket closed - Code: $code, Reason: $reason, Remote: $remote, Intentional: $isIntentionalDisconnect"
                    Log.w(TAG, disconnectReason)
                    
                    isConnected = false
                    isAuthenticated = false
                    stopHeartbeat()
                    stopPhoneStateBroadcast()
                    
                    // If closed due to auth failure, report as auth failure instead of generic disconnect
                    if (code == 4001 || reason?.contains("token", ignoreCase = true) == true ||
                        reason?.contains("auth", ignoreCase = true) == true ||
                        reason?.contains("InvalidTokenError", ignoreCase = true) == true) {
                        Log.e(TAG, "Auth failure disconnect: $reason")
                        _connectionState.value = ConnectionState.AuthFailed(reason ?: "Invalid token")
                        // Don't reconnect on auth failures
                        return
                    }
                    
                    _connectionState.value = ConnectionState.Disconnected
                    
                    // Only attempt reconnection if this wasn't intentional and conditions are met
                    if (!isIntentionalDisconnect && remote && code != 1000) {
                        // Don't reconnect if it's rate limiting or server indicates no retry
                        if (reason?.contains("rate limit", ignoreCase = true) == false &&
                            reason?.contains("no retry", ignoreCase = true) == false) {
                            scheduleReconnect()
                        } else {
                            Log.w(TAG, "Not reconnecting due to server indication: $reason")
                        }
                    } else {
                        Log.d(TAG, "Not reconnecting - Intentional: $isIntentionalDisconnect, Remote: $remote, Code: $code")
                    }
                }
                override fun onError(ex: Exception?) {
                    Log.e(TAG, "WebSocket error: ${ex?.message}", ex)
                    _connectionState.value = ConnectionState.Error(ex?.message ?: "Unknown error")
                    stopHeartbeat(); stopPhoneStateBroadcast()
                }
            }
            Log.d(TAG, "Calling webSocketClient.connect()")
            webSocketClient?.connect()
        } catch (e: Exception) {
            Log.e(TAG, "WebSocket connection setup failed", e)
            _connectionState.value = ConnectionState.Error(e.message ?: "Connection failed")
        }
        } finally {
            connectionLock.unlock()
        }
    }

    fun disconnect() {
        connectionLock.lock()
        try {
            isIntentionalDisconnect = true
            reconnectJob?.cancel()
            reconnectAttempts = 0
            
            webSocketClient?.close()
            webSocketClient = null
            isConnected = false
            isAuthenticated = false
            stopHeartbeat()
            stopPhoneStateBroadcast()
            _connectionState.value = ConnectionState.Disconnected
            
            Log.d(TAG, "Intentional disconnect completed")
        } finally {
            connectionLock.unlock()
        }
    }

    private fun startPhoneStateBroadcast() {
        stopPhoneStateBroadcast()
        phoneStateBroadcastJob = coroutineScope.launch {
            while (isConnected) { delay(3000); if (isConnected && isAuthenticated) sendPhoneState() }
        }
    }

    private fun stopPhoneStateBroadcast() { phoneStateBroadcastJob?.cancel(); phoneStateBroadcastJob = null }

    private fun sendPhoneState() {
        try {
            phoneDataProvider?.updatePhoneData()
            val state = phoneDataProvider?.phoneState?.value ?: return
            val apps = phoneDataProvider?.getInstalledApps() ?: emptyList()
            val notifications = phoneDataProvider?.getActiveNotifications() ?: emptyList()
            send(mapOf(
                "type" to "phone.state",
                "battery" to mapOf("level" to state.battery.level, "is_charging" to state.battery.isCharging,
                    "health" to state.battery.health, "temperature" to state.battery.temperature,
                    "voltage" to state.battery.voltage, "technology" to state.battery.technology),
                "storage" to mapOf("total_bytes" to state.storage.totalBytes, "used_bytes" to state.storage.usedBytes,
                    "free_bytes" to state.storage.freeBytes, "used_percent" to state.storage.usedPercent),
                "network" to mapOf("is_connected" to state.network.isConnected, "type" to state.network.type,
                    "ssid" to state.network.ssid, "is_metered" to state.network.isMetered,
                    "signal_strength" to state.network.signalStrength),
                "clipboard" to state.clipboard,
                "volume" to mapOf("volume" to state.volume.volume, "is_muted" to state.volume.isMuted, "max_volume" to state.volume.maxVolume),
                "flashlight" to state.flashlight, "notifications_enabled" to state.notificationsEnabled,
                "media" to mapOf("is_playing" to state.activeMedia.isPlaying, "title" to state.activeMedia.title,
                    "artist" to state.activeMedia.artist, "album" to state.activeMedia.album,
                    "duration" to state.activeMedia.duration, "position" to state.activeMedia.position,
                    "package_name" to state.activeMedia.packageName),
                "installed_apps_count" to apps.size, "notifications_count" to notifications.size,
                "timestamp" to state.timestamp
            ))
        } catch (e: Exception) { Log.e(TAG, "Failed to send phone state", e) }
    }

    private fun startHeartbeat() {
        stopHeartbeat()
        heartbeatJob = coroutineScope.launch {
            var missedPongs = 0
            while (isConnected) {
                delay(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS)
                if (isConnected) {
                    sendHeartbeat()
                    // Increment missed pongs counter - will be reset when pong is received
                    missedPongs++
                    if (missedPongs > 3) {
                        Log.e(TAG, "Too many missed pongs (${missedPongs}), forcing reconnection")
                        forceReconnect("Heartbeat timeout")
                        break
                    }
                }
            }
        }
    }

    private fun stopHeartbeat() { heartbeatJob?.cancel(); heartbeatJob = null }

    private fun sendHeartbeat() { try { send(mapOf("type" to "ping")) } catch (e: Exception) { } }

    private fun authenticate() { 
        val clientId = UUID.randomUUID().toString()
        val token = AppConfig.accessToken
        Log.d(TAG, "Sending authentication message. ClientID: $clientId, Token: ${if (!token.isNullOrEmpty()) "present" else "null"}")
        send(mapOf("type" to "auth", "access_token" to (token ?: ""), "client_id" to clientId))
    }

    fun sendChatMessage(content: String, conversationId: String? = null) {
        // Only send if authenticated and connected
        if (!isAuthenticated || !isConnected) {
            Log.w(TAG, "Cannot send chat message - Authenticated: $isAuthenticated, Connected: $isConnected")
            return
        }
        
        try {
            val msg = ChatMessage(id = UUID.randomUUID().toString(), conversationId = conversationId,
                role = com.aistudio.dashcompanion.data.model.MessageRole.USER, content = content)
            _chatMessages.value = _chatMessages.value + msg
            send(mapOf("type" to "chat.send", "message_id" to msg.id, "conversation_id" to conversationId, "content" to content))
            Log.d(TAG, "Chat message sent successfully")
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send chat message", e)
        }
    }

    fun sendVoiceSTT(audioBase64: String) { 
        if (isAuthenticated && isConnected) {
            try {
                send(mapOf("type" to "voice.stt", "audio_base64" to audioBase64))
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send voice STT", e)
            }
        } else {
            Log.w(TAG, "Cannot send voice STT - Authenticated: $isAuthenticated, Connected: $isConnected")
        }
    }
    
    fun sendVoiceTTS(text: String) { 
        if (isAuthenticated && isConnected) {
            try {
                send(mapOf("type" to "voice.tts", "text" to text))
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send voice TTS", e)
            }
        } else {
            Log.w(TAG, "Cannot send voice TTS - Authenticated: $isAuthenticated, Connected: $isConnected")
        }
    }
    
    fun sendMessageJson(data: Map<String, Any>) { 
        if (isAuthenticated && isConnected) {
            try {
                send(data)
            } catch (e: Exception) {
                Log.e(TAG, "Failed to send JSON message", e)
            }
        } else {
            Log.w(TAG, "Cannot send JSON message - Authenticated: $isAuthenticated, Connected: $isConnected")
        }
    }

    private fun send(data: Any) {
        try { webSocketClient?.send(moshi.adapter(Any::class.java).toJson(data)) }
        catch (e: Exception) { Log.e(TAG, "Failed to send message", e) }
    }

    private fun handleMessage(message: String) {
        try {
            val json = moshi.adapter(Any::class.java).fromJson(message) as? Map<String, Any> ?: return
            val type = json["type"] as? String ?: return

            when (type) {
                "session.info" -> { 
                    Log.i(TAG, "Session authenticated successfully")
                    isAuthenticated = true; _connectionState.value = ConnectionState.Authenticated 
                }
                "chat.token" -> { _currentResponse.value += (json["content"] as? String ?: "") }
                "chat.done" -> {
                    val content = _currentResponse.value
                    if (content.isNotEmpty()) {
                        _chatMessages.value = _chatMessages.value + ChatMessage(
                            id = json["message_id"] as? String ?: UUID.randomUUID().toString(),
                            conversationId = json["conversation_id"] as? String,
                            role = com.aistudio.dashcompanion.data.model.MessageRole.ASSISTANT, content = content)
                    }
                    _currentResponse.value = ""
                }
                "voice.tts_ready" -> {
                    val base64 = json["audio_base64"] as? String
                    if (base64 != null) {
                        _isTtsSpeaking.value = true
                        AudioPlayerManager.playBase64Audio(base64)
                        coroutineScope.launch { AudioPlayerManager.isPlaying.collect { _isTtsSpeaking.value = it } }
                    }
                }
                "system" -> {
                    val data = json["data"] as? Map<String, Any>
                    if (data != null) try { _systemState.value = systemStateAdapter.fromJsonValue(data) } catch (e: Exception) { }
                }
                "pong" -> { }
                // Desktop → Android notifications
                "desktop.notification" -> DesktopEventMonitor.handleDesktopNotification(
                    json["title"] as? String ?: "", json["text"] as? String ?: "")
                "desktop.ai.approval" -> DesktopEventMonitor.fireAiApprovalRequired(json["details"] as? String ?: "")
                "desktop.crash" -> DesktopEventMonitor.fireDesktopCrash(json["details"] as? String ?: "")
                // Phone Information Requests from Desktop
                "phone.get_state" -> sendPhoneState()
                "phone.get_apps" -> {
                    val apps = phoneDataProvider?.getInstalledApps() ?: emptyList()
                    send(mapOf("type" to "phone.apps.response", "apps" to apps.map {
                        mapOf("package_name" to it.packageName, "name" to it.name, "is_system" to it.isSystemApp)
                    }))
                }
                "phone.get_notifications" -> {
                    val notifications = phoneDataProvider?.getActiveNotifications() ?: emptyList()
                    send(mapOf("type" to "phone.notifications.response", "notifications" to notifications.map {
                        mapOf("package_name" to it.packageName, "title" to it.title, "text" to it.text, "timestamp" to it.timestamp)
                    }))
                }
                "phone.get_clipboard" -> {
                    send(mapOf("type" to "phone.clipboard.response", "text" to (phoneDataProvider?.getClipboardText() ?: "")))
                }
                // Phone Controls from Desktop
                "phone.clipboard.set" -> phoneDataProvider?.setClipboardText(json["text"] as? String ?: "")
                "phone.volume.set" -> phoneDataProvider?.setVolume((json["level"] as? Number)?.toInt() ?: 0)
                "phone.volume.mute" -> phoneDataProvider?.toggleMute()
                "phone.flashlight.set" -> phoneDataProvider?.setFlashlight(json["enabled"] as? Boolean ?: false)
                "phone.flashlight.toggle" -> phoneDataProvider?.setFlashlight(!(phoneDataProvider?.phoneState?.value?.flashlight ?: false))
                "phone.apps.open" -> {
                    val pkg = json["package_name"] as? String ?: ""
                    try {
                        val ctx = DashApplication.instance
                        val intent = ctx?.packageManager?.getLaunchIntentForPackage(pkg)
                        if (intent != null) { intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK); ctx.startActivity(intent) }
                    } catch (e: Exception) { Log.e(TAG, "Failed to open app: $pkg", e) }
                }
                "phone.notifications.clear" -> { Log.d(TAG, "Clear notifications from desktop") }
                // Media Controls from Desktop
                "phone.media.play" -> {
                    try {
                        val ctx = DashApplication.instance
                        val am = ctx?.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PLAY))
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PLAY))
                    } catch (e: Exception) { Log.e(TAG, "Media play failed", e) }
                }
                "phone.media.pause" -> {
                    try {
                        val ctx = DashApplication.instance
                        val am = ctx?.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE))
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PAUSE))
                    } catch (e: Exception) { Log.e(TAG, "Media pause failed", e) }
                }
                "phone.media.next" -> {
                    try {
                        val ctx = DashApplication.instance
                        val am = ctx?.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_NEXT))
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_NEXT))
                    } catch (e: Exception) { Log.e(TAG, "Media next failed", e) }
                }
                "phone.media.previous" -> {
                    try {
                        val ctx = DashApplication.instance
                        val am = ctx?.getSystemService(Context.AUDIO_SERVICE) as? android.media.AudioManager
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_DOWN, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS))
                        am?.dispatchMediaKeyEvent(android.view.KeyEvent(android.view.KeyEvent.ACTION_UP, android.view.KeyEvent.KEYCODE_MEDIA_PREVIOUS))
                    } catch (e: Exception) { Log.e(TAG, "Media previous failed", e) }
                }
                // Desktop Tool Execution
                "desktop.tool.execute" -> {
                    val tool = json["tool"] as? String ?: ""
                    val params = json["params"] as? Map<String, Any> ?: emptyMap()
                    Log.d(TAG, "Executing desktop tool: $tool with params: $params")
                    executeDesktopTool(tool, params)
                }
                "desktop.tool.response" -> {
                    val tool = json["tool"] as? String ?: ""
                    val result = json["result"] as? String ?: ""
                    val success = json["success"] as? Boolean ?: false
                    Log.d(TAG, "Desktop tool response: $tool - success: $success, result: $result")
                    // Could show a notification or update UI to show tool execution result
                }
                "pong" -> {
                    Log.d(TAG, "Pong received - connection is healthy")
                    // Reset missed pongs counter in heartbeat
                    // Note: This is a simple approach, for production we'd need a more sophisticated counter
                }
                else -> Log.d(TAG, "Unknown message type: $type")
            }
        } catch (e: Exception) { Log.e(TAG, "Failed to handle message", e) }
    }

    private fun executeDesktopTool(tool: String, params: Map<String, Any>) {
        try {
            val ctx = DashApplication.instance ?: return
            when (tool.lowercase()) {
                "open_chrome", "open_browser" -> {
                    val intent = ctx.packageManager.getLaunchIntentForPackage("com.android.chrome")
                    if (intent != null) {
                        intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        ctx.startActivity(intent)
                    } else {
                        // Fallback to default browser
                        val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse("https://www.google.com"))
                        browserIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                        ctx.startActivity(browserIntent)
                    }
                }
                "open_url" -> {
                    val url = params["url"] as? String ?: "https://www.google.com"
                    val browserIntent = Intent(Intent.ACTION_VIEW, Uri.parse(url))
                    browserIntent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                    ctx.startActivity(browserIntent)
                }
                "open_app" -> {
                    val packageName = params["package_name"] as? String
                    if (packageName != null) {
                        val intent = ctx.packageManager.getLaunchIntentForPackage(packageName)
                        if (intent != null) {
                            intent.addFlags(Intent.FLAG_ACTIVITY_NEW_TASK)
                            ctx.startActivity(intent)
                        }
                    }
                }
                else -> {
                    Log.d(TAG, "Unknown desktop tool: $tool")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to execute desktop tool: $tool", e)
        }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectAttempts++
        
        // Exponential backoff: 2^attempt * base_delay, capped at 30 seconds
        val backoffDelay = (2.0.pow(reconnectAttempts).toLong() * AppConfig.WEBSOCKET_RECONNECT_DELAY_MS)
            .coerceAtMost(30000L)
        
        Log.d(TAG, "Scheduling reconnection attempt $reconnectAttempts in ${backoffDelay}ms")
        
        reconnectJob = coroutineScope.launch {
            delay(backoffDelay)
            if (!isIntentionalDisconnect && !isConnected) {
                Log.d(TAG, "Attempting reconnection #$reconnectAttempts")
                connect()
            } else {
                Log.d(TAG, "Reconnection cancelled - Intentional: $isIntentionalDisconnect, Connected: $isConnected")
            }
        }
    }

    private fun forceReconnect(reason: String) {
        Log.w(TAG, "Forcing reconnection due to: $reason")
        connectionLock.lock()
        try {
            // Clean up existing connection
            webSocketClient?.close()
            webSocketClient = null
            isConnected = false
            isAuthenticated = false
            stopHeartbeat()
            stopPhoneStateBroadcast()
            
            // Reset reconnection state
            reconnectAttempts = 0
            isIntentionalDisconnect = false
            
            // Attempt immediate reconnection
            _connectionState.value = ConnectionState.Error(reason)
            coroutineScope.launch {
                delay(1000) // Small delay before reconnect
                connect()
            }
        } finally {
            connectionLock.unlock()
        }
    }

    sealed class ConnectionState {
        object Disconnected : ConnectionState()
        object Connected : ConnectionState()
        object Authenticated : ConnectionState()
        data class AuthFailed(val reason: String) : ConnectionState()
        data class Error(val message: String) : ConnectionState()
    }
}
