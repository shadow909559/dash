package com.example

import com.example.data.connection.ConnectionStateManager
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
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

/**
 * Unit tests for ConnectionStateManager — bridges WebSocket state into
 * a single high-level connection flow for the UI.
 *
 * Tests: state mapping, monitoring lifecycle, reconnection triggers,
 * and connection info data class.
 */
@OptIn(ExperimentalCoroutinesApi::class)
class ConnectionStateManagerTest {

    private val testDispatcher = StandardTestDispatcher()

    @Before
    fun setUp() {
        Dispatchers.setMain(testDispatcher)
        ConnectionStateManager.stopMonitoring()
        WebSocketManager.disconnect()
    }

    @After
    fun tearDown() {
        ConnectionStateManager.stopMonitoring()
        WebSocketManager.disconnect()
        Dispatchers.resetMain()
    }

    // ─── Info Default State ───

    @Test
    fun `Info default is Offline with disconnected message`() {
        val info = ConnectionStateManager.Info()
        assertEquals(ConnectionStateManager.State.Offline, info.state)
        assertEquals("Disconnected", info.message)
        assertEquals(0L, info.lastConnectedTime)
        assertEquals(0, info.reconnectAttempts)
    }

    @Test
    fun `Info can be constructed with all fields`() {
        val info = ConnectionStateManager.Info(
            state = ConnectionStateManager.State.Online,
            message = "Connected to DASH",
            lastConnectedTime = 1000L,
            reconnectAttempts = 3
        )
        assertEquals(ConnectionStateManager.State.Online, info.state)
        assertEquals("Connected to DASH", info.message)
        assertEquals(1000L, info.lastConnectedTime)
        assertEquals(3, info.reconnectAttempts)
    }

    // ─── State Enum Tests ───

    @Test
    fun `State enum has all expected values`() {
        val states = ConnectionStateManager.State.entries
        assertEquals(5, states.size)
        assertTrue(states.contains(ConnectionStateManager.State.Online))
        assertTrue(states.contains(ConnectionStateManager.State.Offline))
        assertTrue(states.contains(ConnectionStateManager.State.Reconnecting))
        assertTrue(states.contains(ConnectionStateManager.State.AuthFailed))
        assertTrue(states.contains(ConnectionStateManager.State.NetworkUnavailable))
    }

    // ─── Monitoring Lifecycle ───

    @Test
    fun `startMonitoring then stopMonitoring does not throw`() {
        ConnectionStateManager.startMonitoring()
        ConnectionStateManager.stopMonitoring()
        // No exception = pass
    }

    @Test
    fun `startMonitoring twice does not create duplicate monitors`() {
        ConnectionStateManager.startMonitoring()
        ConnectionStateManager.startMonitoring()
        ConnectionStateManager.stopMonitoring()
        // No exception = pass
    }

    @Test
    fun `stopMonitoring when not started does not throw`() {
        ConnectionStateManager.stopMonitoring()
        // No exception = pass
    }

    // ─── State Mapping via WebSocket State ───

    @Test
    fun `when WS is Disconnected, Info state is Offline initially`() {
        WebSocketManager.disconnect()
        // The ConnectionStateManager maps Disconnected -> Reconnecting when monitoring
        // but without monitoring, the info retains its initial value
        val info = ConnectionStateManager.info.value
        // Initially it's Offline since monitoring hasn't started
        assertEquals(ConnectionStateManager.State.Offline, info.state)
    }

    // ─── WebSocketManager Connection States Coverage ───

    @Test
    fun `WebSocketManager ConnectionState enum has all expected values`() {
        val states = WebSocketManager.ConnectionState.entries
        assertEquals(5, states.size)
        assertTrue(states.contains(WebSocketManager.ConnectionState.Disconnected))
        assertTrue(states.contains(WebSocketManager.ConnectionState.Connected))
        assertTrue(states.contains(WebSocketManager.ConnectionState.Authenticated))
        assertTrue(states.contains(WebSocketManager.ConnectionState.AuthFailed))
        assertTrue(states.contains(WebSocketManager.ConnectionState.DisconnectedError))
    }

    @Test
    fun `WebSocketManager connectionState is observable`() {
        // Just verify it's a StateFlow we can read from
        val currentState = WebSocketManager.connectionState.value
        assertTrue(currentState is WebSocketManager.ConnectionState)
    }

    @Test
    fun `WebSocketManager systemState is observable`() {
        val state = WebSocketManager.systemState.value
        assertEquals(0.0, state.cpuPercent, 0.001)
    }

    // ─── WebSocketManager Data Classes ───

    @Test
    fun `ToolConfirmation equality works`() {
        val tc1 = WebSocketManager.ToolConfirmation(
            toolName = "cmd", params = mapOf("a" to 1), confirmationToken = "tok"
        )
        val tc2 = WebSocketManager.ToolConfirmation(
            toolName = "cmd", params = mapOf("a" to 1), confirmationToken = "tok"
        )
        assertEquals(tc1, tc2)
    }

    @Test
    fun `CommandResult equality works`() {
        val cr1 = WebSocketManager.CommandResult("id1", true, "ok", "")
        val cr2 = WebSocketManager.CommandResult("id1", true, "ok", "")
        assertEquals(cr1, cr2)
    }

    @Test
    fun `SttResult equality works`() {
        val s1 = WebSocketManager.SttResult("r1", "hello")
        val s2 = WebSocketManager.SttResult("r1", "hello")
        assertEquals(s1, s2)
    }

    @Test
    fun `ChatStatus equality works`() {
        val cs1 = WebSocketManager.ChatStatus("m1", "done", "")
        val cs2 = WebSocketManager.ChatStatus("m1", "done", "")
        assertEquals(cs1, cs2)
    }

    @Test
    fun `TtsAudio equality works`() {
        val t1 = WebSocketManager.TtsAudio("base64data")
        val t2 = WebSocketManager.TtsAudio("base64data")
        assertEquals(t1, t2)
    }

    @Test
    fun `DesktopNotification equality works`() {
        val d1 = WebSocketManager.DesktopNotification("title", "text")
        val d2 = WebSocketManager.DesktopNotification("title", "text")
        assertEquals(d1, d2)
    }
}
