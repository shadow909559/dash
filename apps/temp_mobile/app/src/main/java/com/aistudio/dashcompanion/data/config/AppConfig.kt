package com.aistudio.dashcompanion.data.config

import com.aistudio.dashcompanion.BuildConfig

object AppConfig {
    var SERVER_IP = BuildConfig.DASH_SERVER_IP
    var SERVER_PORT = BuildConfig.DASH_SERVER_PORT
    
    val REST_BASE_URL: String get() = "http://$SERVER_IP:$SERVER_PORT/api/v1/"
    val WEBSOCKET_URL: String get() = "ws://$SERVER_IP:$SERVER_PORT/api/v1/ws"
    val SYSTEM_WS_URL: String get() = "ws://$SERVER_IP:$SERVER_PORT/api/v1/ws/system"
    
    const val API_PREFIX = "/api/v1"
    // Optimized timeouts for reduced latency
    const val CONNECT_TIMEOUT_SECONDS = 15L
    const val READ_TIMEOUT_SECONDS = 60L
    const val WRITE_TIMEOUT_SECONDS = 30L
    // Reduced heartbeat interval for faster connection state detection
    const val WEBSOCKET_HEARTBEAT_INTERVAL_MS = 15000L
    // Faster reconnection for better resilience
    const val WEBSOCKET_RECONNECT_DELAY_MS = 2000L

    var accessToken: String? = if (BuildConfig.DASH_ACCESS_TOKEN == "placeholder_token") null else BuildConfig.DASH_ACCESS_TOKEN
    var refreshToken: String? = if (BuildConfig.DASH_REFRESH_TOKEN == "placeholder_refresh_token") null else BuildConfig.DASH_REFRESH_TOKEN
}
