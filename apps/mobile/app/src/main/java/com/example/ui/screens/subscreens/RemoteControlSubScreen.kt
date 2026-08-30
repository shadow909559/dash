package com.example.ui.screens.subscreens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.DashApiService
import com.example.data.config.AppConfig
import com.example.data.connection.AutoConnectManager
import com.example.data.websocket.WebSocketManager
import com.example.ui.components.GlassCard
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.*
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

/**
 * Full remote control screen — power, WoL, Ollama, auto-connect.
 * Allows complete autonomous control of the desktop from the phone.
 */
@Composable
fun RemoteControlSubScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val context = LocalContext.current
    val scope = rememberCoroutineScope()
    val connectionState by WebSocketManager.connectionState.collectAsState()
    val autoConnectRunning by AutoConnectManager.isRunning.collectAsState()
    val autoConnectStatus by AutoConnectManager.lastStatus.collectAsState()
    val wolMac by AutoConnectManager.wolMacAddress.collectAsState()

    var serverIp by remember { mutableStateOf(AppConfig.SERVER_IP) }
    var macInput by remember { mutableStateOf(wolMac ?: "") }
    var isStarting by remember { mutableStateOf(false) }
    var startMessage by remember { mutableStateOf<String?>(null) }
    var startSuccess by remember { mutableStateOf(false) }
    var systemStatus by remember { mutableStateOf<com.example.data.api.RemoteSystemStatusResponse?>(null) }
    var isLoadingStatus by remember { mutableStateOf(false) }

    val isConnected = connectionState == WebSocketManager.ConnectionState.Authenticated

    // Load status on entry
    LaunchedEffect(Unit) {
        isLoadingStatus = true
        try {
            systemStatus = DashApiService.getRemoteSystemStatus()
        } catch (_: Exception) {}
        isLoadingStatus = false
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
    ) {
        SubScreenHeader(
            title = "Remote Control",
            subtitle = "Power & system controls",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(14.dp)
        ) {
            // ─── Auto-Connect & WoL ───
            item {
                GlassCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
                        Text("AUTO-CONNECT & WAKE", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)

                        // Auto-connect toggle
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                            Column(Modifier.weight(1f)) {
                                Text("Auto-Connect", fontSize = 14.sp, fontWeight = FontWeight.SemiBold, color = dashColors().textPrimary)
                                Text(autoConnectStatus, fontSize = 11.sp, color = dashColors().textMuted, fontFamily = FontFamily.Monospace)
                            }
                            Switch(
                                checked = autoConnectRunning,
                                onCheckedChange = { enabled ->
                                    if (enabled) AutoConnectManager.start(context) else AutoConnectManager.stop()
                                },
                                colors = SwitchDefaults.colors(checkedThumbColor = DashCyanPrimary, checkedTrackColor = DashCyanPrimary.copy(alpha = 0.3f))
                            )
                        }

                        HorizontalDivider(color = dashColors().borderGlass, thickness = 0.5.dp)

                        // WoL MAC input
                        Text("Wake-on-LAN MAC Address", fontSize = 12.sp, color = dashColors().textSecondary)
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            OutlinedTextField(
                                value = macInput,
                                onValueChange = { macInput = it },
                                placeholder = { Text("AA:BB:CC:DD:EE:FF", color = dashColors().textMuted, fontSize = 12.sp) },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace, color = DashCyanPrimary),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                                    focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                                ),
                                singleLine = true
                            )
                            Button(
                                onClick = {
                                    AutoConnectManager.setWolMac(context, macInput.ifBlank { null })
                                    scope.launch {
                                        startMessage = "Saving..."
                                        startSuccess = true
                                        kotlinx.coroutines.delay(1500)
                                        startMessage = null
                                    }
                                },
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = DashPurpleSecondary)
                            ) {
                                Text("Save", color = dashColors().surface, fontWeight = FontWeight.Bold, fontSize = 12.sp)
                            }
                        }

                        // Manual WoL button
                        Button(
                            onClick = {
                                scope.launch {
                                    val mac = macInput.ifBlank { wolMac } ?: return@launch
                                    startMessage = "Sending WoL..."
                                    startSuccess = false
                                    try {
                                        val result = DashApiService.wakeOnLan(mac)
                                        startMessage = result.summary
                                        startSuccess = true
                                    } catch (e: Exception) {
                                        startMessage = "WoL failed: ${e.message}"
                                        startSuccess = false
                                    }
                                }
                            },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(12.dp),
                            colors = ButtonDefaults.buttonColors(containerColor = DashCyanPrimary)
                        ) {
                            Icon(Icons.Default.Power, null, Modifier.size(16.dp), tint = dashColors().surface)
                            Spacer(Modifier.width(8.dp))
                            Text("Wake PC Now", color = dashColors().surface, fontWeight = FontWeight.Bold)
                        }

                        if (startMessage != null) {
                            Box(Modifier.fillMaxWidth().clip(RoundedCornerShape(8.dp)).background(if (startSuccess) DashSuccessGreen.copy(alpha = 0.1f) else DashErrorRed.copy(alpha = 0.1f)).padding(10.dp)) {
                                Text(startMessage!!, fontFamily = FontFamily.Monospace, fontSize = 11.sp, color = if (startSuccess) DashSuccessGreen else DashErrorRed)
                            }
                        }
                    }
                }
            }

            // ─── Service Status ───
            item {
                GlassCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
                            Text("SERVICE STATUS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                            if (isLoadingStatus) {
                                CircularProgressIndicator(Modifier.size(14.dp), color = DashCyanPrimary, strokeWidth = 1.5.dp)
                            }
                        }

                        if (systemStatus != null) {
                            ServiceRow("Backend", systemStatus!!.backend.running, systemStatus!!.backend.detail)
                            ServiceRow("Ollama", systemStatus!!.ollama.running, systemStatus!!.ollama.detail)
                            ServiceRow("Qwen Model", systemStatus!!.qwen.running, systemStatus!!.qwen.detail)
                            ServiceRow("Desktop App", systemStatus!!.desktop.running, systemStatus!!.desktop.detail)
                        } else {
                            Text("Tap refresh to check status", fontSize = 12.sp, color = dashColors().textMuted)
                        }
                    }
                }
            }

            // ─── Start Services ───
            item {
                GlassCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("START SERVICES", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)

                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(10.dp)) {
                            ServiceButton("Start Ollama", Icons.Default.PlayArrow, DashSuccessGreen, Modifier.weight(1f), isStarting) {
                                scope.launch { startService("ollama", context, { isStarting = it }, { startMessage = it }, { startSuccess = it }) }
                            }
                            ServiceButton("Start Backend", Icons.Default.PlayArrow, DashCyanPrimary, Modifier.weight(1f), isStarting) {
                                scope.launch { startService("backend", context, { isStarting = it }, { startMessage = it }, { startSuccess = it }) }
                            }
                            ServiceButton("Start All", Icons.Default.PlayArrow, DashPurpleSecondary, Modifier.weight(1f), isStarting) {
                                scope.launch { startService("all", context, { isStarting = it }, { startMessage = it }, { startSuccess = it }) }
                            }
                        }
                    }
                }
            }

            // ─── Power Controls ───
            item {
                GlassCard(Modifier.fillMaxWidth()) {
                    Column(Modifier.fillMaxWidth().padding(18.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                        Text("POWER CONTROLS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)

                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            PowerControlButton("Lock", Icons.Default.Lock, DashCyanPrimary, Modifier.weight(1f)) {
                                scope.launch {
                                    try { DashApiService.lock(); startMessage = "Locked!" } catch (e: Exception) { startMessage = "Failed: ${e.message}" }
                                }
                            }
                            PowerControlButton("Sleep", Icons.Default.PowerSettingsNew, DashPurpleSecondary, Modifier.weight(1f)) {
                                scope.launch {
                                    try { DashApiService.sleep(); startMessage = "Sleeping..." } catch (e: Exception) { startMessage = "Failed: ${e.message}" }
                                }
                            }
                            PowerControlButton("Restart", Icons.Default.RestartAlt, DashApprovalAmber, Modifier.weight(1f)) {
                                scope.launch {
                                    try { DashApiService.restart(); startMessage = "Restarting..." } catch (e: Exception) { startMessage = "Failed: ${e.message}" }
                                }
                            }
                            PowerControlButton("Shutdown", Icons.Default.Power, DashErrorRed, Modifier.weight(1f)) {
                                scope.launch {
                                    try { DashApiService.shutdown(); startMessage = "Shutting down..." } catch (e: Exception) { startMessage = "Failed: ${e.message}" }
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun ServiceRow(name: String, running: Boolean, detail: String) {
    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Box(Modifier.size(8.dp).clip(CircleShape).background(if (running) DashSuccessGreen else DashErrorRed))
            Spacer(Modifier.width(8.dp))
            Text(name, fontSize = 13.sp, color = dashColors().textPrimary)
        }
        Column(horizontalAlignment = Alignment.End) {
            Text(if (running) "Online" else "Offline", fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = if (running) DashSuccessGreen else DashErrorRed)
            if (detail.isNotBlank()) Text(detail, fontSize = 9.sp, color = dashColors().textMuted)
        }
    }
}

@Composable
private fun ServiceButton(label: String, icon: ImageVector, color: Color, modifier: Modifier, isLoading: Boolean, onClick: () -> Unit) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    GlassCard(modifier = modifier, cornerRadius = 12.dp, onClick = { if (!isLoading) { hm.perform(HapticPattern.TAP); onClick() } }) {
        Column(Modifier.fillMaxWidth().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Icon(icon, label, Modifier.size(18.dp), tint = color)
            Text(label, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = dashColors().textPrimary)
        }
    }
}

@Composable
private fun PowerControlButton(label: String, icon: ImageVector, color: Color, modifier: Modifier, onClick: () -> Unit) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    GlassCard(modifier = modifier, cornerRadius = 14.dp, onClick = { hm.perform(HapticPattern.DESTROY); onClick() }) {
        Column(Modifier.fillMaxWidth().padding(12.dp), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(4.dp)) {
            Icon(icon, label, Modifier.size(18.dp), tint = color)
            Text(label, fontSize = 10.sp, fontWeight = FontWeight.SemiBold, color = dashColors().textPrimary)
        }
    }
}

private suspend fun startService(
    service: String,
    context: android.content.Context,
    setLoading: (Boolean) -> Unit,
    setMessage: (String) -> Unit,
    setSuccess: (Boolean) -> Unit
) {
    setLoading(true)
    setMessage("Starting $service...")
    setSuccess(false)
    try {
        val result = DashApiService.startService(com.example.data.api.RemoteStartRequest(service = service))
        setMessage(result.message.ifBlank { "Done" })
        setSuccess(result.success)
    } catch (e: Exception) {
        setMessage("Failed: ${e.message}")
        setSuccess(false)
    }
    setLoading(false)
}
