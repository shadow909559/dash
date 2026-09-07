package com.example.data.connection

import android.content.Context
import android.util.Log
import com.example.data.api.CloudRelayApi
import com.example.data.api.DashApiService
import com.example.data.api.RelayRegisterRequest
import com.example.data.api.RelayWoLRequest
import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.*
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import java.net.HttpURLConnection
import java.net.URL

/**
 * AutoConnectManager — keeps the Android app perpetually connected to DASH.
 *
 * Hybrid connection flow:
 *   1. Try local backend first (fastest, lowest latency)
 *   2. If local fails, check cloud relay (Fly.io + Supabase)
 *   3. Cloud relay tells us if PC is online/offline
 *   4. If PC is offline, trigger WoL:
 *      a. Via cloud relay (sends to public IP)
 *      b. Via local API (if on same network but backend slow)
 *      c. Via direct UDP broadcast (if on same WiFi)
 *   5. After WoL, poll until PC comes online
 *   6. Once online, connect via tunnel URL or local IP
 */
object AutoConnectManager {
    private const val TAG = "AutoConnect"

    private val _isRunning = MutableStateFlow(false)
    val isRunning: StateFlow<Boolean> = _isRunning

    private val _lastStatus = MutableStateFlow("Idle")
    val lastStatus: StateFlow<String> = _lastStatus

    private val _wolMacAddress = MutableStateFlow<String?>(null)
    val wolMacAddress: StateFlow<String?> = _wolMacAddress

    private val _pcStatus = MutableStateFlow<String>("unknown")
    val pcStatus: StateFlow<String> = _pcStatus

    private val _tunnelUrl = MutableStateFlow<String?>(null)
    val tunnelUrl: StateFlow<String?> = _tunnelUrl

    private var job: Job? = null
    private val scope = CoroutineScope(Dispatchers.IO + SupervisorJob())

    private const val RECONNECT_INTERVAL_MS = 5_000L
    private const val WOL_TRIGGER_ATTEMPTS = 3
    private const val POST_WOL_POLL_MS = 3_000L
    private const val POST_WOL_MAX_WAIT_MS = 120_000L
    private const val CLOUD_CHECK_INTERVAL_MS = 30_000L

    /** Local backend base URL built from AppConfig. */
    private val localBaseUrl: String
        get() = AppConfig.REST_BASE_URL

    fun start(context: Context) {
        if (_isRunning.value) return
        _isRunning.value = true
        _lastStatus.value = "Starting..."
        val prefs = context.getSharedPreferences("dash_auto_connect", Context.MODE_PRIVATE)
        _wolMacAddress.value = prefs.getString("wol_mac", null)
        job = scope.launch {
            Log.i(TAG, "Auto-connect loop started (hybrid mode)")
            autoConnectLoop()
        }
    }

    fun stop() {
        _isRunning.value = false
        job?.cancel()
        job = null
        _lastStatus.value = "Stopped"
    }

    fun setWolMac(context: Context, mac: String?) {
        _wolMacAddress.value = mac
        context.getSharedPreferences("dash_auto_connect", Context.MODE_PRIVATE)
            .edit().putString("wol_mac", mac).apply()
    }

    fun triggerConnect() {
        if (!_isRunning.value) {
            _isRunning.value = true
            job = scope.launch { autoConnectLoop() }
        }
        scope.launch {
            _lastStatus.value = "Connecting..."
            attemptConnect()
        }
    }

    /**
     * Trigger WoL from the RemoteControl screen.
     * Tries cloud relay first (works from anywhere), then local, then direct UDP.
     */
    suspend fun triggerWoLFromUI(context: Context) {
        val mac = _wolMacAddress.value
        if (mac.isNullOrBlank()) {
            _lastStatus.value = "No MAC address configured"
            return
        }
        _lastStatus.value = "Sending Wake-on-LAN..."

        // Try smart WoL (cloud → local)
        val result = CloudRelayApi.smartWoL(
            RelayWoLRequest(
                device_id = AppConfig.DEVICE_ID ?: "dash-pc",
                mac_address = mac
            ),
            localBaseUrl
        )

        if (result != null && result.ok) {
            _lastStatus.value = "WoL sent: ${result.note}"
        } else {
            // Fallback: direct UDP
            _lastStatus.value = "Sending WoL via UDP..."
            trySendWoLDirect(mac)
        }

        _lastStatus.value = "Waiting for PC to boot..."
        waitForBackend()
    }

    // ── Main Loop ────────────────────────────────────────────

    private suspend fun autoConnectLoop() {
        var failedAttempts = 0
        var lastCloudCheck = 0L

        while (_isRunning.value) {
            val state = WebSocketManager.connectionState.value
            if (state == WebSocketManager.ConnectionState.Authenticated) {
                _lastStatus.value = "Connected"
                failedAttempts = 0

                // Periodically check cloud relay for PC status
                if (System.currentTimeMillis() - lastCloudCheck > CLOUD_CHECK_INTERVAL_MS) {
                    checkCloudRelayStatus()
                    lastCloudCheck = System.currentTimeMillis()
                }

                delay(10_000)
                continue
            }

            // Try local backend first
            val connected = attemptConnect()
            if (connected) {
                failedAttempts = 0
                _lastStatus.value = "Connected (local)"
                continue
            }

            // Local failed — check cloud relay
            failedAttempts++
            _lastStatus.value = "Local unreachable, checking cloud..."

            val cloudStatus = checkCloudRelayStatus()
            if (cloudStatus == "online") {
                // PC is online in cloud but local is unreachable
                // Maybe we're on a different network — try tunnel
                val tunnel = _tunnelUrl.value
                if (!tunnel.isNullOrBlank()) {
                    _lastStatus.value = "Connecting via tunnel: $tunnel"
                    // Switch to tunnel URL and try connecting
                    val prevIp = AppConfig.SERVER_IP
                    val prevPort = AppConfig.SERVER_PORT
                    val prevHttps = AppConfig.USE_HTTPS
                    AppConfig.setRemoteUrl(tunnel)
                    val tunnelConnected = attemptConnect()
                    if (tunnelConnected) {
                        _lastStatus.value = "Connected (tunnel)"
                        continue
                    }
                    // Restore original config if tunnel didn't work
                    AppConfig.SERVER_IP = prevIp
                    AppConfig.SERVER_PORT = prevPort
                }
                _lastStatus.value = "PC online but unreachable directly"
            } else if (cloudStatus == "offline" || cloudStatus == "unknown") {
                // PC is off — trigger WoL
                if (failedAttempts >= WOL_TRIGGER_ATTEMPTS) {
                    _lastStatus.value = "PC offline — sending Wake-on-LAN..."
                    trySendWoL()
                    _lastStatus.value = "Waiting for PC to boot..."
                    waitForBackend()
                    failedAttempts = 0
                    continue
                }
            }

            val backoff = minOf(
                RECONNECT_INTERVAL_MS * (1L shl minOf(failedAttempts - 1, 3)),
                60_000L
            )
            delay(backoff)
        }
    }

    // ── Cloud Relay ──────────────────────────────────────────

    /**
     * Check PC status via cloud relay — tries local first, then cloud.
     * Returns: "online", "offline", "unknown", or "error"
     */
    private suspend fun checkCloudRelayStatus(): String {
        return try {
            val (status, isCloud) = CloudRelayApi.smartGetPcStatus(localBaseUrl)
            if (status == null) return "error"

            _pcStatus.value = status.status
            _tunnelUrl.value = status.tunnel_url.ifBlank { null }

            // If we don't have a MAC configured, get it from cloud
            if (_wolMacAddress.value.isNullOrBlank() && status.mac_address.isNotBlank()) {
                _wolMacAddress.value = status.mac_address
            }

            val source = if (isCloud) "cloud" else "local"
            Log.i(TAG, "PC status via $source: ${status.status}, tunnel: ${status.tunnel_url}")
            status.status
        } catch (e: Exception) {
            Log.w(TAG, "Cloud relay check failed: ${e.message}")
            _pcStatus.value = "error"
            "error"
        }
    }

    /**
     * Register this Android device with both local and cloud relay.
     */
    suspend fun registerWithCloudRelay() {
        val deviceId = AppConfig.DEVICE_ID ?: "android-${android.os.Build.MODEL}"
        val request = RelayRegisterRequest(
            device_id = deviceId,
            name = "DASH Android",
            platform = "android",
            capabilities = listOf("chat", "voice", "remote_control", "wol")
        )

        try {
            CloudRelayApi.smartRegister(request, localBaseUrl)
            Log.i(TAG, "Registered with relay (device_id=$deviceId)")
        } catch (e: Exception) {
            Log.w(TAG, "Relay registration failed: ${e.message}")
        }
    }

    // ── Connection ───────────────────────────────────────────

    private suspend fun attemptConnect(): Boolean {
        return try {
            if (!AppConfig.isAuthenticated) return false
            val healthOk = checkBackendHealth()
            if (!healthOk) return false
            WebSocketManager.connect()
            delay(3000)
            WebSocketManager.connectionState.value == WebSocketManager.ConnectionState.Authenticated
        } catch (e: Exception) {
            Log.w(TAG, "Connect attempt failed: ${e.message}")
            false
        }
    }

    private fun checkBackendHealth(): Boolean {
        return try {
            val url = URL("http://${AppConfig.SERVER_IP}:${AppConfig.SERVER_PORT}/health")
            val conn = url.openConnection() as HttpURLConnection
            conn.connectTimeout = 3000
            conn.requestMethod = "GET"
            val code = conn.responseCode
            conn.disconnect()
            code == 200
        } catch (_: Exception) {
            false
        }
    }

    // ── Wake-on-LAN ──────────────────────────────────────────

    private suspend fun trySendWoL() {
        val mac = _wolMacAddress.value ?: return

        // 1. Try smart WoL (cloud relay first, then local)
        val result = CloudRelayApi.smartWoL(
            RelayWoLRequest(
                device_id = AppConfig.DEVICE_ID ?: "dash-pc",
                mac_address = mac
            ),
            localBaseUrl
        )

        if (result != null && result.ok) {
            Log.i(TAG, "WoL via relay: ${result.note}")
            _lastStatus.value = "WoL sent: ${result.note}"
            return
        }

        // 2. Try local API (works if on same network but backend is slow)
        try {
            val apiResult = DashApiService.wakeOnLan(mac)
            Log.i(TAG, "WoL result: ${apiResult.summary}")
            _lastStatus.value = "WoL sent: ${apiResult.packets_sent} packets"
            return
        } catch (e: Exception) {
            Log.w(TAG, "WoL via local API failed: ${e.message}")
        }

        // 3. Direct UDP broadcast (works if on same WiFi)
        _lastStatus.value = "Sending WoL directly via UDP..."
        trySendWoLDirect(mac)
    }

    private fun trySendWoLDirect(mac: String) {
        try {
            val cleanMac = mac.replace("-", ":").replace(".", ":").trim()
            val parts = cleanMac.split(":")
            if (parts.size != 6) {
                Log.e(TAG, "Invalid MAC: $mac")
                return
            }
            val macBytes = ByteArray(6) { parts[it].toInt(16).toByte() }
            val magicPacket = ByteArray(102)
            for (i in 0..5) magicPacket[i] = 0xFF.toByte()
            for (i in 0..15) System.arraycopy(macBytes, 0, magicPacket, 6 + i * 6, 6)

            val addresses = listOf("255.255.255.255", "192.168.1.255", "10.0.0.255")
            var sent = 0
            for (addr in addresses) {
                try {
                    val socket = java.net.DatagramSocket()
                    socket.broadcast = true
                    val packet = java.net.DatagramPacket(
                        magicPacket, magicPacket.size,
                        java.net.InetAddress.getByName(addr), 9
                    )
                    socket.send(packet)
                    socket.close()
                    sent++
                    Log.i(TAG, "WoL direct sent to $addr")
                } catch (e: Exception) {
                    Log.w(TAG, "WoL direct to $addr failed: ${e.message}")
                }
            }
            _lastStatus.value = "WoL sent directly ($sent broadcasts)"
        } catch (e: Exception) {
            Log.e(TAG, "Direct WoL failed: ${e.message}")
        }
    }

    // ── Wait for Boot ────────────────────────────────────────

    private suspend fun waitForBackend() {
        val startTime = System.currentTimeMillis()
        while (_isRunning.value && System.currentTimeMillis() - startTime < POST_WOL_MAX_WAIT_MS) {
            delay(POST_WOL_POLL_MS)
            val elapsed = (System.currentTimeMillis() - startTime) / 1000
            _lastStatus.value = "Waiting for backend... (${elapsed}s)"

            // Check local backend
            if (checkBackendHealth()) {
                Log.i(TAG, "Backend is now reachable locally")
                _lastStatus.value = "Backend online!"
                attemptConnect()
                return
            }

            // Check cloud relay
            val cloudStatus = checkCloudRelayStatus()
            if (cloudStatus == "online") {
                Log.i(TAG, "PC is online via cloud relay")
                _lastStatus.value = "PC online via cloud!"
                // Try connecting via tunnel if available
                val tunnel = _tunnelUrl.value
                if (!tunnel.isNullOrBlank()) {
                    _lastStatus.value = "Connecting via tunnel: $tunnel"
                    val prevIp = AppConfig.SERVER_IP
                    val prevPort = AppConfig.SERVER_PORT
                    AppConfig.setRemoteUrl(tunnel)
                    val tunnelConnected = attemptConnect()
                    if (tunnelConnected) {
                        _lastStatus.value = "Connected (tunnel)"
                        return
                    }
                    AppConfig.SERVER_IP = prevIp
                    AppConfig.SERVER_PORT = prevPort
                }
                attemptConnect()
                return
            }
        }
        _lastStatus.value = "Timeout waiting for PC"
    }
}
