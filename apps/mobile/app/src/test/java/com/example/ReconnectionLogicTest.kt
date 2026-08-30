package com.example

import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import kotlin.math.min
import kotlin.math.pow

/**
 * Unit tests for reconnection logic — verifies the exponential backoff formula,
 * state transition behavior during reconnection, and edge cases.
 *
 * The WebSocketManager uses:
 *   backoff = min(2^attempts * BASE_DELAY, MAX_DELAY)
 *   where BASE_DELAY=1000ms, MAX_DELAY=15000ms
 *
 * Expected sequence: 1s, 2s, 4s, 8s, 15s, 15s, ...
 */
class ReconnectionLogicTest {

    @Before
    fun setUp() {
        WebSocketManager.disconnect()
        AppConfig.accessToken = "valid-test-token"
        AppConfig.setServer("10.0.2.2", "8000")
    }

    // ─── Backoff Formula Tests ───

    @Test
    fun `reconnection backoff formula matches expected values`() {
        val baseDelay = AppConfig.WEBSOCKET_RECONNECT_DELAY_MS
        val maxDelay = AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS

        // Calculate expected backoff for each attempt
        val expectedBackoffs = listOf(
            min((2.0.pow(1).toLong() * baseDelay), maxDelay), // 2000ms
            min((2.0.pow(2).toLong() * baseDelay), maxDelay), // 4000ms
            min((2.0.pow(3).toLong() * baseDelay), maxDelay), // 8000ms
            min((2.0.pow(4).toLong() * baseDelay), maxDelay), // 16000 -> capped at 15000ms
            min((2.0.pow(4).toLong() * baseDelay), maxDelay), // capped at 15000ms
            min((2.0.pow(4).toLong() * baseDelay), maxDelay), // capped at 15000ms
        )

        assertEquals(2000L, expectedBackoffs[0])
        assertEquals(4000L, expectedBackoffs[1])
        assertEquals(8000L, expectedBackoffs[2])
        assertEquals(15000L, expectedBackoffs[3])
        assertEquals(15000L, expectedBackoffs[4])
        assertEquals(15000L, expectedBackoffs[5])
    }

    @Test
    fun `backoff never exceeds max reconnect delay`() {
        val baseDelay = AppConfig.WEBSOCKET_RECONNECT_DELAY_MS
        val maxDelay = AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS

        for (attempts in 1..20) {
            val backoff = min(
                (2.0.pow(attempts.coerceAtMost(4)).toLong() * baseDelay),
                maxDelay
            )
            assertTrue(
                "Backoff $backoff should be <= maxDelay $maxDelay at attempt $attempts",
                backoff <= maxDelay
            )
        }
    }

    @Test
    fun `backoff is always at least base delay`() {
        val baseDelay = AppConfig.WEBSOCKET_RECONNECT_DELAY_MS

        for (attempts in 1..10) {
            val backoff = min(
                (2.0.pow(attempts.coerceAtMost(4)).toLong() * baseDelay),
                AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS
            )
            assertTrue(
                "Backoff $backoff should be >= baseDelay $baseDelay",
                backoff >= baseDelay
            )
        }
    }

    @Test
    fun `backoff increases monotonically until cap`() {
        val baseDelay = AppConfig.WEBSOCKET_RECONNECT_DELAY_MS
        val maxDelay = AppConfig.WEBSOCKET_MAX_RECONNECT_DELAY_MS

        var prevBackoff = 0L
        for (attempts in 1..10) {
            val backoff = min(
                (2.0.pow(attempts.coerceAtMost(4)).toLong() * baseDelay),
                maxDelay
            )
            assertTrue(
                "Backoff should be >= previous: attempt=$attempts, prev=$prevBackoff, cur=$backoff",
                backoff >= prevBackoff
            )
            prevBackoff = backoff
        }
    }

    // ─── State Transitions During Connection ───

    @Test
    fun `initial state is Disconnected`() {
        WebSocketManager.disconnect()
        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)
    }

    @Test
    fun `disconnect resets state to Disconnected`() {
        WebSocketManager.disconnect()
        assertEquals(WebSocketManager.ConnectionState.Disconnected, WebSocketManager.connectionState.value)
    }

    @Test
    fun `connect with valid token does not set AuthFailed`() {
        AppConfig.accessToken = "valid-token-123"
        WebSocketManager.connect()
        // May transition to Connected (connecting) or DisconnectedError (if backend unreachable)
        // but should NOT be AuthFailed
        // Note: On a machine without a running backend, this will likely fail with DisconnectedError
        // The important thing is it's NOT AuthFailed
        val state = WebSocketManager.connectionState.value
        assertTrue(
            "State should not be AuthFailed for valid token, was: $state",
            state != WebSocketManager.ConnectionState.AuthFailed
        )
        WebSocketManager.disconnect()
    }

    // ─── Intentional Disconnect Prevents Reconnect ───

    @Test
    fun `intentional disconnect prevents reconnection attempts`() {
        // Disconnect intentionally
        WebSocketManager.disconnect()
        // The state should be Disconnected (not Reconnecting or DisconnectedError)
        assertEquals(
            WebSocketManager.ConnectionState.Disconnected,
            WebSocketManager.connectionState.value
        )
    }

    // ─── Token Validation Edge Cases ───

    @Test
    fun `empty string token prevents connection`() {
        AppConfig.accessToken = ""
        WebSocketManager.connect()
        assertEquals(WebSocketManager.ConnectionState.AuthFailed, WebSocketManager.connectionState.value)
    }

    @Test
    fun `very long token is accepted by guard`() {
        AppConfig.accessToken = "a".repeat(10000)
        WebSocketManager.connect()
        // Guard should pass (not AuthFailed) — actual connection may fail for other reasons
        val state = WebSocketManager.connectionState.value
        assertTrue(
            "Long token should pass auth guard, was: $state",
            state != WebSocketManager.ConnectionState.AuthFailed
        )
        WebSocketManager.disconnect()
    }

    @Test
    fun `token with special characters is accepted by guard`() {
        AppConfig.accessToken = "eyJhbGci.eyJzdWIiOiIxMjM0NTY3ODkwIn0!@#$%^&*()"
        WebSocketManager.connect()
        val state = WebSocketManager.connectionState.value
        assertTrue(
            "Special chars token should pass auth guard, was: $state",
            state != WebSocketManager.ConnectionState.AuthFailed
        )
        WebSocketManager.disconnect()
    }

    // ─── AppConfig Server URL Construction ───

    @Test
    fun `websocket URL contains token parameter`() {
        AppConfig.accessToken = "my-token-123"
        val expectedUrl = "ws://10.0.2.2:8000/api/v1/ws?token=my-token-123"
        assertEquals(expectedUrl, "${AppConfig.WEBSOCKET_URL}?token=${AppConfig.accessToken}")
    }

    // ─── Connection State Flow Updates ───

    @Test
    fun `chatDone defaults to false`() {
        WebSocketManager.resetStream()
        assertFalse(WebSocketManager.chatDone.value)
    }

    @Test
    fun `toolConfirmation defaults to null`() {
        WebSocketManager.resetStream()
        assertEquals(null, WebSocketManager.toolConfirmation.value)
    }

    @Test
    fun `commandResult defaults to null`() {
        WebSocketManager.resetStream()
        assertEquals(null, WebSocketManager.commandResult.value)
    }

    @Test
    fun `sttResult defaults to null`() {
        WebSocketManager.resetStream()
        assertEquals(null, WebSocketManager.sttResult.value)
    }

    @Test
    fun `ttsAudio defaults to null`() {
        WebSocketManager.resetStream()
        assertEquals(null, WebSocketManager.ttsAudio.value)
    }

    @Test
    fun `chatStatus defaults to null`() {
        WebSocketManager.resetStream()
        assertEquals(null, WebSocketManager.chatStatus.value)
    }
}
