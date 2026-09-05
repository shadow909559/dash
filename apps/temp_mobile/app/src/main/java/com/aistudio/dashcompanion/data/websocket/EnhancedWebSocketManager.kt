package com.aistudio.dashcompanion.data.websocket

import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
import android.util.Log
import com.aistudio.dashcompanion.data.config.AppConfig
import com.aistudio.dashcompanion.data.discovery.DesktopDiscoveryManager
import com.aistudio.dashcompanion.data.model.ChatMessage
import com.aistudio.dashcompanion.data.model.ChatResponse
import com.aistudio.dashcompanion.data.model.MessageRole
import com.aistudio.dashcompanion.data.model.SystemState
import com.aistudio.dashcompanion.data.pairing.DesktopPairingManager
import com.squareup.moshi.Moshi
import com.squareup.moshi.kotlin.reflect.KotlinJsonAdapterFactory
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlin.math.pow
import org.java_websocket.client.WebSocketClient
import org.java_websocket.handshake.ServerHandshake
import java.net.URI as JavaURI
import java.util.UUID

/**
 * Enhanced WebSocket Manager with auto-discovery and persistent connection
 * Handles automatic desktop discovery, secure pairing, and reliable connection management
 */
object EnhancedWebSocketManager {
    private const val TAG = "EnhancedWebSocket"
    private val coroutineScope = CoroutineScope(Dispatchers.IO)
    
    private val moshi = Moshi.Builder()
        .add(KotlinJsonAdapterFactory())
        .build()
    
    private val chatResponseAdapter = moshi.adapter(ChatResponse::class.java)
    private val systemStateAdapter = moshi.adapter(SystemState::class.java)
    
    private var webSocketClient: WebSocketClient? = null
    private var isConnected = false
    private var isAuthenticated = false
    private var context: Context? = null
    
    // Connection management
    private var heartbeatJob: Job? = null
    private var reconnectJob: Job? = null
    private var reconnectAttempts = 0
    private var isIntentionalDisconnect = false
    private var connectionLock = java.util.concurrent.locks.ReentrantLock()
    
    // Network monitoring
    private var networkCallback: ConnectivityManager.NetworkCallback? = null
    private var connectivityManager: ConnectivityManager? = null
    
    // Auto-discovery
    private var discoveryJob: Job? = null
    private var lastDiscoveredDesktop: DesktopDiscoveryManager.DiscoveredDesktop? = null
    
    // Command system
    private val pendingCommands = mutableMapOf<String, CommandCallback>()
    private data class CommandCallback(
        val onComplete: (CommandResult) -> Unit,
        val timeout: Long = 10000L
    )
    
    data class CommandResult(
        val commandId: String,
        val success: Boolean,
        val result: String? = null,
        val error: String? = null,
        val timestamp: Long = System.currentTimeMillis()
    )
    
    sealed class ConnectionState {
        object Disconnected : ConnectionState()
        object Discovering : ConnectionState()
        object Connecting : ConnectionState()
        object Connected : ConnectionState()
        object Authenticating : ConnectionState()
        object Authenticated : ConnectionState()
        data class Error(val message: String) : ConnectionState()
        data class AuthFailed(val reason: String) : ConnectionState()
        data class DesktopUnavailable(val reason: String) : ConnectionState()
    }
    
    private val _connectionState = MutableStateFlow<ConnectionState>(ConnectionState.Disconnected)
    val connectionState: StateFlow<ConnectionState> = _connectionState.asStateFlow()
    
    private val _systemState = MutableStateFlow<SystemState?>(null)
    val systemState: StateFlow<SystemState?> = _systemState.asStateFlow()
    
    private val _chatMessages = MutableStateFlow<List<ChatMessage>>(emptyList())
    val chatMessages: StateFlow<List<ChatMessage>> = _chatMessages.asStateFlow()
    
    private val _currentResponse = MutableStateFlow<String>("")
    val currentResponse: StateFlow<String> = _currentResponse.asStateFlow()
    
    /**
     * Initialize with context
     */
    fun setContext(context: Context) {
        this.context = context
        this.connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as ConnectivityManager
        setupNetworkMonitoring()
    }
    
    /**
     * Auto-connect with discovery
     */
    fun autoConnect() {
        val ctx = context ?: return
        
        connectionLock.lock()
        try {
            // Check if we have a paired desktop
            val pairedDesktop = DesktopPairingManager.getPairedDesktop(ctx)
            if (pairedDesktop != null) {
                // Connect to known desktop
                Log.d(TAG, "Connecting to paired desktop: ${pairedDesktop.name}")
                AppConfig.SERVER_IP = pairedDesktop.ip
                AppConfig.SERVER_PORT = pairedDesktop.port.toString()
                connect(pairedDesktop.authToken)
            } else {
                // Auto-discover desktop
                Log.d(TAG, "No paired desktop, starting discovery")
                startAutoDiscovery()
            }
        } finally {
            connectionLock.unlock()
        }
    }
    
    /**
     * Start auto-discovery of desktop
     */
    private fun startAutoDiscovery() {
        val ctx = context ?: return
        
        discoveryJob?.cancel()
        _connectionState.value = ConnectionState.Discovering
        
        discoveryJob = coroutineScope.launch {
            try {
                DesktopDiscoveryManager.discoverDesktops(ctx).collect { desktop ->
                    Log.d(TAG, "Discovered desktop: ${desktop.name} at ${desktop.ip}:${desktop.port}")
                    lastDiscoveredDesktop = desktop
                    
                    // Auto-connect to first discovered desktop
                    AppConfig.SERVER_IP = desktop.ip
                    AppConfig.SERVER_PORT = desktop.port.toString()
                    connect()
                }
            } catch (e: Exception) {
                Log.e(TAG, "Auto-discovery failed", e)
                _connectionState.value = ConnectionState.Error("Discovery failed: ${e.message}")
            }
        }
    }
    
    /**
     * Connect with optional auth token
     */
    fun connect(authToken: String? = null) {
        connectionLock.lock()
        try {
            if (isConnected) {
                Log.d(TAG, "Already connected")
                return
            }
            
            // Cancel existing operations
            reconnectJob?.cancel()
            discoveryJob?.cancel()
            reconnectAttempts = 0
            isIntentionalDisconnect = false
            
            // Set auth token if provided
            authToken?.let { AppConfig.accessToken = it }
            
            // Validate token
            val token = AppConfig.accessToken
            if (token.isNullOrEmpty() || token == "placeholder_token") {
                Log.e(TAG, "No valid auth token")
                _connectionState.value = ConnectionState.AuthFailed("Authentication required")
                return
            }
            
            _connectionState.value = ConnectionState.Connecting
            Log.d(TAG, "Connecting to ${AppConfig.WEBSOCKET_URL}")
            
            webSocketClient = object : WebSocketClient(JavaURI(AppConfig.WEBSOCKET_URL)) {
                override fun onOpen(handshake: ServerHandshake?) {
                    Log.d(TAG, "WebSocket opened")
                    isConnected = true
                    _connectionState.value = ConnectionState.Connected
                    authenticate()
                    startHeartbeat()
                }
                
                override fun onMessage(message: String?) {
                    message?.let { handleMessage(it) }
                }
                
                override fun onClose(code: Int, reason: String?, remote: Boolean) {
                    handleDisconnect(code, reason, remote)
                }
                
                override fun onError(ex: Exception?) {
                    Log.e(TAG, "WebSocket error: ${ex?.message}", ex)
                    _connectionState.value = ConnectionState.Error(ex?.message ?: "Unknown error")
                    stopHeartbeat()
                }
            }
            
            webSocketClient?.connect()
        } catch (e: Exception) {
            Log.e(TAG, "Connection failed", e)
            _connectionState.value = ConnectionState.Error(e.message ?: "Connection failed")
        } finally {
            connectionLock.unlock()
        }
    }
    
    /**
     * Disconnect intentionally
     */
    fun disconnect() {
        connectionLock.lock()
        try {
            isIntentionalDisconnect = true
            reconnectJob?.cancel()
            discoveryJob?.cancel()
            reconnectAttempts = 0
            
            webSocketClient?.close()
            webSocketClient = null
            isConnected = false
            isAuthenticated = false
            stopHeartbeat()
            _connectionState.value = ConnectionState.Disconnected
            
            Log.d(TAG, "Disconnected")
        } finally {
            connectionLock.unlock()
        }
    }
    
    /**
     * Handle disconnect with reconnection logic
     */
    private fun handleDisconnect(code: Int, reason: String?, remote: Boolean) {
        Log.w(TAG, "Disconnected - Code: $code, Reason: $reason, Remote: $remote")
        
        isConnected = false
        isAuthenticated = false
        stopHeartbeat()
        
        // Check for auth failure
        if (code == 4001 || reason?.contains("auth", ignoreCase = true) == true) {
            _connectionState.value = ConnectionState.AuthFailed(reason ?: "Authentication failed")
            return
        }
        
        // Check for desktop unavailable
        if (code == 1003 || reason?.contains("unavailable", ignoreCase = true) == true) {
            _connectionState.value = ConnectionState.DesktopUnavailable(reason ?: "Desktop unavailable")
            return
        }
        
        _connectionState.value = ConnectionState.Disconnected
        
        // Auto-reconnect if not intentional
        if (!isIntentionalDisconnect && remote && code != 1000) {
            scheduleReconnect()
        }
    }
    
    /**
     * Schedule reconnection with exponential backoff
     */
    private fun scheduleReconnect() {
        reconnectJob?.cancel()
        
        val delay = calculateBackoffDelay(reconnectAttempts)
        Log.d(TAG, "Scheduling reconnect in ${delay}ms (attempt $reconnectAttempts)")
        
        reconnectJob = coroutineScope.launch {
            delay(delay)
            reconnectAttempts++
            _connectionState.value = ConnectionState.Connecting
            connect()
        }
    }
    
    /**
     * Calculate exponential backoff delay
     */
    private fun calculateBackoffDelay(attempt: Int): Long {
        val baseDelay = 2000L // 2 seconds
        val maxDelay = 30000L // 30 seconds
        val delay = (baseDelay * (2.0.pow(attempt.coerceAtMost(5)))).toLong()
        return delay.coerceAtMost(maxDelay)
    }
    
    /**
     * Authenticate with server
     */
    private fun authenticate() {
        _connectionState.value = ConnectionState.Authenticating
        
        val authMessage = mapOf(
            "type" to "auth",
            "token" to (AppConfig.accessToken ?: ""),
            "timestamp" to System.currentTimeMillis()
        )
        
        sendMessage(authMessage)
    }
    
    /**
     * Start heartbeat
     */
    private fun startHeartbeat() {
        stopHeartbeat()
        heartbeatJob = coroutineScope.launch {
            while (isConnected) {
                delay(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS)
                if (isConnected) {
                    sendHeartbeat()
                }
            }
        }
    }
    
    private fun stopHeartbeat() {
        heartbeatJob?.cancel()
        heartbeatJob = null
    }
    
    private fun sendHeartbeat() {
        val heartbeat = mapOf(
            "type" to "heartbeat",
            "timestamp" to System.currentTimeMillis()
        )
        sendMessage(heartbeat)
    }
    
    /**
     * Send message to server
     */
    private fun sendMessage(message: Map<String, Any>) {
        try {
            val json = moshi.adapter(Map::class.java).toJson(message)
            webSocketClient?.send(json)
        } catch (e: Exception) {
            Log.e(TAG, "Failed to send message", e)
        }
    }
    
    /**
     * Handle incoming message
     */
    private fun handleMessage(message: String) {
        try {
            val json = moshi.adapter(Map::class.java).fromJson(message) as? Map<String, Any>
            val type = json?.get("type") as? String ?: return
            
            when (type) {
                "auth_success" -> {
                    isAuthenticated = true
                    _connectionState.value = ConnectionState.Authenticated
                    reconnectAttempts = 0 // Reset reconnection attempts on successful auth
                    Log.d(TAG, "Authentication successful")
                }
                "auth_error" -> {
                    val reason = json["reason"] as? String ?: "Unknown error"
                    _connectionState.value = ConnectionState.AuthFailed(reason)
                    Log.e(TAG, "Authentication failed: $reason")
                }
                "system_state" -> {
                    val systemStateJson = json["data"] as? Map<String, Any>
                    val systemState = systemStateAdapter.fromJsonValue(systemStateJson) as? SystemState
                    systemState?.let { _systemState.value = it }
                }
                "chat_response" -> {
                    val responseJson = json["data"] as? Map<String, Any>
                    val response = chatResponseAdapter.fromJsonValue(responseJson) as? ChatResponse
                    response?.let { handleChatResponse(it) }
                }
                "command_result" -> {
                    handleCommandResult(json)
                }
                "heartbeat_ack" -> {
                    // Heartbeat acknowledged, connection is healthy
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Failed to handle message", e)
        }
    }
    
    private fun handleChatResponse(response: ChatResponse) {
        _currentResponse.value = response.content

        if (response.done) {
            val message = ChatMessage(
                role = MessageRole.ASSISTANT,
                content = _currentResponse.value,
                timestamp = System.currentTimeMillis()
            )
            _chatMessages.value = _chatMessages.value + message
            _currentResponse.value = ""
        }
    }
    
    private fun handleCommandResult(json: Map<String, Any>) {
        val commandId = json["command_id"] as? String ?: return
        val success = json["success"] as? Boolean ?: false
        val result = json["result"] as? String
        val error = json["error"] as? String
        
        val commandResult = CommandResult(
            commandId = commandId,
            success = success,
            result = result,
            error = error
        )
        
        pendingCommands[commandId]?.onComplete(commandResult)
        pendingCommands.remove(commandId)
    }
    
    /**
     * Send command to desktop
     */
    fun sendCommand(
        command: String,
        payload: Map<String, Any> = emptyMap(),
        onComplete: (CommandResult) -> Unit
    ) {
        if (!isAuthenticated) {
            onComplete(CommandResult(
                commandId = "",
                success = false,
                error = "Not authenticated"
            ))
            return
        }
        
        val commandId = UUID.randomUUID().toString()
        
        val commandMessage = mapOf(
            "type" to "command",
            "command_id" to commandId,
            "command" to command,
            "payload" to payload,
            "timestamp" to System.currentTimeMillis()
        )
        
        // Set timeout for command
        coroutineScope.launch {
            delay(10000L) // 10 second timeout
            if (pendingCommands.containsKey(commandId)) {
                onComplete(CommandResult(
                    commandId = commandId,
                    success = false,
                    error = "Command timeout"
                ))
                pendingCommands.remove(commandId)
            }
        }
        
        pendingCommands[commandId] = CommandCallback(onComplete)
        sendMessage(commandMessage)
    }
    
    /**
     * Setup network monitoring
     */
    private fun setupNetworkMonitoring() {
        val cm = connectivityManager ?: return
        
        val callback = object : ConnectivityManager.NetworkCallback() {
            override fun onAvailable(network: Network) {
                Log.d(TAG, "Network available")
                if (!isConnected) {
                    autoConnect()
                }
            }

            override fun onLost(network: Network) {
                Log.d(TAG, "Network lost")
                disconnect()
            }
        }
        networkCallback = callback

        val request = NetworkRequest.Builder()
            .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
            .build()

        cm.registerNetworkCallback(request, callback)
    }
    
    /**
     * Cleanup
     */
    fun cleanup() {
        networkCallback?.let {
            connectivityManager?.unregisterNetworkCallback(it)
        }
        disconnect()
    }
}