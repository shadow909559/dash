package com.example.data.connection

import android.util.Log
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Tracks high-level connection health: Online, Offline, Reconnecting, AuthFailed.
 * Bridges WebSocket state into a single flow consumed by the UI.
 * Auto-starts monitoring when the first collector subscribes.
 */
object ConnectionStateManager {
    private const val TAG = "ConnStateManager"
    private val scope = CoroutineScope(Dispatchers.IO)

    enum class State {
        Online, Offline, Reconnecting, AuthFailed, NetworkUnavailable
    }

    data class Info(
        val state: State = State.Offline,
        val message: String = "Disconnected",
        val lastConnectedTime: Long = 0,
        val reconnectAttempts: Int = 0
    )

    private val _info = MutableStateFlow(Info())
    val info: StateFlow<Info> = _info.asStateFlow()

    private var monitorJob: Job? = null
    private var isMonitoring = false

    fun startMonitoring() {
        if (isMonitoring) return
        isMonitoring = true
        monitorJob?.cancel()
        monitorJob = scope.launch {
            Log.i(TAG, "Connection monitoring started")
            var lastState: WebSocketManager.ConnectionState? = null
            while (true) {
                val wsState = WebSocketManager.connectionState.value
                if (wsState != lastState) {
                    lastState = wsState
                    when (wsState) {
                        WebSocketManager.ConnectionState.Authenticated -> {
                            _info.value = Info(
                                state = State.Online,
                                message = "Connected to DASH",
                                lastConnectedTime = System.currentTimeMillis(),
                                reconnectAttempts = 0
                            )
                            Log.i(TAG, "State: Online")
                        }
                        WebSocketManager.ConnectionState.Connected -> {
                            // Waiting for auth — show connecting
                            _info.value = _info.value.copy(
                                state = State.Reconnecting,
                                message = "Authenticating..."
                            )
                        }
                        WebSocketManager.ConnectionState.Disconnected -> {
                            val current = _info.value
                            _info.value = current.copy(
                                state = State.Reconnecting,
                                message = "Reconnecting\u2026",
                                reconnectAttempts = current.reconnectAttempts + 1
                            )
                            Log.d(TAG, "State: Reconnecting (#${_info.value.reconnectAttempts})")
                            // Auto-reconnect
                            delay(1500)
                            WebSocketManager.connect()
                        }
                        WebSocketManager.ConnectionState.AuthFailed -> {
                            _info.value = Info(
                                state = State.AuthFailed,
                                message = "Authentication failed \u2014 re-pair required"
                            )
                            Log.w(TAG, "State: AuthFailed")
                        }
                        WebSocketManager.ConnectionState.DisconnectedError -> {
                            _info.value = _info.value.copy(
                                state = State.Offline,
                                message = "Connection error"
                            )
                            Log.w(TAG, "State: Error")
                        }
                    }
                }
                delay(800) // Check more frequently for responsive UI
            }
        }
    }

    fun stopMonitoring() {
        isMonitoring = false
        monitorJob?.cancel()
        monitorJob = null
    }
}
