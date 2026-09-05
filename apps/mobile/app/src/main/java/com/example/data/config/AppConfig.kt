package com.example.data.config

import com.example.data.security.SecurityManager

/**
 * Centralized DASH configuration.
 * Loads persisted server config from encrypted storage on first access.
 * Falls back to BuildConfig values (embedded at build time from .env) if no config saved.
 *
 * Supports both local (http://) and remote (https://) connections.
 * Remote mode auto-detects Cloudflare tunnel URLs and switches to HTTPS.
 */
object AppConfig {
    // Server connection — defaults from BuildConfig (set at build time from .env),
    // overridden by SecurityManager on startup if previously paired.
    var SERVER_IP: String = com.example.BuildConfig.DASH_SERVER_IP.ifBlank { "" }
    var SERVER_PORT: String = com.example.BuildConfig.DASH_SERVER_PORT.ifBlank { "8000" }

    /** Unique device identifier — persisted in encrypted storage. */
    var DEVICE_ID: String? = null
        private set

    /** Fly.io cloud backend URL — used by cloud relay when PC is off. */
    const val CLOUD_BASE_URL: String = "http://15.206.185.189:8001"

    /** Auto-detected: true when connecting via HTTPS (Cloudflare tunnel, etc.) */
    var USE_HTTPS: Boolean = false
        private set

    val REST_BASE_URL: String
        get() {
            val scheme = if (USE_HTTPS) "https" else "http"
            val port = if (USE_HTTPS && SERVER_PORT == "8000") "443" else SERVER_PORT
            return "$scheme://$SERVER_IP:$port/api/v1/"
        }

    val WEBSOCKET_BASE_URL: String
        get() {
            val scheme = if (USE_HTTPS) "wss" else "ws"
            val port = if (USE_HTTPS && SERVER_PORT == "8000") "443" else SERVER_PORT
            return "$scheme://$SERVER_IP:$port/api/v1/ws"
        }

    val WEBSOCKET_URL: String get() = WEBSOCKET_BASE_URL

    const val CONNECT_TIMEOUT_SECONDS = 10L
    const val READ_TIMEOUT_SECONDS = 30L
    const val WRITE_TIMEOUT_SECONDS = 15L
    const val WEBSOCKET_HEARTBEAT_INTERVAL_MS = 12000L
    const val WEBSOCKET_RECONNECT_DELAY_MS = 1000L
    const val WEBSOCKET_MAX_RECONNECT_DELAY_MS = 15000L

    /** Update server address at runtime. Auto-detects HTTPS for tunnel URLs. */
    fun setServer(ip: String, port: String) {
        SERVER_IP = ip
        SERVER_PORT = port
        detectRemoteMode()
    }

    /** Set a full remote URL (e.g. "https://xxx.trycloudflare.com") */
    fun setRemoteUrl(url: String) {
        // Parse "https://hostname:port" or "https://hostname"
        val cleaned = url.trimEnd('/')
        val isHttps = cleaned.startsWith("https://")
        val host = cleaned
            .removePrefix("https://")
            .removePrefix("http://")
            .substringBefore('/')
            .substringBefore(':')
        val port = cleaned
            .removePrefix("https://")
            .removePrefix("http://")
            .substringBefore('/')
            .substringAfter(':', missingDelimiterValue = "")

        SERVER_IP = host
        SERVER_PORT = port.ifBlank { if (isHttps) "443" else "8000" }
        USE_HTTPS = isHttps
        android.util.Log.i("AppConfig", "Remote URL set: ${REST_BASE_URL}")
    }

    /** Auto-detect if we should use HTTPS based on the server hostname. */
    private fun detectRemoteMode() {
        val remoteHosts = listOf(
            ".trycloudflare.com",
            ".cfargotunnel.com",
            ".cloudflare.com",
            ".ngrok.io",
            ".ngrok-free.app",
            ".loca.lt",
            ".fly.dev",
        )
        USE_HTTPS = remoteHosts.any { SERVER_IP.contains(it) }
        if (USE_HTTPS && SERVER_PORT == "8000") {
            SERVER_PORT = "443"
        }
    }

    // In-memory token cache (synced with encrypted storage)
    @Volatile
    var accessToken: String? = null

    @Volatile
    var refreshToken: String? = null

    val isAuthenticated: Boolean
        get() = !accessToken.isNullOrBlank() && accessToken != "placeholder_token"

    /**
     * Restore all persisted configuration from encrypted storage.
     * Called once at app startup from DashApplication.
     * Falls back to BuildConfig values on first launch or when stored config is stale.
     */
    fun restoreFromStorage(context: android.content.Context) {
        val buildIp = com.example.BuildConfig.DASH_SERVER_IP.ifBlank { null }
        val buildPort = com.example.BuildConfig.DASH_SERVER_PORT.ifBlank { null }
        val buildToken = com.example.BuildConfig.DASH_ACCESS_TOKEN.ifBlank { null }

        // Restore device ID from SecurityManager
        DEVICE_ID = SecurityManager.getDeviceId(context)
        android.util.Log.i("AppConfig", "Device ID: $DEVICE_ID")

        // Restore server IP/port from encrypted storage
        val savedIp = SecurityManager.getServerIp(context)
        val savedPort = SecurityManager.getServerPort(context)

        if (!savedIp.isNullOrBlank() && savedIp != "10.0.2.2" && buildIp != null) {
            // Stored IP is a real LAN IP — use it
            SERVER_IP = savedIp
            SERVER_PORT = savedPort?.ifBlank { "8000" } ?: "8000"
        } else if (!savedIp.isNullOrBlank() && savedIp == "10.0.2.2" && buildIp != null) {
            // Stored IP is emulator default — override with BuildConfig LAN IP
            SERVER_IP = buildIp
            SERVER_PORT = buildPort ?: "8000"
            SecurityManager.saveServerConfig(context, SERVER_IP, SERVER_PORT)
            android.util.Log.i("AppConfig", "Overrode stale emulator IP with BuildConfig: $SERVER_IP")
        } else if (!savedIp.isNullOrBlank()) {
            // Stored IP exists, no BuildConfig override — use stored
            SERVER_IP = savedIp
            SERVER_PORT = savedPort?.ifBlank { "8000" } ?: "8000"
        }
        // else: already using BuildConfig defaults

        // Auto-detect remote mode from saved hostname
        detectRemoteMode()

        // Restore device token from encrypted storage
        val deviceToken = SecurityManager.getDeviceToken(context)
        if (!deviceToken.isNullOrBlank()) {
            accessToken = deviceToken
        }

        // Also check legacy auth token
        val authToken = SecurityManager.getAuthToken(context)
        if (accessToken.isNullOrBlank() && !authToken.isNullOrBlank()) {
            accessToken = authToken
        }

        // Fallback: if still no valid token, use BuildConfig token (embedded at build time)
        if (accessToken.isNullOrBlank() || accessToken == "placeholder_token") {
            if (buildToken != null && buildToken != "placeholder_token") {
                accessToken = buildToken
                // Persist to encrypted storage so next startup doesn't need BuildConfig fallback
                SecurityManager.saveDeviceToken(context, buildToken)
                SecurityManager.saveAuthToken(context, buildToken)
                android.util.Log.i("AppConfig", "Bootstrapped token from BuildConfig")
            }
        }

        // Persist server config if it's still the emulator default and we have BuildConfig
        if ((savedIp.isNullOrBlank() || savedIp == "10.0.2.2") && buildIp != null) {
            SecurityManager.saveServerConfig(context, SERVER_IP, SERVER_PORT)
        }

        android.util.Log.i("AppConfig", "Restored: server=$SERVER_IP:$SERVER_PORT (https=$USE_HTTPS), token=${if (isAuthenticated) "present" else "missing"}")
    }
}
