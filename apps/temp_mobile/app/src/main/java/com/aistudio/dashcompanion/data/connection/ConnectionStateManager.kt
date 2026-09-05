package com.aistudio.dashcompanion.data.connection

import android.content.Context
import android.util.Log
import com.aistudio.dashcompanion.data.monitor.DesktopStatusMonitor
import com.aistudio.dashcompanion.data.websocket.EnhancedWebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch
import kotlin.math.pow

/**
 * Connection State Manager
 * Handles offline/disconnected states and automatic recovery
 */
object ConnectionStateManager {
    private const val TAG = "ConnectionStateManager"
    private val coroutineScope = CoroutineScope(Dispatchers.IO)
    
    enum class ConnectionState {
        Online,
        Offline,
        Reconnecting,
        DesktopUnavailable,
        NetworkUnavailable,
        PairingRequired
    }
    
    data class ConnectionInfo(
        val state: ConnectionState,
        val lastConnectedTime: Long,
        val disconnectReason: String?,
        val reconnectAttempts: Int,
        val nextReconnectTime: Long
    )
    
    private val _connectionInfo = MutableStateFlow(
        ConnectionInfo(
            state = ConnectionState.Offline,
            lastConnectedTime = 0,
            disconnectReason = null,
            reconnectAttempts = 0,
            nextReconnectTime = 0
        )
    )
    val connectionInfo: StateFlow<ConnectionInfo> = _connectionInfo.asStateFlow()
    
    private var reconnectJob: Job? = null
    private var context: Context? = null
    
    /**
     * Initialize with context
     */
    fun setContext(context: Context) {
        this.context = context
    }
    
    /**
     * Handle connection state change
     */
    fun handleConnectionChange(isConnected: Boolean, reason: String? = null) {
        if (isConnected) {
            _connectionInfo.value = _connectionInfo.value.copy(
                state = ConnectionState.Online,
                lastConnectedTime = System.currentTimeMillis(),
                disconnectReason = null,
                reconnectAttempts = 0,
                nextReconnectTime = 0
            )
            Log.d(TAG, "Connection established")
        } else {
            val currentState = _connectionInfo.value
            _connectionInfo.value = currentState.copy(
                state = ConnectionState.Offline,
                disconnectReason = reason,
                nextReconnectTime = System.currentTimeMillis() + calculateReconnectDelay(currentState.reconnectAttempts)
            )
            Log.d(TAG, "Connection lost: $reason")
            
            // Start reconnection attempt
            scheduleReconnect()
        }
    }
    
    /**
     * Handle desktop unavailable state
     */
    fun handleDesktopUnavailable(reason: String) {
        _connectionInfo.value = _connectionInfo.value.copy(
            state = ConnectionState.DesktopUnavailable,
            disconnectReason = reason
        )
        Log.d(TAG, "Desktop unavailable: $reason")
    }
    
    /**
     * Handle network unavailable state
     */
    fun handleNetworkUnavailable() {
        _connectionInfo.value = _connectionInfo.value.copy(
            state = ConnectionState.NetworkUnavailable,
            disconnectReason = "Network unavailable"
        )
        Log.d(TAG, "Network unavailable")
    }
    
    /**
     * Handle pairing required state
     */
    fun handlePairingRequired(reason: String) {
        _connectionInfo.value = _connectionInfo.value.copy(
            state = ConnectionState.PairingRequired,
            disconnectReason = reason
        )
        Log.d(TAG, "Pairing required: $reason")
    }
    
    /**
     * Schedule reconnection attempt
     */
    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        
        val currentInfo = _connectionInfo.value
        val delay = calculateReconnectDelay(currentInfo.reconnectAttempts)
        
        _connectionInfo.value = currentInfo.copy(
            state = ConnectionState.Reconnecting,
            reconnectAttempts = currentInfo.reconnectAttempts + 1,
            nextReconnectTime = System.currentTimeMillis() + delay
        )
        
        reconnectJob = coroutineScope.launch {
            delay(delay)
            attemptReconnect()
        }
        
        Log.d(TAG, "Scheduling reconnect in ${delay}ms (attempt ${currentInfo.reconnectAttempts + 1})")
    }
    
    /**
     * Attempt reconnection
     */
    private fun attemptReconnect() {
        val currentInfo = _connectionInfo.value
        
        when (currentInfo.state) {
            ConnectionState.Offline, ConnectionState.Reconnecting -> {
                Log.d(TAG, "Attempting reconnection (attempt ${currentInfo.reconnectAttempts})")
                EnhancedWebSocketManager.autoConnect()
            }
            ConnectionState.DesktopUnavailable -> {
                Log.d(TAG, "Desktop unavailable, skipping reconnect")
                // Don't reconnect if desktop is unavailable
            }
            ConnectionState.NetworkUnavailable -> {
                Log.d(TAG, "Network unavailable, waiting for network recovery")
                // Let network monitoring handle this
            }
            ConnectionState.PairingRequired -> {
                Log.d(TAG, "Pairing required, cannot auto-reconnect")
                // User needs to re-pair
            }
            else -> {
                // Already connected or in another state
            }
        }
    }
    
    /**
     * Calculate exponential backoff delay
     */
    private fun calculateReconnectDelay(attempt: Int): Long {
        val baseDelay = 2000L // 2 seconds
        val maxDelay = 60000L // 60 seconds
        val delay = (baseDelay * (2.0.pow(attempt.coerceAtMost(5)))).toLong()
        return delay.coerceAtMost(maxDelay)
    }
    
    /**
     * Get user-friendly status message
     */
    fun getStatusMessage(): String {
        val info = _connectionInfo.value
        
        return when (info.state) {
            ConnectionState.Online -> "Connected to DASH Desktop"
            ConnectionState.Offline -> {
                if (info.disconnectReason != null) {
                    "Disconnected: ${info.disconnectReason}"
                } else {
                    "Disconnected from DASH Desktop"
                }
            }
            ConnectionState.Reconnecting -> {
                val timeUntilReconnect = (info.nextReconnectTime - System.currentTimeMillis()) / 1000
                "Reconnecting in ${timeUntilReconnect}s... (attempt ${info.reconnectAttempts})"
            }
            ConnectionState.DesktopUnavailable -> "DASH Desktop is offline. Start the desktop application to connect."
            ConnectionState.NetworkUnavailable -> "Network unavailable. Check your internet connection."
            ConnectionState.PairingRequired -> "Authentication required. Please re-pair with your desktop."
        }
    }
    
    /**
     * Check if reconnection is in progress
     */
    fun isReconnecting(): Boolean {
        return _connectionInfo.value.state == ConnectionState.Reconnecting
    }
    
    /**
     * Cancel reconnection attempts
     */
    fun cancelReconnect() {
        reconnectJob?.cancel()
        reconnectJob = null
        _connectionInfo.value = _connectionInfo.value.copy(
            state = ConnectionState.Offline,
            reconnectAttempts = 0,
            nextReconnectTime = 0
        )
        Log.d(TAG, "Reconnection cancelled")
    }
    
    /**
     * Force reconnection
     */
    fun forceReconnect() {
        cancelReconnect()
        EnhancedWebSocketManager.disconnect()
        coroutineScope.launch {
            delay(1000)
            EnhancedWebSocketManager.autoConnect()
        }
    }
    
    /**
     * Get current state
     */
    fun getCurrentState(): ConnectionState {
        return _connectionInfo.value.state
    }
}