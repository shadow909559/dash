package com.aistudio.dashcompanion.data.config

/**
 * Configuration for DashApiService that reads from centralized AppConfig.
 * This ensures REST API uses the same single source of truth as WebSocket.
 */
object DashApiConfig {
    fun getBaseUrl(): String = AppConfig.REST_BASE_URL
    
    fun getAccessToken(): String? = AppConfig.accessToken
    
    fun updateToken(token: String?) {
        AppConfig.accessToken = token
    }
}
