package com.aistudio.dashcompanion.data.monitor

import android.content.Context
import android.util.Log
import com.aistudio.dashcompanion.data.websocket.EnhancedWebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.Job
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * Desktop Status Monitor
 * Comprehensive monitoring of desktop connection and system status
 */
object DesktopStatusMonitor {
    private const val TAG = "DesktopStatusMonitor"
    private val coroutineScope = CoroutineScope(Dispatchers.IO)
    
    enum class DesktopStatus {
        Unknown,
        Online,
        Offline,
        Connecting,
        ConnectionLost,
        BackendUnavailable,
        PairingRequired,
        NetworkUnavailable
    }
    
    data class DesktopHealth(
        val status: DesktopStatus,
        val connectionQuality: ConnectionQuality,
        val latency: Long,
        val lastSeen: Long,
        val systemLoad: SystemLoad?,
        val message: String
    )
    
    data class ConnectionQuality(
        val signalStrength: Int, // 0-100
        val stability: Int, // 0-100
        val reliability: Float // 0.0-1.0
    )
    
    data class SystemLoad(
        val cpuUsage: Float,
        val memoryUsage: Float,
        val diskUsage: Float,
        val networkActivity: Float
    )
    
    private val _desktopHealth = MutableStateFlow<DesktopHealth>(
        DesktopHealth(
            status = DesktopStatus.Unknown,
            connectionQuality = ConnectionQuality(0, 0, 0f),
            latency = 0,
            lastSeen = 0,
            systemLoad = null,
            message = "Status unknown"
        )
    )
    val desktopHealth: StateFlow<DesktopHealth> = _desktopHealth.asStateFlow()
    
    private var monitoringJob: Job? = null
    private var latencyCheckJob: Job? = null
    private var connectionQuality = ConnectionQuality(0, 0, 0f)
    private var latencyHistory = mutableListOf<Long>()
    private var connectionAttemptCount = 0
    private var successfulConnectionCount = 0
    
    /**
     * Start monitoring
     */
    fun startMonitoring(context: Context) {
        stopMonitoring()
        
        monitoringJob = coroutineScope.launch {
            while (true) {
                updateDesktopStatus()
                delay(5000) // Check every 5 seconds
            }
        }
        
        latencyCheckJob = coroutineScope.launch {
            while (true) {
                checkLatency()
                delay(10000) // Check latency every 10 seconds
            }
        }
        
        Log.d(TAG, "Desktop status monitoring started")
    }
    
    /**
     * Stop monitoring
     */
    fun stopMonitoring() {
        monitoringJob?.cancel()
        latencyCheckJob?.cancel()
        monitoringJob = null
        latencyCheckJob = null
        Log.d(TAG, "Desktop status monitoring stopped")
    }
    
    /**
     * Update desktop status based on connection state
     */
    private fun updateDesktopStatus() {
        val connectionState = EnhancedWebSocketManager.connectionState.value
        val systemState = EnhancedWebSocketManager.systemState.value
        
        val (status, message) = when (connectionState) {
            is EnhancedWebSocketManager.ConnectionState.Authenticated -> {
                connectionAttemptCount++
                successfulConnectionCount++
                DesktopStatus.Online to "Connected and authenticated"
            }
            is EnhancedWebSocketManager.ConnectionState.Connected -> {
                DesktopStatus.Connecting to "Connection established, authenticating"
            }
            is EnhancedWebSocketManager.ConnectionState.Connecting -> {
                DesktopStatus.Connecting to "Attempting to connect"
            }
            is EnhancedWebSocketManager.ConnectionState.Authenticating -> {
                DesktopStatus.Connecting to "Authenticating with desktop"
            }
            is EnhancedWebSocketManager.ConnectionState.Disconnected -> {
                DesktopStatus.Offline to "Disconnected from desktop"
            }
            is EnhancedWebSocketManager.ConnectionState.Discovering -> {
                DesktopStatus.Offline to "Discovering desktop"
            }
            is EnhancedWebSocketManager.ConnectionState.AuthFailed -> {
                DesktopStatus.PairingRequired to "Authentication failed, re-pairing required"
            }
            is EnhancedWebSocketManager.ConnectionState.DesktopUnavailable -> {
                DesktopStatus.BackendUnavailable to "Desktop backend unavailable"
            }
            is EnhancedWebSocketManager.ConnectionState.Error -> {
                DesktopStatus.ConnectionLost to "Connection error: ${connectionState.message}"
            }
        }

        val systemLoad = systemState?.let {
            SystemLoad(
                cpuUsage = it.cpu.percent.toFloat(),
                memoryUsage = it.ram.percent.toFloat(),
                diskUsage = it.disk.percent.toFloat(),
                networkActivity = it.network.downloadSpeed.toFloat()
            )
        }
        
        _desktopHealth.value = DesktopHealth(
            status = status,
            connectionQuality = connectionQuality,
            latency = getCurrentLatency(),
            lastSeen = System.currentTimeMillis(),
            systemLoad = systemLoad,
            message = message
        )
    }
    
    /**
     * Check latency with ping
     */
    private fun checkLatency() {
        val startTime = System.currentTimeMillis()

        coroutineScope.launch {
            // Send a ping command (single CommandResult callback)
            EnhancedWebSocketManager.sendCommand("ping", emptyMap()) { result ->
                val latency = System.currentTimeMillis() - startTime

                if (result.success) {
                    updateLatencyHistory(latency)
                    updateConnectionQuality()
                } else {
                    // Failed ping, decrease quality
                    connectionQuality = connectionQuality.copy(
                        signalStrength = (connectionQuality.signalStrength * 0.8).toInt(),
                        stability = (connectionQuality.stability * 0.7).toInt()
                    )
                }
            }
        }
    }
    
    /**
     * Update latency history
     */
    private fun updateLatencyHistory(latency: Long) {
        latencyHistory.add(latency)
        if (latencyHistory.size > 10) {
            latencyHistory.removeAt(0)
        }
    }
    
    /**
     * Get current average latency
     */
    private fun getCurrentLatency(): Long {
        return if (latencyHistory.isEmpty()) 0L else latencyHistory.average().toLong()
    }
    
    /**
     * Update connection quality based on metrics
     */
    private fun updateConnectionQuality() {
        val avgLatency = getCurrentLatency()
        val reliability = if (connectionAttemptCount > 0) {
            successfulConnectionCount.toFloat() / connectionAttemptCount.toFloat()
        } else 0f
        
        val signalStrength = when {
            avgLatency < 50 -> 100
            avgLatency < 100 -> 80
            avgLatency < 200 -> 60
            avgLatency < 500 -> 40
            else -> 20
        }
        
        val stability = (reliability * 100).toInt()
        
        connectionQuality = ConnectionQuality(
            signalStrength = signalStrength,
            stability = stability,
            reliability = reliability
        )
    }
    
    /**
     * Get current status
     */
    fun getCurrentStatus(): DesktopStatus {
        return _desktopHealth.value.status
    }
    
    /**
     * Get health message
     */
    fun getHealthMessage(): String {
        return _desktopHealth.value.message
    }
    
    /**
     * Check if desktop is healthy
     */
    fun isDesktopHealthy(): Boolean {
        val health = _desktopHealth.value
        return health.status == DesktopStatus.Online &&
               health.connectionQuality.signalStrength > 50 &&
               health.connectionQuality.stability > 70
    }
    
    /**
     * Get detailed status report
     */
    fun getStatusReport(): String {
        val health = _desktopHealth.value
        return """
            Status: ${health.status}
            Message: ${health.message}
            Signal Strength: ${health.connectionQuality.signalStrength}%
            Stability: ${health.connectionQuality.stability}%
            Reliability: ${(health.connectionQuality.reliability * 100).toInt()}%
            Latency: ${health.latency}ms
            Last Seen: ${health.lastSeen}
            CPU Load: ${health.systemLoad?.cpuUsage ?: 0}%
            Memory Load: ${health.systemLoad?.memoryUsage ?: 0}%
        """.trimIndent()
    }
}