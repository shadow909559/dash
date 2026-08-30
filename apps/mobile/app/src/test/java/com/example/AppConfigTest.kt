package com.example

import com.example.data.config.AppConfig
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for AppConfig — centralized DASH configuration.
 *
 * Covers: server address management, URL construction,
 * authentication state, token lifecycle, and timeout constants.
 */
class AppConfigTest {

    @Before
    fun setUp() {
        AppConfig.accessToken = null
        AppConfig.refreshToken = null
        AppConfig.setServer("10.0.2.2", "8000")
    }

    // ─── Server Configuration ───

    @Test
    fun `default server is emulator address`() {
        // After setUp, defaults to 10.0.2.2
        assertEquals("10.0.2.2", AppConfig.SERVER_IP)
        assertEquals("8000", AppConfig.SERVER_PORT)
    }

    @Test
    fun `setServer updates IP and port`() {
        AppConfig.setServer("192.168.1.42", "9000")
        assertEquals("192.168.1.42", AppConfig.SERVER_IP)
        assertEquals("9000", AppConfig.SERVER_PORT)
    }

    @Test
    fun `REST_BASE_URL reflects current server`() {
        AppConfig.setServer("192.168.1.10", "8080")
        assertEquals("http://192.168.1.10:8080/api/v1/", AppConfig.REST_BASE_URL)
    }

    @Test
    fun `WEBSOCKET_URL reflects current server`() {
        AppConfig.setServer("10.0.0.5", "7777")
        assertEquals("ws://10.0.0.5:7777/api/v1/ws", AppConfig.WEBSOCKET_URL)
    }

    @Test
    fun `WEBSOCKET_BASE_URL matches WEBSOCKET_URL`() {
        assertEquals(AppConfig.WEBSOCKET_BASE_URL, AppConfig.WEBSOCKET_URL)
    }

    // ─── Timeout Constants ───

    @Test
    fun `timeouts are reasonable`() {
        assertTrue(AppConfig.CONNECT_TIMEOUT_SECONDS > 0)
        assertTrue(AppConfig.READ_TIMEOUT_SECONDS > AppConfig.CONNECT_TIMEOUT_SECONDS)
        assertTrue(AppConfig.WRITE_TIMEOUT_SECONDS > 0)
    }

    @Test
    fun `heartbeat interval is between 5s and 60s`() {
        assertTrue(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS >= 5000)
        assertTrue(AppConfig.WEBSOCKET_HEARTBEAT_INTERVAL_MS <= 60000)
    }

    @Test
    fun `reconnect delay is positive`() {
        assertTrue(AppConfig.WEBSOCKET_RECONNECT_DELAY_MS > 0)
    }

    @Test
    fun `max reconnect delay is greater than base delay`() {
        assertTrue(AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS > AppConfig.WEBSOCKET_RECONNECT_DELAY_MS)
    }

    @Test
    fun `max reconnect delay is at least 10 seconds`() {
        assertTrue(AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS >= 10000)
    }

    // ─── Authentication State ───

    @Test
    fun `isAuthenticated is false when token is null`() {
        AppConfig.accessToken = null
        assertFalse(AppConfig.isAuthenticated)
    }

    @Test
    fun `isAuthenticated is false when token is blank`() {
        AppConfig.accessToken = "  "
        assertFalse(AppConfig.isAuthenticated)
    }

    @Test
    fun `isAuthenticated is false for placeholder token`() {
        AppConfig.accessToken = "placeholder_token"
        assertFalse(AppConfig.isAuthenticated)
    }

    @Test
    fun `isAuthenticated is true with valid token`() {
        AppConfig.accessToken = "eyJhbGciOiJIUzI1NiJ9.test-token"
        assertTrue(AppConfig.isAuthenticated)
    }

    @Test
    fun `isAuthenticated is true with simple token`() {
        AppConfig.accessToken = "abc123"
        assertTrue(AppConfig.isAuthenticated)
    }

    // ─── Token Lifecycle ───

    @Test
    fun `setting accessToken to null clears authentication`() {
        AppConfig.accessToken = "valid-token"
        assertTrue(AppConfig.isAuthenticated)
        AppConfig.accessToken = null
        assertFalse(AppConfig.isAuthenticated)
    }

    @Test
    fun `setting refreshToken does not affect accessToken`() {
        AppConfig.accessToken = "access-123"
        AppConfig.refreshToken = "refresh-456"
        assertEquals("access-123", AppConfig.accessToken)
        assertEquals("refresh-456", AppConfig.refreshToken)
    }

    @Test
    fun `refreshToken can be set independently`() {
        AppConfig.refreshToken = "refresh-abc"
        assertEquals("refresh-abc", AppConfig.refreshToken)
    }

    @Test
    fun `refreshToken default is null`() {
        AppConfig.refreshToken = null
        assertNull(AppConfig.refreshToken)
    }

    // ─── URL Edge Cases ───

    @Test
    fun `server with unusual port constructs correct URL`() {
        AppConfig.setServer("10.0.0.1", "65535")
        assertEquals("http://10.0.0.1:65535/api/v1/", AppConfig.REST_BASE_URL)
        assertEquals("ws://10.0.0.1:65535/api/v1/ws", AppConfig.WEBSOCKET_URL)
    }

    @Test
    fun `localhost server constructs correct URL`() {
        AppConfig.setServer("localhost", "8000")
        assertEquals("http://localhost:8000/api/v1/", AppConfig.REST_BASE_URL)
    }

    @Test
    fun `IP-only server constructs correct URL`() {
        AppConfig.setServer("192.168.1.1", "8000")
        assertEquals("http://192.168.1.1:8000/api/v1/", AppConfig.REST_BASE_URL)
    }

    // ─── Multiple setServer Calls ───

    @Test
    fun `multiple setServer calls use latest values`() {
        AppConfig.setServer("10.0.0.1", "8000")
        AppConfig.setServer("10.0.0.2", "8001")
        AppConfig.setServer("10.0.0.3", "8002")
        assertEquals("10.0.0.3", AppConfig.SERVER_IP)
        assertEquals("8002", AppConfig.SERVER_PORT)
        assertEquals("http://10.0.0.3:8002/api/v1/", AppConfig.REST_BASE_URL)
    }

    // Helper
    private fun assertNull(value: Any?) {
        org.junit.Assert.assertNull(value)
    }
}
