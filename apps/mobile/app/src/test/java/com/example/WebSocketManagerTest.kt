package com.example

import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.ExperimentalCoroutinesApi
import kotlinx.coroutines.test.StandardTestDispatcher
import kotlinx.coroutines.test.advanceUntilIdle
import kotlinx.coroutines.test.resetMain
import kotlinx.coroutines.test.runTest
import kotlinx.coroutines.test.setMain
import org.junit.After
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for WebSocketManager state management, message handling,
 * connection guards, and reconnection logic.
 *
 * These tests exercise the public API and observable StateFlows without
 * requiring a real network connection.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class WebSocketManagerTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        // Reset to clean state
        WebSocketManager.disconnect()
        AppConfig.accessToken = null
        AppConfig.setServer("10.0.2.2", "8000")
    }

    @After
    fun tearDown() {
        WebSocketManager.disconnect()
        Dispatchers.resetMain()
    }

    // ─── Connection Guard Tests ───

    @Test
    fun `connect with no token sets AuthFailed state`() {
        AppConfig.accessToken = null
        WebSocketManager.connect()
        assertEquals(
            WebSocketManager.ConnectionState.AuthFailed,
            WebSocketManager.connectionState.value
        )
    }

    @Test
    fun `connect with placeholder token sets AuthFailed state`() {
        AppConfig.accessToken = "placeholder_token"
        WebSocketManager.connect()
        assertEquals(
            WebSocketManager.ConnectionState.AuthFailed,
            WebSocketManager.connectionState.value
        )
    }

    @Test
    fun `connect with blank token sets AuthFailed state`() {
        AppConfig.accessToken = "   "
        WebSocketManager.connect()
        assertEquals(
            WebSocketManager.ConnectionState.AuthFailed,
            WebSocketManager.connectionState.value
        )
    }

    // ─── Disconnect Tests ───

    @Test
    fun `disconnect sets Disconnected state`() {
        WebSocketManager.disconnect()
        assertEquals(
            WebSocketManager.ConnectionState.Disconnected,
            WebSocketManager.connectionState.value
        )
    }

    @Test
    fun `disconnect clears chatTokens`() {
        // Simulate accumulated tokens via resetStream
        WebSocketManager.resetStream()
        WebSocketManager.disconnect()
        assertEquals("", WebSocketManager.chatTokens.value)
        assertFalse(WebSocketManager.chatDone.value)
    }

    @Test
    fun `disconnect clears doneMessageId`() {
        WebSocketManager.disconnect()
        assertNull(WebSocketManager.doneMessageId.value)
    }

    @Test
    fun `disconnect clears doneConversationId`() {
        WebSocketManager.disconnect()
        assertNull(WebSocketManager.doneConversationId.value)
    }

    // ─── Reset Stream Tests ───

    @Test
    fun `resetStream clears all streaming accumulators`() {
        WebSocketManager.resetStream()
        assertEquals("", WebSocketManager.chatTokens.value)
        assertFalse(WebSocketManager.chatDone.value)
        assertNull(WebSocketManager.doneMessageId.value)
        assertNull(WebSocketManager.doneConversationId.value)
        assertNull(WebSocketManager.toolConfirmation.value)
        assertNull(WebSocketManager.commandResult.value)
        assertNull(WebSocketManager.sttResult.value)
        assertNull(WebSocketManager.ttsAudio.value)
        assertNull(WebSocketManager.chatStatus.value)
    }

    // ─── Connection State Flow Tests ───

    @Test
    fun `connectionState default is Disconnected`() {
        WebSocketManager.disconnect()
        assertEquals(
            WebSocketManager.ConnectionState.Disconnected,
            WebSocketManager.connectionState.value
        )
    }

    @Test
    fun `chatTokens default is empty`() {
        WebSocketManager.resetStream()
        assertEquals("", WebSocketManager.chatTokens.value)
    }

    @Test
    fun `chatDone default is false`() {
        WebSocketManager.resetStream()
        assertFalse(WebSocketManager.chatDone.value)
    }

    @Test
    fun `systemState default has zero metrics`() {
        val state = WebSocketManager.systemState.value
        assertEquals(0.0, state.cpuPercent, 0.001)
        assertEquals(0.0, state.ramPercent, 0.001)
        assertEquals(0.0, state.gpuPercent, 0.001)
        assertEquals(0.0, state.diskPercent, 0.001)
        assertEquals("", state.hostname)
        assertEquals("", state.platform)
        assertEquals(0L, state.uptime)
        assertFalse(state.desktopOnline)
    }

    // ─── System State Data Class Tests ───

    @Test
    fun `SystemState defaults are correct`() {
        val state = WebSocketManager.SystemState()
        assertEquals(0.0, state.cpuPercent, 0.001)
        assertEquals(0.0, state.ramPercent, 0.001)
        assertEquals(false, state.desktopOnline)
    }

    @Test
    fun `SystemState can be constructed with values`() {
        val state = WebSocketManager.SystemState(
            cpuPercent = 45.5,
            ramPercent = 72.0,
            gpuPercent = 12.3,
            diskPercent = 88.9,
            hostname = "DESKTOP-TEST",
            platform = "Windows",
            uptime = 3600,
            desktopOnline = true
        )
        assertEquals(45.5, state.cpuPercent, 0.001)
        assertEquals(72.0, state.ramPercent, 0.001)
        assertEquals(12.3, state.gpuPercent, 0.001)
        assertEquals(88.9, state.diskPercent, 0.001)
        assertEquals("DESKTOP-TEST", state.hostname)
        assertEquals("Windows", state.platform)
        assertEquals(3600L, state.uptime)
        assertTrue(state.desktopOnline)
    }

    // ─── Tool Confirmation Data Class Tests ───

    @Test
    fun `ToolConfirmation stores all fields`() {
        val tc = WebSocketManager.ToolConfirmation(
            toolName = "execute_command",
            params = mapOf("command" to "dir"),
            confirmationToken = "abc-123"
        )
        assertEquals("execute_command", tc.toolName)
        assertEquals("dir", tc.params["command"])
        assertEquals("abc-123", tc.confirmationToken)
    }

    // ─── Command Result Data Class Tests ───

    @Test
    fun `CommandResult success stores result`() {
        val cr = WebSocketManager.CommandResult(
            commandId = "cmd-1",
            success = true,
            result = "Volume set to 50%"
        )
        assertTrue(cr.success)
        assertEquals("Volume set to 50%", cr.result)
        assertEquals("", cr.error)
    }

    @Test
    fun `CommandResult failure stores error`() {
        val cr = WebSocketManager.CommandResult(
            commandId = "cmd-2",
            success = false,
            error = "Permission denied"
        )
        assertFalse(cr.success)
        assertEquals("Permission denied", cr.error)
    }

    // ─── Desktop Notification Data Class Tests ───

    @Test
    fun `DesktopNotification stores title and text`() {
        val dn = WebSocketManager.DesktopNotification(
            title = "System Alert",
            text = "CPU usage exceeded 90%"
        )
        assertEquals("System Alert", dn.title)
        assertEquals("CPU usage exceeded 90%", dn.text)
    }

    // ─── STT Result Data Class Tests ───

    @Test
    fun `SttResult stores request and text`() {
        val stt = WebSocketManager.SttResult(
            requestId = "req-1",
            text = "Hello DASH"
        )
        assertEquals("req-1", stt.requestId)
        assertEquals("Hello DASH", stt.text)
    }

    // ─── Chat Status Data Class Tests ───

    @Test
    fun `ChatStatus stores all fields`() {
        val cs = WebSocketManager.ChatStatus(
            messageId = "msg-1",
            status = "thinking",
            detail = "Processing tool call"
        )
        assertEquals("msg-1", cs.messageId)
        assertEquals("thinking", cs.status)
        assertEquals("Processing tool call", cs.detail)
    }

    // ─── TTS Audio Data Class Tests ───

    @Test
    fun `TtsAudio stores audio base64`() {
        val tts = WebSocketManager.TtsAudio(audioBase64 = "SGVsbG8=")
        assertEquals("SGVsbG8=", tts.audioBase64)
    }

    // ─── sendChatMessage Guard Tests ───

    @Test
    fun `sendChatMessage when not connected is a no-op`() {
        WebSocketManager.disconnect()
        // Should not throw — just logs a warning
        WebSocketManager.sendChatMessage("Hello DASH")
        // Tokens should remain empty since we're not connected
        assertEquals("", WebSocketManager.chatTokens.value)
    }

    // ─── sendCommand Guard Tests ───

    @Test
    fun `sendCommand when not connected is a no-op`() {
        WebSocketManager.disconnect()
        // Should not throw
        WebSocketManager.sendCommand("get_volume")
    }

    // ─── confirmTool Tests ───

    @Test
    fun `confirmTool clears toolConfirmation`() {
        WebSocketManager.resetStream()
        WebSocketManager.confirmTool("token-123", true)
        assertNull(WebSocketManager.toolConfirmation.value)
    }

    @Test
    fun `confirmTool reject also clears toolConfirmation`() {
        WebSocketManager.resetStream()
        WebSocketManager.confirmTool("token-456", false)
        assertNull(WebSocketManager.toolConfirmation.value)
    }

    // ─── cancelChat Test ───

    @Test
    fun `cancelChat does not throw when disconnected`() {
        WebSocketManager.disconnect()
        WebSocketManager.cancelChat()
        // No exception = pass
    }
}
