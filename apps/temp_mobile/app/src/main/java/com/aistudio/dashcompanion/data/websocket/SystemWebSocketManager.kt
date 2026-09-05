package com.aistudio.dashcompanion.data.websocket

import android.util.Log
import com.aistudio.dashcompanion.data.config.AppConfig
import com.aistudio.dashcompanion.data.model.SystemState
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
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

object SystemWebSocketManager {
    private const val TAG = "SystemWebSocketManager"
    private val coroutineScope = CoroutineScope(Dispatchers.IO)

    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()

    private val systemStateAdapter = moshi.adapter(SystemState::class.java)

    private var webSocketClient: WebSocketClient? = null
    private var isConnected = false
    private var heartbeatJob: kotlinx.coroutines.Job? = null
    
    // Reconnection management
    private var reconnectJob: kotlinx.coroutines.Job? = null
    private var reconnectAttempts = 0
    private var isIntentionalDisconnect = false
    private var connectionLock = java.util.concurrent.locks.ReentrantLock()

    private val _connectionState = MutableStateFlow<SystemConnectionState>(SystemConnectionState.Disconnected)
    val connectionState: StateFlow<SystemConnectionState> = _connectionState.asStateFlow()

    private val _systemState = MutableStateFlow<SystemState?>(null)
    val systemState: StateFlow<SystemState?> = _systemState.asStateFlow()

    fun connect() {
        connectionLock.lock()
        try {
            if (isConnected) {
                Log.d(TAG, "Already connected")
                return
            }
            
            // Cancel any existing reconnection attempts
            reconnectJob?.cancel()
            reconnectAttempts = 0
            isIntentionalDisconnect = false

            try {
                val uri = JavaURI(AppConfig.SYSTEM_WS_URL)
                Log.d(TAG, "Connecting to system WS: $uri")

            webSocketClient = object : WebSocketClient(uri) {
                override fun onOpen(handshake: ServerHandshake?) {
                    Log.d(TAG, "System WebSocket connected")
                    isConnected = true
                    _connectionState.value = SystemConnectionState.Connected
                    
                    // Request full snapshot
                    val subscribeMsg = mapOf(
                        "type" to "get_full_snapshot"
                    )
                    sendJson(subscribeMsg)
                    
                    startHeartbeat()
                }

                override fun onMessage(message: String?) {
                    message?.let { handleMessage(it) }
                }

                override fun onClose(code: Int, reason: String?, remote: Boolean) {
                    val disconnectReason = "System WebSocket closed - Code: $code, Reason: $reason, Remote: $remote, Intentional: $isIntentionalDisconnect"
                    Log.w(TAG, disconnectReason)
                    
                    isConnected = false
                    stopHeartbeat()
                    _connectionState.value = SystemConnectionState.Disconnected
                    
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
                    Log.e(TAG, "System WebSocket error", ex)
                    _connectionState.value = SystemConnectionState.Error(ex?.message ?: "Unknown error")
                    stopHeartbeat()
                }
            }

            webSocketClient?.connect()
        } catch (e: Exception) {
            Log.e(TAG, "Failed to connect system WS", e)
            _connectionState.value = SystemConnectionState.Error(e.message ?: "Connection failed")
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
            stopHeartbeat()
            _connectionState.value = SystemConnectionState.Disconnected
            
            Log.d(TAG, "Intentional disconnect completed")
        } finally {
            connectionLock.unlock()
        }
    }

    private fun startHeartbeat() {
        stopHeartbeat()
        heartbeatJob = coroutineScope.launch {
            while (isConnected) {
                delay(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS)
                if (isConnected) {
                    try {
                        val heartbeat = mapOf("type" to "ping")
                        sendJson(heartbeat)
                    } catch (e: Exception) {
                        Log.e(TAG, "Failed to send heartbeat", e)
                    }
                }
            }
        }
    }

    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }

    private fun sendJson(data: Map<String, Any>) {
        try {
            val json = moshi.adapter(Map::class.java).toJson(data)
            webSocketClient?.send(json)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send message", e)
        }
    }

    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        reconnectAttempts++
        
        // Exponential backoff: 2^attempt * base_delay, capped at 30 seconds
        val backoffDelay = (2.0.pow(reconnectAttempts).toLong() * AppConfig.WEBSOCKET_RECONNECT_DELAY_MS)
            .coerceAtMost(30000L)
        
        Log.d(TAG, "Scheduling system WS reconnection attempt $reconnectAttempts in ${backoffDelay}ms")
        
        reconnectJob = coroutineScope.launch {
            delay(backoffDelay)
            if (!isIntentionalDisconnect && !isConnected) {
                Log.d(TAG, "Attempting system WS reconnection #$reconnectAttempts")
                connect()
            } else {
                Log.d(TAG, "System WS reconnection cancelled - Intentional: $isIntentionalDisconnect, Connected: $isConnected")
            }
        }
    }

    private fun handleMessage(message: String) {
        try {
            val json = moshi.adapter(Any::class.java).fromJson(message) as? Map<String, Any>
            val type = json?.get("type") as? String

            when (type) {
                "system" -> {
                    val data = json["data"] as? Map<String, Any>
                    data?.let {
                        try {
                            val systemState = systemStateAdapter.fromJsonValue(it)
                            if (systemState != null) {
                                _systemState.value = systemState
                            }
                        } catch (e: Exception) {
                            Log.e(TAG, "Failed to parse system state", e)
                        }
                    }
                }
                "pong" -> {
                    Log.d(TAG, "Pong received")
                }
                "subscribed" -> {
                    Log.d(TAG, "Subscribed to system updates")
                }
                else -> {
                    Log.d(TAG, "Unknown system WS message type: $type")
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle system message", e)
        }
    }

    sealed class SystemConnectionState {
        object Disconnected : SystemConnectionState()
        object Connected : SystemConnectionState()
        data class Error(val message: String) : SystemConnectionState()
    }
}

