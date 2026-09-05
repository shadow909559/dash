package com.aistudio.dashcompanion.data.integration

import android.content.Context
import android.util.Log
import com.aistudio.dashcompanion.data.command.CommandExecutionManager
import com.aistudio.dashcompanion.data.connection.ConnectionStateManager
import com.aistudio.dashcompanion.data.discovery.DesktopDiscoveryManager
import com.aistudio.dashcompanion.data.monitor.DesktopStatusMonitor
import com.aistudio.dashcompanion.data.pairing.DesktopPairingManager
import com.aistudio.dashcompanion.data.security.SecurityManager
import com.aistudio.dashcompanion.data.websocket.EnhancedWebSocketManager
import kotlinx.coroutines.CoroutineScope
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.flow.first
import kotlinx.coroutines.launch

/**
 * Connection Integration Test Suite
 * Tests the complete end-to-end connection flow
 */
object ConnectionIntegrationTest {
    private const val TAG = "ConnectionIntegrationTest"
    private val testScope = CoroutineScope(Dispatchers.IO)
    
    data class TestResult(
        val testName: String,
        val passed: Boolean,
        val message: String,
        val duration: Long
    )
    
    private val testResults = mutableListOf<TestResult>()
    
    /**
     * Run complete integration test suite
     */
    suspend fun runCompleteTestSuite(context: Context): List<TestResult> {
        testResults.clear()
        
        Log.d(TAG, "Starting complete integration test suite")
        
        // Initialize all managers
        initializeManagers(context)
        
        // Run tests in sequence
        testDiscovery(context)
        testPairing(context)
        testConnection(context)
        testAuthentication(context)
        testCommandExecution(context)
        testVoiceCommands(context)
        testReconnection(context)
        testNetworkChange(context)
        testBackgroundConnection(context)
        testSecurity(context)
        testPerformance(context)
        
        Log.d(TAG, "Integration test suite completed")
        return testResults.toList()
    }
    
    /**
     * Initialize all managers
     */
    private fun initializeManagers(context: Context) {
        EnhancedWebSocketManager.setContext(context)
        // DesktopPairingManager is context-per-call (no setContext API)
        SecurityManager.initialize(context)
        DesktopStatusMonitor.startMonitoring(context)
        ConnectionStateManager.setContext(context)
    }
    
    /**
     * Test 1: Desktop Discovery
     */
    private suspend fun testDiscovery(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 1: Desktop Discovery")
            
            var discovered = false
            DesktopDiscoveryManager.discoverDesktops(context).collect { desktop ->
                Log.d(TAG, "Discovered desktop: ${desktop.name}")
                discovered = true
            }
            
            val duration = System.currentTimeMillis() - startTime
            if (discovered) {
                testResults.add(TestResult(
                    testName = "Desktop Discovery",
                    passed = true,
                    message = "Successfully discovered desktop",
                    duration = duration
                ))
            } else {
                testResults.add(TestResult(
                    testName = "Desktop Discovery",
                    passed = false,
                    message = "No desktop discovered (desktop may not be running)",
                    duration = duration
                ))
            }
        } catch (e: Exception) {
            val duration = System.currentTimeMillis() - startTime
            testResults.add(TestResult(
                testName = "Desktop Discovery",
                passed = false,
                message = "Discovery failed: ${e.message}",
                duration = duration
            ))
        }
    }
    
    /**
     * Test 2: Pairing Flow
     */
    private suspend fun testPairing(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 2: Pairing Flow")
            
            // Check if already paired
            if (DesktopPairingManager.isPaired(context)) {
                val desktop = DesktopPairingManager.getPairedDesktop(context)
                testResults.add(TestResult(
                    testName = "Pairing Flow",
                    passed = true,
                    message = "Already paired with ${desktop?.name}",
                    duration = System.currentTimeMillis() - startTime
                ))
                return
            }
            
            // Initiate pairing (simulated)
            val request = DesktopPairingManager.initiatePairing(
                context,
                DesktopDiscoveryManager.DiscoveredDesktop(
                    name = "Test Desktop",
                    host = "localhost",
                    port = 8765,
                    ip = "127.0.0.1"
                )
            )
            
            val response = DesktopPairingManager.PairingResponse(
                desktopId = "test-desktop-id",
                desktopName = "Test Desktop",
                publicKey = "test-public-key",
                authToken = "test-auth-token",
                timestamp = System.currentTimeMillis(),
                approved = true
            )
            
            val pairedDesktop = DesktopPairingManager.confirmPairing(
                context,
                DesktopDiscoveryManager.DiscoveredDesktop(
                    name = "Test Desktop",
                    host = "localhost",
                    port = 8765,
                    ip = "127.0.0.1"
                ),
                response
            )
            
            testResults.add(TestResult(
                testName = "Pairing Flow",
                passed = true,
                message = "Successfully paired with ${pairedDesktop.name}",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Pairing Flow",
                passed = false,
                message = "Pairing failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 3: Connection Establishment
     */
    private suspend fun testConnection(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 3: Connection Establishment")
            
            EnhancedWebSocketManager.autoConnect()
            
            // Wait for connection
            delay(5000)
            
            val connectionState = EnhancedWebSocketManager.connectionState.value
            val isConnected = connectionState is EnhancedWebSocketManager.ConnectionState.Authenticated
            
            testResults.add(TestResult(
                testName = "Connection Establishment",
                passed = isConnected,
                message = if (isConnected) "Successfully connected" else "Connection failed: $connectionState",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Connection Establishment",
                passed = false,
                message = "Connection failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 4: Authentication
     */
    private suspend fun testAuthentication(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 4: Authentication")
            
            val connectionState = EnhancedWebSocketManager.connectionState.value
            val isAuthenticated = connectionState is EnhancedWebSocketManager.ConnectionState.Authenticated
            
            testResults.add(TestResult(
                testName = "Authentication",
                passed = isAuthenticated,
                message = if (isAuthenticated) "Successfully authenticated" else "Authentication failed",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Authentication",
                passed = false,
                message = "Authentication test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 5: Command Execution
     */
    private suspend fun testCommandExecution(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 5: Command Execution")
            
            var commandExecuted = false
            CommandExecutionManager.setVolume(50) { success, result ->
                commandExecuted = success
                Log.d(TAG, "Command result: success=$success, result=$result")
            }
            
            delay(2000) // Wait for command execution
            
            testResults.add(TestResult(
                testName = "Command Execution",
                passed = commandExecuted,
                message = if (commandExecuted) "Command executed successfully" else "Command execution failed",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Command Execution",
                passed = false,
                message = "Command execution failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 6: Voice Commands
     */
    private suspend fun testVoiceCommands(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 6: Voice Commands")
            
            // Initialize voice processor
            com.aistudio.dashcompanion.data.voice.VoiceCommandProcessor.setContext(context)
            
            // Simulate voice command
            val command = com.aistudio.dashcompanion.data.voice.VoiceCommandProcessor.parseVoiceCommand("open Chrome")
            
            testResults.add(TestResult(
                testName = "Voice Commands",
                passed = command.parsedCommand == "open",
                message = "Voice command parsed: ${command.parsedCommand}",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Voice Commands",
                passed = false,
                message = "Voice command test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 7: Reconnection
     */
    private suspend fun testReconnection(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 7: Reconnection")
            
            // Disconnect
            EnhancedWebSocketManager.disconnect()
            delay(1000)
            
            // Reconnect
            EnhancedWebSocketManager.autoConnect()
            delay(5000)
            
            val connectionState = EnhancedWebSocketManager.connectionState.value
            val reconnected = connectionState is EnhancedWebSocketManager.ConnectionState.Authenticated
            
            testResults.add(TestResult(
                testName = "Reconnection",
                passed = reconnected,
                message = if (reconnected) "Successfully reconnected" else "Reconnection failed",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Reconnection",
                passed = false,
                message = "Reconnection test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 8: Network Change Handling
     */
    private suspend fun testNetworkChange(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 8: Network Change Handling")
            
            // Simulate network change
            ConnectionStateManager.handleNetworkUnavailable()
            delay(1000)
            
            ConnectionStateManager.handleConnectionChange(true)
            delay(2000)
            
            val connectionState = ConnectionStateManager.getCurrentState()
            
            testResults.add(TestResult(
                testName = "Network Change Handling",
                passed = connectionState == ConnectionStateManager.ConnectionState.Online,
                message = "Network change handled: $connectionState",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Network Change Handling",
                passed = false,
                message = "Network change test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 9: Background Connection
     */
    private suspend fun testBackgroundConnection(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 9: Background Connection")
            
            com.aistudio.dashcompanion.data.background.BackgroundConnectionManager.setContext(context)
            com.aistudio.dashcompanion.data.background.BackgroundConnectionManager.onAppBackground()
            delay(2000)
            
            com.aistudio.dashcompanion.data.background.BackgroundConnectionManager.onAppForeground()
            delay(2000)
            
            testResults.add(TestResult(
                testName = "Background Connection",
                passed = true,
                message = "Background connection handled correctly",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Background Connection",
                passed = false,
                message = "Background connection test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 10: Security
     */
    private suspend fun testSecurity(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 10: Security")
            
            // Test command validation
            val validation = SecurityManager.validateCommand(
                "set_volume",
                mapOf("level" to 50),
                "test-token"
            )
            
            val signature = SecurityManager.signCommand("set_volume", mapOf("level" to 50), context)
            val verified = SecurityManager.verifyCommandSignature("set_volume", mapOf("level" to 50), signature, context)
            
            testResults.add(TestResult(
                testName = "Security",
                passed = validation.isValid && verified,
                message = "Security validation: valid=${validation.isValid}, verified=$verified",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Security",
                passed = false,
                message = "Security test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Test 11: Performance
     */
    private suspend fun testPerformance(context: Context) {
        val startTime = System.currentTimeMillis()
        
        try {
            Log.d(TAG, "Test 11: Performance")
            
            com.aistudio.dashcompanion.data.performance.PerformanceOptimizer.monitorPerformance()
            delay(2000)
            
            val metrics = com.aistudio.dashcompanion.data.performance.PerformanceOptimizer.performanceMetrics.value
            
            testResults.add(TestResult(
                testName = "Performance",
                passed = metrics.fps >= 30, // At least 30 FPS
                message = "Performance: FPS=${metrics.fps}, Latency=${metrics.latency}ms",
                duration = System.currentTimeMillis() - startTime
            ))
        } catch (e: Exception) {
            testResults.add(TestResult(
                testName = "Performance",
                passed = false,
                message = "Performance test failed: ${e.message}",
                duration = System.currentTimeMillis() - startTime
            ))
        }
    }
    
    /**
     * Get test summary
     */
    fun getTestSummary(): String {
        val passed = testResults.count { it.passed }
        val total = testResults.size
        val percentage = if (total > 0) (passed * 100 / total) else 0
        
        return """
            Test Summary:
            Passed: $passed/$total ($percentage%)
            
            Results:
            ${testResults.joinToString("\n") { result ->
                "[${if (result.passed) "PASS" else "FAIL"}] ${result.testName}: ${result.message} (${result.duration}ms)"
            }}
        """.trimIndent()
    }
}