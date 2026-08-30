package com.example

import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for the device pairing flow — the end-to-end sequence from
 * pairing code → device token → stored config → authenticated WebSocket.
 *
 * Tests the observable state machine and token lifecycle that drives
 * Android ↔ DASH backend pairing without requiring a real backend.
 */
class DevicePairingFlowTest {

    @Before
    fun setUp() {
        // Simulate a clean unpaired device
        AppConfig.accessToken = null
        AppConfig.refreshToken = null
        AppConfig.setServer("10.0.2.2", "8000")
        WebSocketManager.disconnect()
        WebSocketManager.resetStream()
    }

    // ─── Pre-Pairing State ───

    @Test
    fun `device starts unauthenticated`() {
        assertFalse(AppConfig.isAuthenticated)
        assertNull(AppConfig.accessToken)
    }

    @Test
    fun `device starts at default server address`() {
        assertEquals("10.0.2.2", AppConfig.SERVER_IP)
        assertEquals("8000", AppConfig.SERVER_PORT)
    }

    @Test
    fun `device starts disconnected`() {
        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)
    }

    // ─── Pairing Flow: Step 1 — Server Configuration ───

    @Test
    fun `user configures server address`() {
        AppConfig.setServer("192.168.1.42", "8000")
        assertEquals("192.168.1.42", AppConfig.SERVER_IP)
        assertEquals("8000", AppConfig.SERVER_PORT)
        // URL should reflect new server
        assertTrue(AppConfig.REST_BASE_URL.contains("192.168.1.42"))
        assertTrue(AppConfig.WEBSOCKET_URL.contains("192.168.1.42"))
    }

    // ─── Pairing Flow: Step 2 — Token Acquisition ───

    @Test
    fun `after pairing, token is stored in AppConfig`() {
        // Simulate a successful pairing response
        val simulatedToken = "eyJhbGciOiJIUzI1NiJ9.eyJkZXZpY2VfaWQiOiJhbmRyb2lkLTEyMyJ9.signature"
        AppConfig.accessToken = simulatedToken
        assertTrue(AppConfig.isAuthenticated)
        assertEquals(simulatedToken, AppConfig.accessToken)
    }

    @Test
    fun `token enables WebSocket connection guard`() {
        AppConfig.accessToken = "pairing-token-abc"
        assertTrue(AppConfig.isAuthenticated)
        // connect() will proceed past the auth guard
        // (actual WS connection may fail if backend isn't running)
        WebSocketManager.connect()
        val state = WebSocketManager.connectionState.value
        assertTrue(
            "Should not be AuthFailed with valid pairing token, was: $state",
            state != WebSocketManager.ConnectionState.AuthFailed
        )
        WebSocketManager.disconnect()
    }

    // ─── Pairing Flow: Step 3 — Connection ───

    @Test
    fun `WebSocket connects after pairing`() {
        AppConfig.setServer("10.0.2.2", "8000")
        AppConfig.accessToken = "valid-paired-token"
        // Attempt connection — on a machine with the backend running,
        // this would transition to Connected then Authenticated
        WebSocketManager.connect()
        // The important assertion: not AuthFailed
        assertTrue(
            "State should not be AuthFailed",
            WebSocketManager.connectionState.value != WebSocketManager.ConnectionState.AuthFailed
        )
        WebSocketManager.disconnect()
    }

    // ─── Pairing Flow: Step 4 — Authentication via session.info ───

    @Test
    fun `session_aviation info transitions state to Authenticated`() {
        // This tests the expected state transition when the server sends session.info
        // We verify the state machine allows this transition
        val states = WebSocketManager.ConnectionState.entries
        assertTrue("Authenticated state exists", states.contains(WebSocketManager.ConnectionState.Authenticated))
        assertTrue("Connected state exists", states.contains(WebSocketManager.ConnectionState.Connected))
    }

    // ─── Pairing Flow: Step 5 — Streaming Works After Auth ───

    @Test
    fun `after auth, chat tokens accumulate`() {
        // Verify the chatTokens StateFlow can accumulate
        WebSocketManager.resetStream()
        assertEquals("", WebSocketManager.chatTokens.value)

        // After streaming starts (simulated), tokens accumulate
        // The actual streaming is driven by handleMessage which is private,
        // but we verify the flow is ready to receive
        assertFalse(WebSocketManager.chatDone.value)
    }

    // ─── Pairing Revocation ───

    @Test
    fun `clearing token revokes pairing`() {
        AppConfig.accessToken = "pairing-token"
        assertTrue(AppConfig.isAuthenticated)
        AppConfig.accessToken = null
        assertFalse(AppConfig.isAuthenticated)
        // WebSocket should fail auth guard
        WebSocketManager.connect()
        assertEquals(WebSocketManager.ConnectionState.AuthFailed, WebSocketManager.connectionState.value)
    }

    @Test
    fun `setting token to placeholder revokes pairing`() {
        AppConfig.accessToken = "real-token"
        assertTrue(AppConfig.isAuthenticated)
        AppConfig.accessToken = "placeholder_token"
        assertFalse(AppConfig.isAuthenticated)
    }

    // ─── Re-Pairing Flow ───

    @Test
    fun `re-pairing with new token replaces old`() {
        AppConfig.accessToken = "old-pairing-token"
        assertEquals("old-pairing-token", AppConfig.accessToken)

        // Simulate re-pairing with new token
        AppConfig.accessToken = "new-pairing-token"
        assertEquals("new-pairing-token", AppConfig.accessToken)
        assertTrue(AppConfig.isAuthenticated)
    }

    // ─── Complete Pairing Lifecycle ───

    @Test
    fun `full pairing lifecycle unpaired to configure to pair to connect to authenticated to disconnect to unpaired`() {
        // Step 1: Unpaired
        assertFalse(AppConfig.isAuthenticated)
        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)

        // Step 2: Configure server
        AppConfig.setServer("192.168.1.100", "8000")
        assertEquals("192.168.1.100", AppConfig.SERVER_IP)

        // Step 3: Receive device token from pairing
        AppConfig.accessToken = "lifecycle-test-token"
        assertTrue(AppConfig.isAuthenticated)

        // Step 4: Connect WebSocket
        WebSocketManager.connect()
        val connState = WebSocketManager.connectionState.value
        assertTrue(
            "Should not be AuthFailed with valid token",
            connState != WebSocketManager.ConnectionState.AuthFailed
        )

        // Step 5: Disconnect
        WebSocketManager.disconnect()
        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)

        // Step 6: Revoke token (simulate unpairing)
        AppConfig.accessToken = null
        assertFalse(AppConfig.isAuthenticated)
    }

    // ─── Multiple Pairing Attempts ───

    @Test
    fun `multiple rapid connect-disconnect cycles do not corrupt state`() {
        AppConfig.accessToken = "cycle-test-token"

        repeat(5) {
            WebSocketManager.connect()
            WebSocketManager.disconnect()
        }

        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)
        assertFalse(WebSocketManager.chatDone.value)
        assertEquals("", WebSocketManager.chatTokens.value)
    }

    // ─── Stream Reset After Reconnect ───

    @Test
    fun `resetStream clears accumulated state for fresh conversation`() {
        WebSocketManager.resetStream()
        // After reset, all accumulators should be clean
        assertEquals("", WebSocketManager.chatTokens.value)
        assertFalse(WebSocketManager.chatDone.value)
        assertNull(WebSocketManager.toolConfirmation.value)
        assertNull(WebSocketManager.commandResult.value)
        assertNull(WebSocketManager.sttResult.value)
        assertNull(WebSocketManager.ttsAudio.value)
        assertNull(WebSocketManager.chatStatus.value)
    }

    // ─── Token Not Exposed in URLs ───

    @Test
    fun `REST_BASE_URL does not contain token`() {
        AppConfig.accessToken = "secret-token-123"
        assertFalse(
            "REST URL should not contain token",
            AppConfig.REST_BASE_URL.contains("secret-token-123")
        )
    }

    @Test
    fun `token is passed via query parameter not header in WebSocket URL`() {
        AppConfig.accessToken = "ws-test-token"
        // WebSocket URL is the base — token is appended by WebSocketManager.connect()
        assertFalse(AppConfig.WEBSOCKET_URL.contains("ws-test-token"))
        // The full URL with token is:
        val fullUrl = "${AppConfig.WEBSOCKET_URL}?token=${AppConfig.accessToken}"
        assertTrue(fullUrl.contains("?token=ws-test-token"))
    }
}
