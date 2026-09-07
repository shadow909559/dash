package com.example.ui.screens.subscreens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.LightMode
import androidx.compose.material.icons.filled.PowerSettingsNew
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.RestartAlt
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.DashApiService
import com.example.ui.components.GlassCard
import com.example.ui.components.RadialGauge
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

@Composable
fun ComputerControlSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val systemMetrics by viewModel.systemMetrics.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    val haptic = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()
    var terminalInput by remember { mutableStateOf("") }
    val terminalHistory = remember {
        mutableStateListOf<String>(
            "[DASH Remote Terminal v1.0]",
            "Type a command below to execute on your PC."
        )
    }
    var windowsList by remember { mutableStateOf<List<String>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var isLoadingWindows by remember { mutableStateOf(false) }

    // Auto-load windows on screen entry
    androidx.compose.runtime.LaunchedEffect(Unit) {
        isLoadingWindows = true
        try {
            val response = DashApiService.listWindows()
            @Suppress("UNCHECKED_CAST")
            val windows = response.details["windows"] as? List<Map<String, Any>>
            windowsList = windows?.mapNotNull { it["title"] as? String ?: it["name"] as? String } ?: emptyList()
        } catch (_: Exception) {}
        isLoadingWindows = false
    }

    // Auto-load current volume on entry
    androidx.compose.runtime.LaunchedEffect(Unit) {
        try {
            val volResponse = DashApiService.getVolume()
            // Volume is available but we track it locally for UI state
        } catch (_: Exception) {}
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("computer_control_screen")
    ) {
        SubScreenHeader(
            title = "Computer Control",
            subtitle = "Hardware, terminal, power",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Hardware Telemetry
            item {
                GlassCard(modifier = Modifier.fillMaxWidth()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(14.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Text(
                                text = "REAL-TIME HARDWARE METRICS",
                                style = MaterialTheme.typography.labelSmall,
                                color = dashColors().textMuted,
                                letterSpacing = 1.2.sp
                            )
                            Text(
                                text = "Latency: ${systemMetrics.latencyMs}ms",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 11.sp,
                                color = DashSuccessGreen
                            )
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceAround
                        ) {
                            RadialGauge(value = systemMetrics.cpuUsage.toFloat(), label = "CPU", accentColor = DashCyanPrimary, size = 66.dp)
                            RadialGauge(value = systemMetrics.ramUsage.toFloat(), label = "RAM", accentColor = DashPurpleSecondary, size = 66.dp)
                            RadialGauge(value = systemMetrics.gpuUsage.toFloat(), label = "GPU", accentColor = DashCyanPrimary, size = 66.dp)
                            RadialGauge(value = systemMetrics.storageUsage.toFloat(), label = "Disk", accentColor = DashApprovalAmber, size = 66.dp)
                        }
                    }
                }
            }

            // Power Actions Row
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    PowerButton(
                        label = "Lock PC",
                        icon = Icons.Default.Lock,
                        accentColor = DashCyanPrimary,
                        modifier = Modifier.weight(1f)
                    ) {
                        terminalHistory.add("\u23f3 Locking workstation...")
                        scope.launch {
                            try {
                                DashApiService.lock()
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2714 Workstation locked.")
                                viewModel.refreshMetrics()
                            } catch (e: Exception) {
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2718 Lock failed: ${e.message}")
                            }
                        }
                    }
                    PowerButton(
                        label = "Sleep",
                        icon = Icons.Default.PowerSettingsNew,
                        accentColor = DashPurpleSecondary,
                        modifier = Modifier.weight(1f)
                    ) {
                        terminalHistory.add("\u23f3 Sending sleep signal...")
                        scope.launch {
                            try {
                                DashApiService.sleep()
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2714 Desktop sleeping.")
                            } catch (e: Exception) {
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2718 Sleep failed: ${e.message}")
                            }
                        }
                    }
                    PowerButton(
                        label = "Restart PC",
                        icon = Icons.Default.RestartAlt,
                        accentColor = DashApprovalAmber,
                        modifier = Modifier.weight(1f)
                    ) {
                        terminalHistory.add("\u26a0 Restarting PC in 10s...")
                        scope.launch {
                            try {
                                DashApiService.restart()
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2714 Restart initiated.")
                            } catch (e: Exception) {
                                terminalHistory.removeAt(terminalHistory.size - 1)
                                terminalHistory.add("\u2718 Restart failed: ${e.message}")
                            }
                        }
                    }
                }
            }

            // Volume Control
            item {
                VolumeControlCard(terminalHistory = terminalHistory)
            }

            // Brightness Control
            item {
                BrightnessControlCard(terminalHistory = terminalHistory)
            }

            // Interactive Remote Terminal
            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    backgroundColor = Color.Black.copy(alpha = 0.85f),
                    borderColor = DashCyanPrimary.copy(alpha = 0.3f)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Icon(
                                    imageVector = Icons.Default.Terminal,
                                    contentDescription = "Terminal",
                                    tint = DashCyanPrimary,
                                    modifier = Modifier.size(16.dp)
                                )
                                Spacer(modifier = Modifier.width(6.dp))
                                Text(
                                    text = "DASH REMOTE TERMINAL",
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = DashCyanPrimary
                                )
                            }
                            val connLabel = when (connectionState) {
                                com.example.data.websocket.WebSocketManager.ConnectionState.Authenticated -> "Connected \u25cf"
                                else -> "Disconnected \u25cb"
                            }
                            Text(
                                text = connLabel,
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp,
                                color = if (connectionState == com.example.data.websocket.WebSocketManager.ConnectionState.Authenticated) DashSuccessGreen else DashErrorRed
                            )
                        }

                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .clip(RoundedCornerShape(8.dp))
                                .background(dashColors().surfaceContainerLow)
                                .padding(12.dp),
                            verticalArrangement = Arrangement.spacedBy(4.dp)
                        ) {
                            terminalHistory.takeLast(12).forEach { line ->
                                Text(
                                    text = line,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 11.sp,
                                    color = when {
                                        line.startsWith("\u2714") -> DashSuccessGreen
                                        line.startsWith("\u2718") -> DashErrorRed
                                        line.startsWith("\u23f3") || line.startsWith("\u26a0") -> DashApprovalAmber
                                        line.startsWith("[") -> DashCyanPrimary
                                        else -> dashColors().textSecondary
                                    },
                                    lineHeight = 15.sp
                                )
                            }
                        }

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            OutlinedTextField(
                                value = terminalInput,
                                onValueChange = { terminalInput = it },
                                placeholder = {
                                    Text(
                                        text = "Enter command...",
                                        fontSize = 11.sp,
                                        fontFamily = FontFamily.Monospace,
                                        color = dashColors().textMuted
                                    )
                                },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                textStyle = MaterialTheme.typography.bodySmall.copy(
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 12.sp,
                                    color = DashCyanPrimary
                                ),
                                colors = OutlinedTextFieldDefaults.colors(
                                    focusedBorderColor = DashCyanPrimary,
                                    unfocusedBorderColor = dashColors().borderGlass,
                                    focusedContainerColor = dashColors().surfaceContainerLow,
                                    unfocusedContainerColor = dashColors().surfaceContainerLow
                                ),
                                singleLine = true,
                                keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                                keyboardActions = KeyboardActions(
                                    onSend = {
                                        if (terminalInput.isNotBlank()) {
                                            val cmd = terminalInput.trim()
                                            terminalHistory.add("$ ")
                                            terminalHistory.add("executing: $cmd")
                                            terminalInput = ""
                                            scope.launch {
                                                terminalHistory.add("[pending] $cmd...")
                                                try {
                                                    // Use chat to send command
                                                    viewModel.sendMessage("Execute this PC command: $cmd")
                                                    terminalHistory.removeAll { it == "[pending] $cmd..." }
                                                    terminalHistory.add("\u2714 Command sent: $cmd")
                                                } catch (e: Exception) {
                                                    terminalHistory.removeAll { it == "[pending] $cmd..." }
                                                    terminalHistory.add("\u2718 Failed: ${e.message}")
                                                }
                                            }
                                        }
                                    }
                                )
                            )

                            IconButton(
                                onClick = {
                                    hm.perform(HapticPattern.TAP)
                                    if (terminalInput.isNotBlank()) {
                                        val cmd = terminalInput.trim()
                                        terminalHistory.add("$ ")
                                        terminalHistory.add("executing: $cmd")
                                        terminalInput = ""
                                        scope.launch {
                                            terminalHistory.add("[pending] $cmd...")
                                            try {
                                                viewModel.sendMessage("Execute this PC command: $cmd")
                                                terminalHistory.removeAll { it == "[pending] $cmd..." }
                                                terminalHistory.add("\u2714 Command sent: $cmd")
                                            } catch (e: Exception) {
                                                terminalHistory.removeAll { it == "[pending] $cmd..." }
                                                terminalHistory.add("\u2718 Failed: ${e.message}")
                                            }
                                        }
                                    }
                                },
                                modifier = Modifier
                                    .size(40.dp)
                                    .clip(CircleShape)
                                    .background(DashCyanPrimary)
                            ) {
                                Icon(
                                    imageVector = Icons.AutoMirrored.Filled.Send,
                                    contentDescription = "Execute",
                                    tint = dashColors().surface,
                                    modifier = Modifier.size(18.dp)
                                )
                            }
                        }
                    }
                }
            }

            // Window List (real API call)
            item {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "RUNNING WINDOWS",
                            style = MaterialTheme.typography.labelSmall,
                            color = dashColors().textMuted,
                            letterSpacing = 1.2.sp
                        )
                        if (isLoadingWindows) {
                            Spacer(modifier = Modifier.width(8.dp))
                            androidx.compose.material3.CircularProgressIndicator(
                                modifier = Modifier.size(12.dp),
                                color = DashCyanPrimary,
                                strokeWidth = 1.5.dp
                            )
                        }
                    }
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(8.dp))
                            .background(DashCyanPrimary.copy(alpha = 0.1f))
                            .border(1.dp, DashCyanPrimary.copy(alpha = 0.25f), RoundedCornerShape(8.dp))
                            .clickable {
                                isLoadingWindows = true
                                scope.launch {
                                    try {
                                        val response = DashApiService.listWindows()
                                        @Suppress("UNCHECKED_CAST")
                                        val windows = response.details["windows"] as? List<Map<String, Any>>
                                        windowsList = windows?.mapNotNull { it["title"] as? String ?: it["name"] as? String } ?: emptyList()
                                    } catch (_: Exception) {}
                                    isLoadingWindows = false
                                }
                            }
                            .padding(horizontal = 10.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = "REFRESH",
                            style = MaterialTheme.typography.labelSmall,
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = DashCyanPrimary
                        )
                    }
                }
                Spacer(modifier = Modifier.height(6.dp))
            }

            // Real window list from backend
            if (windowsList.isNotEmpty()) {
                items(windowsList) { windowName ->
                    WindowRow(name = windowName, onFocus = {
                        scope.launch {
                            try { DashApiService.focusWindow(windowName) } catch (_: Exception) {}
                        }
                    }, onClose = {
                        scope.launch {
                            try { DashApiService.closeWindow(windowName) } catch (_: Exception) {}
                            windowsList = windowsList.filter { it != windowName }
                        }
                    })
                }
            } else if (!isLoadingWindows) {
                item {
                    GlassCard(
                        modifier = Modifier.fillMaxWidth(),
                        cornerRadius = 12.dp,
                        backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.5f)
                    ) {
                        Text(
                            text = "No windows detected. Tap Refresh.",
                            modifier = Modifier.padding(14.dp),
                            fontSize = 12.sp,
                            color = dashColors().textMuted
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun VolumeControlCard(terminalHistory: MutableList<String>) {
    val scope = rememberCoroutineScope()
    var volume by remember { mutableStateOf(50f) }
    var volumeLoaded by remember { mutableStateOf(false) }

    // Load actual volume on entry
    LaunchedEffect(Unit) {
        try {
            val vol = DashApiService.getVolume()
            volume = vol.volume.toFloat()
            volumeLoaded = true
        } catch (_: Exception) {}
    }
    var isMuted by remember { mutableStateOf(false) }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "SYSTEM VOLUME",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.2.sp
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "${volume.toInt()}%",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 14.sp,
                    color = DashCyanPrimary,
                    modifier = Modifier.width(40.dp)
                )
                androidx.compose.material3.Slider(
                    value = volume,
                    onValueChange = { volume = it },
                    onValueChangeFinished = {
                        scope.launch {
                            try {
                                DashApiService.setVolume(volume.toInt())
                                terminalHistory.add("\u2714 Volume: ${volume.toInt()}%")
                            } catch (e: Exception) {
                                terminalHistory.add("\u2718 Volume failed: ${e.message}")
                            }
                        }
                    },
                    valueRange = 0f..100f,
                    modifier = Modifier.weight(1f),
                    colors = androidx.compose.material3.SliderDefaults.colors(
                        thumbColor = DashCyanPrimary,
                        activeTrackColor = DashCyanPrimary
                    )
                )
                IconButton(
                    onClick = {
                        isMuted = !isMuted
                        scope.launch {
                            try { DashApiService.toggleMute(isMuted) } catch (_: Exception) {}
                        }
                    },
                    modifier = Modifier
                        .size(32.dp)
                        .clip(CircleShape)
                        .background(if (isMuted) DashErrorRed.copy(alpha = 0.2f) else Color.White.copy(alpha = 0.06f))
                ) {
                    Icon(
                        imageVector = if (isMuted) Icons.Default.Terminal else Icons.Default.Terminal,
                        contentDescription = if (isMuted) "Unmute" else "Mute",
                        tint = if (isMuted) DashErrorRed else dashColors().textMuted,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }
        }
    }
}

@Composable
private fun BrightnessControlCard(terminalHistory: MutableList<String>) {
    val scope = rememberCoroutineScope()
    var brightness by remember { mutableStateOf(50f) }
    var brightnessLoaded by remember { mutableStateOf(false) }

    // Load actual brightness on entry
    LaunchedEffect(Unit) {
        try {
            val br = DashApiService.getBrightness()
            brightness = br.brightness.toFloat()
            brightnessLoaded = true
        } catch (_: Exception) {}
    }

    GlassCard(modifier = Modifier.fillMaxWidth()) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            Text(
                text = "SCREEN BRIGHTNESS",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.2.sp
            )
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "☀",
                    fontSize = 16.sp,
                    color = DashApprovalAmber
                )
                Text(
                    text = "${brightness.toInt()}%",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 14.sp,
                    color = DashApprovalAmber,
                    modifier = Modifier.width(40.dp)
                )
                androidx.compose.material3.Slider(
                    value = brightness,
                    onValueChange = { brightness = it },
                    onValueChangeFinished = {
                        scope.launch {
                            try {
                                DashApiService.setBrightness(brightness.toInt())
                                terminalHistory.add("✔ Brightness: ${brightness.toInt()}%")
                            } catch (e: Exception) {
                                terminalHistory.add("✘ Brightness failed: ${e.message}")
                            }
                        }
                    },
                    valueRange = 0f..100f,
                    modifier = Modifier.weight(1f),
                    colors = androidx.compose.material3.SliderDefaults.colors(
                        thumbColor = DashApprovalAmber,
                        activeTrackColor = DashApprovalAmber
                    )
                )
            }
        }
    }
}

@Composable
private fun PowerButton(
    label: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    accentColor: Color,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    GlassCard(
        modifier = modifier,
        cornerRadius = 16.dp,
        onClick = { hm.perform(HapticPattern.DESTROY); onClick() }
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Icon(
                imageVector = icon,
                contentDescription = label,
                tint = accentColor,
                modifier = Modifier.size(20.dp)
            )
            Text(
                text = label,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                color = dashColors().textPrimary
            )
        }
    }
}

@Composable
private fun WindowRow(name: String, onFocus: () -> Unit, onClose: () -> Unit) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 12.dp,
        backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.5f)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 14.dp, vertical = 10.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Text(
                text = name,
                style = MaterialTheme.typography.titleSmall,
                color = dashColors().textPrimary,
                fontFamily = FontFamily.Monospace,
                fontSize = 12.sp,
                modifier = Modifier.weight(1f)
            )
            Row(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                IconButton(onClick = onFocus, modifier = Modifier.size(28.dp)) {
                    Text("\u25b6", fontSize = 10.sp, color = DashCyanPrimary)
                }
                IconButton(onClick = onClose, modifier = Modifier.size(28.dp)) {
                    Text("\u2716", fontSize = 10.sp, color = DashErrorRed)
                }
            }
        }
    }
}
