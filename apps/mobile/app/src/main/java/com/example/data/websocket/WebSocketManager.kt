package com.example.data.websocket

import android.util.Log
import com.example.data.config.AppConfig
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
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI
import java.util.UUID
import kotlin.math.min
import kotlin.math.pow
import com.example.data.notification.NotificationHelper
import com.example.data.notification.NotificationChime

/**
 * DASH WebSocket Manager — low-latency connection to DASH backend.
 *
 * Authentication: ?token=<device-token> on URL.
 * Server immediately sends session.info on accept.
 *
 * Handles: chat streaming, tool confirmation, desktop control, keepalive.
 * Optimized for minimal latency: fast reconnect, short heartbeat, immediate streaming.
 */
object WebSocketManager {
    private const val TAG = "DASHWebSocket"
    private val scope = CoroutineScope(Dispatchers.IO)
    private var appContext: android.content.Context? = null
    private var lastNotifKey = ""

    fun init(context: android.content.Context) {
        appContext = context.applicationContext
        com.example.data.notification.NotificationHelper.init(context)
    }

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    private var client: WebSocketClient? = null
    private var isConnected = false
    private var heartbeatJob: Job? = null
    private var reconnectJob: Job? = null
    private var reconnectAttempts = 0
    private var isIntentionalDisconnect = false
    private val lock = java.util.concurrent.locks.ReentrantLock()

    // ─── Public state ───
    enum class ConnectionState {
        Disconnected, Connected, Authenticated, AuthFailed, DisconnectedError
    }

    private val _connectionState = MutableStateFlow(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()

    
    // Agent state
    private val _agentEvents = MutableStateFlow<List<Map<String, Any>>>(emptyList())
    val agentEvents: StateFlow<List<Map<String, Any>>> = _agentEvents

    private val _agentGoals = MutableStateFlow<List<Map<String, Any>>>(emptyList())
    val agentGoals: StateFlow<List<Map<String, Any>>> = _agentGoals

    private val _agentStatus = MutableStateFlow<Map<String, Any>?>(null)
    val agentStatus: StateFlow<Map<String, Any>?> = _agentStatus

    private val _agentPlan = MutableStateFlow<Map<String, Any>?>(null)
    val agentPlan: StateFlow<Map<String, Any>?> = _agentPlan

private val _chatTokens = MutableStateFlow("")
    val chatTokens: StateFlow<String> = _chatTokens.asStateFlow()

    private val _chatDone = MutableStateFlow(false)
    val chatDone: StateFlow<Boolean> = _chatDone.asStateFlow()

    private val _doneMessageId = MutableStateFlow<String?>(null)
    val doneMessageId: StateFlow<String?> = _doneMessageId.asStateFlow()

    private val _doneConversationId = MutableStateFlow<String?>(null)
    val doneConversationId: StateFlow<String?> = _doneConversationId.asStateFlow()

    // ─── System state from backend ───
    data class SystemState(
        val cpuPercent: Double = 0.0,
        val ramPercent: Double = 0.0,
        val gpuPercent: Double = 0.0,
        val diskPercent: Double = 0.0,
        val hostname: String = "",
        val platform: String = "",
        val uptime: Long = 0,
        val desktopOnline: Boolean = false
    )

    private val _systemState = MutableStateFlow(SystemState())
    val systemState: StateFlow<SystemState> = _systemState.asStateFlow()

    // ─── Tool confirmation events ───
    data class ToolConfirmation(
        val toolName: String,
        val params: Map<String, Any>,
        val confirmationToken: String
    )

    private val _toolConfirmation = MutableStateFlow<ToolConfirmation?>(null)
    val toolConfirmation: StateFlow<ToolConfirmation?> = _toolConfirmation.asStateFlow()

    // ─── Notification events from backend ───
    data class DesktopNotification(val title: String, val text: String)

    private val _desktopNotification = MutableStateFlow<DesktopNotification?>(null)
    val desktopNotification: StateFlow<DesktopNotification?> = _desktopNotification.asStateFlow()

    // ─── Command result events ───
    data class CommandResult(
        val commandId: String?,
        val success: Boolean,
        val result: String = "",
        val error: String = ""
    )

    private val _commandResult = MutableStateFlow<CommandResult?>(null)
    val commandResult: StateFlow<CommandResult?> = _commandResult.asStateFlow()

    // ─── Live log streaming ───
    private val _logLines = MutableStateFlow<List<String>>(emptyList())
    val logLines: StateFlow<List<String>> = _logLines.asStateFlow()
    private val _logSubscribed = MutableStateFlow(false)
    val logSubscribed: StateFlow<Boolean> = _logSubscribed.asStateFlow()

    fun subscribeToLogs(component: String = "backend") {
        scope.launch {
            val msg = mapOf("type" to "logs.subscribe", "component" to component)
            client?.send(moshi.adapter(Map::class.java).toJson(msg))
        }
    }

    fun clearLogs() { _logLines.value = emptyList() }

    // ─── Voice STT result ───
    data class SttResult(val requestId: String, val text: String)

    private val _sttResult = MutableStateFlow<SttResult?>(null)
    val sttResult: StateFlow<SttResult?> = _sttResult.asStateFlow()

    // ─── Voice TTS audio (streaming queue) ───
    data class TtsAudio(val audioBase64: String)

    private val _ttsAudioQueue = MutableStateFlow<List<TtsAudio>>(emptyList())
    val ttsAudioQueue: StateFlow<List<TtsAudio>> = _ttsAudioQueue.asStateFlow()

    private val _ttsAudio = MutableStateFlow<TtsAudio?>(null)
    val ttsAudio: StateFlow<TtsAudio?> = _ttsAudio.asStateFlow()

    fun clearSttResult() { _sttResult.value = null }
    fun clearTtsAudio() { _ttsAudio.value = null }

    /** Pop the first audio chunk from the queue */
    fun popTtsAudio(): TtsAudio? {
        val current = _ttsAudioQueue.value
        if (current.isEmpty()) return null
        val first = current.first()
        _ttsAudioQueue.value = current.drop(1)
        return first
    }

    fun clearTtsQueue() {
        _ttsAudioQueue.value = emptyList()
        _ttsAudio.value = null
        _ttsAudioQueue.value = emptyList()
    }

    // ─── Chat status ───
    data class ChatStatus(val messageId: String, val status: String, val detail: String = "")

    private val _chatStatus = MutableStateFlow<ChatStatus?>(null)
    val chatStatus: StateFlow<ChatStatus?> = _chatStatus.asStateFlow()

    fun connect() {
        lock.lock()
        try {
            if (isConnected) {
                Log.d(TAG, "Already connected, skipping")
                return
            }

            reconnectJob?.cancel()
            reconnectAttempts = 0
            isIntentionalDisconnect = false

            val token = AppConfig.accessToken
            if (token.isNullOrBlank() || token == "placeholder_token") {
                Log.e(TAG, "No valid token — cannot connect")
                _connectionState.value = ConnectionState.AuthFailed
                return
            }

            val wsUrl = "${AppConfig.WEBSOCKET_URL}?token=$token"
            Log.i(TAG, "Connecting to ${AppConfig.SERVER_IP}:${AppConfig.SERVER_PORT}")

            _connectionState.value = ConnectionState.Connected // show connecting state

            try {
                val socket = object : WebSocketClient(URI(wsUrl)) {
                    override fun onOpen(handshake: ServerHandshake?) {
                        Log.i(TAG, "WebSocket connected")
                        isConnected = true
                        _connectionState.value = ConnectionState.Connected
                        reconnectAttempts = 0
                        startHeartbeat()
                    }

                    override fun onMessage(message: String?) {
                        message?.let { handleMessage(it) }
                    }

                    override fun onClose(code: Int, reason: String?, remote: Boolean) {
                        Log.w(TAG, "Closed code=$code reason=$reason remote=$remote")
                        isConnected = false
                        stopHeartbeat()

                        if (code == 4401 || reason?.contains("auth", true) == true) {
                            _connectionState.value = ConnectionState.AuthFailed
                            return
                        }

                        _connectionState.value = ConnectionState.Disconnected
                        if (!isIntentionalDisconnect && code != 1000) {
                            scheduleReconnect()
                        }
                    }

                    override fun onError(ex: Exception?) {
                        Log.e(TAG, "WS error: ${ex?.message}")
                        if (isConnected) {
                            _connectionState.value = ConnectionState.DisconnectedError
                        }
                        stopHeartbeat()
                    }
                }
                client = socket
                socket.connect()
            } catch (e: Exception) {
                Log.e(TAG, "Connection setup failed", e)
                _connectionState.value = ConnectionState.DisconnectedError
                scheduleReconnect()
            }
        } finally {
            lock.unlock()
        }
    }

    fun disconnect() {
        lock.lock()
        try {
            isIntentionalDisconnect = true
            reconnectJob?.cancel()
            reconnectAttempts = 0
            client?.close()
            client = null
            isConnected = false
            stopHeartbeat()
            _connectionState.value = ConnectionState.Disconnected
        } finally {
            lock.unlock()
        }
    }

    // ─── Chat ───
    fun sendChatMessage(content: String, conversationId: String? = null, voiceMode: Boolean = false) {
        if (!isConnected) {
            Log.w(TAG, "Cannot send — not connected")
            return
        }
        _chatTokens.value = ""
        _chatDone.value = false
        _doneMessageId.value = null
        _doneConversationId.value = null
        _chatStatus.value = null
        send(mapOf(
            "type" to "chat.send",
            "message_id" to UUID.randomUUID().toString(),
            "conversation_id" to (conversationId ?: ""),
            "content" to content,
            "voice_mode" to voiceMode
        ))
    }

    // ─── Tool Confirmation Response ───
    fun confirmTool(token: String, approved: Boolean) {
        send(mapOf(
            "type" to if (approved) "tool.confirmed" else "tool.rejected",
            "confirmation_token" to token
        ))
        _toolConfirmation.value = null
    }

    // ─── Cancel streaming ───
    fun cancelChat() {
        send(mapOf("type" to "chat.cancel"))
    }

    // ─── Desktop commands via WebSocket (from phone) ───
    fun sendCommand(command: String, payload: Map<String, Any> = emptyMap()) {
        if (!isConnected) {
            Log.w(TAG, "Cannot send command — not connected")
            return
        }
        send(mapOf(
            "type" to "command",
            "command" to command,
            "command_id" to UUID.randomUUID().toString(),
            "payload" to payload
        ))
    }

    // ─── Voice STT ───
    fun sendVoiceStt(audioBase64: String) {
        if (!isConnected) return
        send(mapOf(
            "type" to "voice.stt",
            "request_id" to UUID.randomUUID().toString(),
            "audio_base64" to audioBase64
        ))
    }

    /** Send a notification from Android to all desktop/other connected clients */
    fun sendNotification(title: String, message: String, notifType: String = "info") {
        if (!isConnected) return
        send(mapOf(
            "type" to "notification.send",
            "title" to title,
            "message" to message,
            "notif_type" to notifType
        ))
        Log.d(TAG, "Notification sent to desktop: $title - $message")
    }

    // ─── Heartbeat ───
        // ─── Autonomous Agent ───
    fun startAgentGoal(description: String, maxIterations: Int = 10, timeout: Double = 300.0) {
        if (!isConnected) return
        send(mapOf(
            "type" to "agent.start",
            "description" to description,
            "max_iterations" to maxIterations,
            "timeout" to timeout
        ))
    }

    fun cancelAgentGoal(goalId: String) {
        if (!isConnected) return
        send(mapOf("type" to "agent.cancel", "goal_id" to goalId))
    }

    fun queryAgentGoals() {
        if (!isConnected) return
        send(mapOf("type" to "agent.goals"))
    }

    fun queryAgentStatus() {
        if (!isConnected) return
        send(mapOf("type" to "agent.status"))
    }

    fun queryAgentPlan(goalId: String) {
        if (!isConnected) return
        send(mapOf("type" to "agent.plan", "goal_id" to goalId))
    }

private fun startHeartbeat() {
        stopHeartbeat()
        heartbeatJob = scope.launch {
            while (isConnected) {
                delay(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS)
                if (isConnected) {
                    try {
                        send(mapOf("type" to "ping"))
                    } catch (_: Exception) {
                    }
                }
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    // ─── Message dispatch ───
    @Suppress("UNCHECKED_CAST")
    private fun handleMessage(message: String) {
        try {
            val json = moshi.adapter(Any::class.java).fromJson(message) as? Map<String, Any> ?: return
            val type = json["type"] as? String ?: return

            when (type) {
                "session.info" -> {
                    Log.i(TAG, "Authenticated via session.info")
                    _connectionState.value = ConnectionState.Authenticated
                }

                "chat.token" -> {
                    _chatTokens.value += (json["content"] as? String ?: "")
                }

                "chat.done" -> {
                    _chatDone.value = true
                    _doneMessageId.value = json["message_id"] as? String
                    _doneConversationId.value = json["conversation_id"] as? String
                }

                "chat.error" -> {
                    Log.e(TAG, "Chat error: ${json["error"]}")
                    _chatDone.value = true
                }

                "chat.status" -> {
                    _chatStatus.value = ChatStatus(
                        messageId = json["message_id"] as? String ?: "",
                        status = json["status"] as? String ?: "",
                        detail = json["detail"] as? String ?: ""
                    )
                }

                "system" -> {
                    val data = json["data"] as? Map<String, Any> ?: return
                    _systemState.value = SystemState(
                        cpuPercent = (data["cpu_percent"] as? Number)?.toDouble() ?: 0.0,
                        ramPercent = (data["memory_percent"] as? Number)?.toDouble()
                            ?: (data["ram_percent"] as? Number)?.toDouble() ?: 0.0,
                        gpuPercent = (data["gpu_usage"] as? Number)?.toDouble()
                            ?: (data["gpu_percent"] as? Number)?.toDouble() ?: 0.0,
                        diskPercent = (data["disk_percent"] as? Number)?.toDouble() ?: 0.0,
                        hostname = data["hostname"] as? String ?: "",
                        platform = data["platform"] as? String ?: "",
                        uptime = (data["uptime"] as? Number)?.toLong() ?: 0,
                        desktopOnline = true
                    )
                }
                // Agent events
                "agent.goal.started" -> {
                    Log.d(TAG, "Agent goal started: ${json["goal"]}")
                    _agentEvents.value = _agentEvents.value + mapOf("type" to "started", "data" to json)
                }
                "agent.goal.step" -> {
                    _agentEvents.value = _agentEvents.value + mapOf("type" to "step", "data" to json)
                }
                "agent.goal.completed" -> {
                    Log.d(TAG, "Agent goal completed")
                    _agentEvents.value = _agentEvents.value + mapOf("type" to "completed", "data" to json)
                }
                "agent.goal.failed" -> {
                    Log.d(TAG, "Agent goal failed")
                    _agentEvents.value = _agentEvents.value + mapOf("type" to "failed", "data" to json)
                }
                "agent.goals" -> {
                    _agentGoals.value = json["goals"] as? List<Map<String, Any>> ?: emptyList()
                }
                "agent.status" -> {
                    _agentStatus.value = json["status"] as? Map<String, Any>
                }
                "agent.plan" -> {
                    _agentPlan.value = json["plan"] as? Map<String, Any>
                }


                "tool.confirmation_required" -> {
                    _toolConfirmation.value = ToolConfirmation(
                        toolName = json["tool_name"] as? String ?: "",
                        params = (json["arguments"] as? Map<String, Any>) ?: emptyMap(),
                        confirmationToken = json["confirmation_token"] as? String ?: ""
                    )
                }

                "tool.started", "tool.progress", "tool.finished", "tool.error" -> {
                    Log.d(TAG, "Tool event: $type ${json["tool_name"]}")
                }

                "notification.ack" -> {
                    Log.d(TAG, "Notification forwarded to desktop: ${json["notification_id"]}")
                }

                "desktop.notification", "notification.push" -> {
                    val notif = json["notification"] as? Map<*, *>
                    val title = (notif?.get("title") as? String)
                        ?: json["title"] as? String
                        ?: "DASH"
                    val text = (notif?.get("message") as? String)
                        ?: json["text"] as? String
                        ?: ""
                    _desktopNotification.value = DesktopNotification(
                        title = title,
                        text = text
                    )
                    // Filter out process spam (bash.exe, conhost.exe, sleep.exe, etc.)
                    val lowerText = (title + " " + text).lowercase()
                    val isProcessSpam = listOf("bash.exe", "conhost.exe", "sleep.exe",
                        "cmd.exe", "tail.exe", "wmic.exe", "searchprotocolhost",
                        "backgroundtaskhost", ".exe started", "exe stopped"
                    ).any { lowerText.contains(it) }

                    if (!isProcessSpam) {
                        // Play chime + haptic for real notifications
                        NotificationChime.play()
                        // Show as Android system notification
                        appContext?.let { ctx ->
                            NotificationHelper.showDesktopNotification(ctx, title, text)
                        }
                    }

                    // Always store in Room (for history), but throttle via dedup
                    val notifKey = "$title|$text"
                    if (notifKey != lastNotifKey && !isProcessSpam) {
                        lastNotifKey = notifKey
                        scope.launch {
                            try {
                                val ctx = appContext ?: return@launch
                                val db = com.example.data.local.DashDatabase.getDatabase(
                                    ctx, CoroutineScope(Dispatchers.IO)
                                )
                                db.dashDao().insertNotification(
                                    com.example.data.local.entity.NotificationEntity(
                                        title = title,
                                        body = text
                                    )
                                )
                            } catch (e: Exception) {
                                Log.e(TAG, "Failed to store notification: ${e.message}")
                            }
                        }
                    }
                    Log.d(TAG, "Notification received: $title - $text")
                }

                "command_result" -> {
                    _commandResult.value = CommandResult(
                        commandId = json["command_id"] as? String,
                        success = json["success"] as? Boolean ?: false,
                        result = json["result"] as? String ?: "",
                        error = json["error"] as? String ?: ""
                    )
                }

                "voice.stt.done" -> {
                    _sttResult.value = SttResult(
                        requestId = json["request_id"] as? String ?: "",
                        text = json["text"] as? String ?: ""
                    )
                }

                "voice.stt.error" -> {
                    Log.e(TAG, "STT error: ${json["error"]}")
                    _sttResult.value = SttResult(
                        requestId = json["request_id"] as? String ?: "",
                        text = ""
                    )
                }

                "voice.tts_ready", "voice.tts.done" -> {
                    val audio = json["audio_base64"] as? String ?: ""
                    if (audio.isNotBlank()) {
                        val current = _ttsAudioQueue.value
                        _ttsAudioQueue.value = current + TtsAudio(audioBase64 = audio)
                        _ttsAudio.value = TtsAudio(audioBase64 = audio)
                    }
                }

                "voice.tts.error" -> {
                    Log.e(TAG, "TTS error: ${json["error"]}")
                }

                "ai.provider.status" -> {
                    Log.d(TAG, "AI provider status: ${json["status"]} ${json["message"]}")
                }

                "logs.line" -> {
                    val line = json["line"] as? String ?: ""
                    val component = json["component"] as? String ?: "backend"
                    if (line.isNotBlank()) {
                        val current = _logLines.value
                        val updated = (current + "[$component] $line").takeLast(200)
                        _logLines.value = updated
                    }
                }
                "logs.subscribed" -> {
                    _logSubscribed.value = true
                    Log.d(TAG, "Subscribed to logs: ${json["component"]}")
                }
                "logs.ready" -> {
                    Log.d(TAG, "Log streaming ready: ${json["component"]}")
                }
                "logs.error" -> {
                    Log.e(TAG, "Log error: ${json["error"]}")
                }
                "pong" -> { /* heartbeat ack */ }
                else -> Log.d(TAG, "Unhandled: $type")
            }
        } catch (e: Exception) {
            Log.e(TAG, "Handle message error", e)
        }
    }

    private fun send(data: Any) {
        try {
            client?.send(moshi.adapter(Any::class.java).toJson(data))
        } catch (e: Exception) {
            Log.e(TAG, "Send failed", e)
        }
    }

    // ─── Reconnection (fast exponential backoff, capped) ───
    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectAttempts++
        // Faster initial reconnect: 1s, 2s, 4s, 8s, max 15s
        val backoff = min(
            (2.0.pow(reconnectAttempts.coerceAtMost(4)).toLong() * AppConfig.WEBSOCKET_RECONNECT_DELAY_MS),
            AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS
        )

        Log.d(TAG, "Reconnect #$reconnectAttempts in ${backoff}ms")
        reconnectJob = scope.launch {
            delay(backoff)
            if (!isIntentionalDisconnect && !isConnected) {
                connect()
            }
        }
    }

    /** Reset streaming accumulators before sending a new message. */
    fun resetStream() {
        _chatTokens.value = ""
        _chatDone.value = false
        _doneMessageId.value = null
        _doneConversationId.value = null
        _toolConfirmation.value = null
        _commandResult.value = null
        _sttResult.value = null
        _ttsAudio.value = null
        _chatStatus.value = null
    }
}
