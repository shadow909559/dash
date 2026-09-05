package com.aistudio.dashcompanion.data.command

import android.util.Log
import com.aistudio.dashcompanion.data.websocket.EnhancedWebSocketManager
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Command Execution Manager
 * Handles low-latency command execution with proper command envelopes
 */
object CommandExecutionManager {
    private const val TAG = "CommandExecution"
    
    data class CommandEnvelope(
        val commandId: String,
        val command: String,
        val payload: Map<String, Any>,
        val timestamp: Long,
        val authentication: String
    )
    
    data class CommandStatus(
        val commandId: String,
        val status: CommandState,
        val result: String? = null,
        val error: String? = null,
        val executionTime: Long = 0L
    )
    
    enum class CommandState {
        Pending,
        Executing,
        Completed,
        Failed,
        Timeout
    }
    
    private val _commandStatus = MutableStateFlow<Map<String, CommandStatus>>(emptyMap())
    val commandStatus: StateFlow<Map<String, CommandStatus>> = _commandStatus.asStateFlow()
    
    private val commandHistory = mutableListOf<CommandEnvelope>()
    
    /**
     * Execute simple control command with fast path
     */
    fun executeCommand(
        command: String,
        payload: Map<String, Any> = emptyMap(),
        onComplete: (Boolean, String?) -> Unit
    ) {
        val commandId = java.util.UUID.randomUUID().toString()
        val envelope = CommandEnvelope(
            commandId = commandId,
            command = command,
            payload = payload,
            timestamp = System.currentTimeMillis(),
            authentication = com.aistudio.dashcompanion.data.config.AppConfig.accessToken ?: ""
        )
        
        // Track command status
        _commandStatus.value = _commandStatus.value + (commandId to CommandStatus(
            commandId = commandId,
            status = CommandState.Pending
        ))
        
        // Add to history
        commandHistory.add(envelope)
        
        // Send via WebSocket
        EnhancedWebSocketManager.sendCommand(command, payload) { result ->
            val status = if (result.success) CommandState.Completed else CommandState.Failed
            _commandStatus.value = _commandStatus.value + (commandId to CommandStatus(
                commandId = commandId,
                status = status,
                result = result.result,
                error = result.error,
                executionTime = System.currentTimeMillis() - envelope.timestamp
            ))
            
            onComplete(result.success, result.result)
        }
        
        Log.d(TAG, "Executing command: $command (ID: $commandId)")
    }
    
    /**
     * Volume control
     */
    fun setVolume(level: Int, onComplete: (Boolean, String?) -> Unit) {
        executeCommand("set_volume", mapOf("level" to level), onComplete)
    }
    
    /**
     * Brightness control
     */
    fun setBrightness(level: Int, onComplete: (Boolean, String?) -> Unit) {
        executeCommand("set_brightness", mapOf("level" to level), onComplete)
    }
    
    /**
     * Media control
     */
    fun mediaAction(action: String, onComplete: (Boolean, String?) -> Unit) {
        executeCommand("media_control", mapOf("action" to action), onComplete)
    }
    
    /**
     * Launch application
     */
    fun launchApplication(appName: String, onComplete: (Boolean, String?) -> Unit) {
        executeCommand("launch_app", mapOf("app" to appName), onComplete)
    }
    
    /**
     * Lock desktop
     */
    fun lockDesktop(onComplete: (Boolean, String?) -> Unit) {
        executeCommand("lock_desktop", emptyMap(), onComplete)
    }
    
    /**
     * Get system status
     */
    fun getSystemStatus(onComplete: (Boolean, String?) -> Unit) {
        executeCommand("get_system_status", emptyMap(), onComplete)
    }
    
    /**
     * Get command status
     */
    fun getCommandStatus(commandId: String): CommandStatus? {
        return _commandStatus.value[commandId]
    }
    
    /**
     * Clear old command statuses
     */
    fun clearOldStatuses(olderThanMs: Long = 60000L) {
        val cutoffTime = System.currentTimeMillis() - olderThanMs
        val currentStatuses = _commandStatus.value
        val activeStatuses = currentStatuses.filter { (_, status) ->
            (status.executionTime) > cutoffTime
        }
        _commandStatus.value = activeStatuses
    }
}