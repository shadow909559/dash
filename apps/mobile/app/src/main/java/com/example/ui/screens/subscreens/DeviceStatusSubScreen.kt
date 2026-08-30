package com.example.ui.screens.subscreens

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.Error
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
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
fun DeviceStatusSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var isLoading by remember { mutableStateOf(true) }
    var hostname by remember { mutableStateOf("--") }
    var platform by remember { mutableStateOf("--") }
    var cpuPercent by remember { mutableStateOf(0) }
    var ramPercent by remember { mutableStateOf(0) }
    var diskPercent by remember { mutableStateOf(0) }
    var gpuPercent by remember { mutableStateOf(0) }
    var uptime by remember { mutableStateOf("--") }
    var pythonVersion by remember { mutableStateOf("--") }
    var ollamaStatus by remember { mutableStateOf("--") }
    var desktopConnected by remember { mutableStateOf(false) }
    var backendOk by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    // Animated scan line for header
    val infiniteTransition = rememberInfiniteTransition(label = "scan")
    val scanOffset by infiniteTransition.animateFloat(
        initialValue = 0f,
        targetValue = 1f,
        animationSpec = infiniteRepeatable(
            animation = tween(2400, easing = FastOutSlowInEasing),
            repeatMode = RepeatMode.Reverse
        ),
        label = "scan_line"
    )

    fun refresh() {
        scope.launch {
            isLoading = true
            error = null
            try {
                val health = DashApiService.getHealth()
                backendOk = health.status == "ok"
                val details = health.details
                hostname = details["hostname"] as? String ?: "--"
                pythonVersion = details["python_version"] as? String ?: "--"

                try {
                    val overview = DashApiService.getStatusOverview()
                    val sys = overview.details["system"] as? Map<String, Any>
                    val snapshot = sys?.get("snapshot") as? Map<String, Any>
                    cpuPercent = (snapshot?.get("cpu_percent") as? Number)?.toInt() ?: 0
                    ramPercent = (snapshot?.get("memory_percent") as? Number)?.toInt() ?: 0
                    diskPercent = (snapshot?.get("disk_percent") as? Number)?.toInt() ?: 0
                    hostname = (snapshot?.get("hostname") as? String) ?: hostname
                    platform = (snapshot?.get("platform") as? String) ?: "--"
                    uptime = (snapshot?.get("uptime") as? String) ?: "--"
                } catch (_: Exception) {}

                desktopConnected = backendOk
            } catch (e: Exception) {
                error = e.message ?: "Connection failed"
                backendOk = false
                desktopConnected = false
            }
            isLoading = false
        }
    }

    LaunchedEffect(Unit) { refresh() }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("device_status_screen")
    ) {
        SubScreenHeader(
            title = "Device Status",
            subtitle = "Real-time system health",
            subtitleColor = DashSuccessGreen,
            onBack = onBack
        )

        if (isLoading) {
            Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    CircularProgressIndicator(color = DashCyanPrimary, modifier = Modifier.size(48.dp))
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Querying device telemetry...", color = dashColors().textSecondary)
                }
            }
        } else if (error != null) {
            Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(Icons.Default.Error, null, tint = DashErrorRed, modifier = Modifier.size(48.dp))
                    Spacer(modifier = Modifier.height(12.dp))
                    Text("Connection Failed", color = DashErrorRed, fontWeight = FontWeight.Bold)
                    Spacer(modifier = Modifier.height(4.dp))
                    Text(error ?: "", color = dashColors().textSecondary)
                    Spacer(modifier = Modifier.height(16.dp))
                    IconButton(onClick = { refresh() }, modifier = Modifier.size(48.dp).clip(CircleShape).background(DashCyanPrimary.copy(alpha = 0.15f))) {
                        Icon(Icons.Default.Refresh, "Retry", tint = DashCyanPrimary)
                    }
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(top = 16.dp, bottom = 100.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Connection Status
                item {
                    ConnectionStatusCard(
                        backendOk = backendOk,
                        desktopConnected = desktopConnected,
                        hostname = hostname,
                        platform = platform,
                        pythonVersion = pythonVersion
                    )
                }

                // Hardware Telemetry with RadialGauges (premium, matching HomeScreen)
                item {
                    GlassCard(
                        modifier = Modifier.fillMaxWidth(),
                        cornerRadius = 24.dp,
                        backgroundColor = dashColors().surfaceContainerLow,
                        borderColor = dashColors().borderGlass
                    ) {
                        Column(
                            modifier = Modifier.fillMaxWidth().padding(18.dp),
                            verticalArrangement = Arrangement.spacedBy(14.dp)
                        ) {
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceBetween,
                                verticalAlignment = Alignment.CenterVertically
                            ) {
                                Text(
                                    text = "REAL-TIME HARDWARE METRICS",
                                    fontSize = 10.sp,
                                    color = dashColors().textMuted,
                                    letterSpacing = 1.2.sp
                                )
                                Box(
                                    modifier = Modifier
                                        .clip(RoundedCornerShape(8.dp))
                                        .background(DashCyanPrimary.copy(alpha = 0.1f))
                                        .padding(horizontal = 10.dp, vertical = 4.dp)
                                ) {
                                    Text(
                                        text = "LIVE",
                                        fontFamily = FontFamily.Monospace,
                                        fontSize = 10.sp,
                                        fontWeight = FontWeight.Bold,
                                        color = DashCyanPrimary
                                    )
                                }
                            }

                            // Radial Gauges row (premium, matching HomeScreen style)
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = Arrangement.SpaceAround
                            ) {
                                RadialGauge(value = cpuPercent.toFloat(), label = "CPU", accentColor = DashCyanPrimary, size = 76.dp)
                                RadialGauge(value = ramPercent.toFloat(), label = "RAM", accentColor = DashPurpleSecondary, size = 76.dp)
                                RadialGauge(value = gpuPercent.toFloat(), label = "GPU", accentColor = DashCyanPrimary, size = 76.dp)
                                RadialGauge(value = diskPercent.toFloat(), label = "Disk", accentColor = DashApprovalAmber, size = 76.dp)
                            }
                        }
                    }
                }

                // System info
                item {
                    GlassCard(modifier = Modifier.fillMaxWidth(), cornerRadius = 16.dp) {
                        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                            Text("SYSTEM INFORMATION", fontSize = 11.sp, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                            InfoRow("Hostname", hostname)
                            InfoRow("Platform", platform)
                            InfoRow("Uptime", uptime)
                            InfoRow("Python", pythonVersion)
                            InfoRow("Ollama", ollamaStatus.ifBlank { "Available" })
                        }
                    }
                }

                // Quick Actions
                item {
                    Text(
                        text = "QUICK ACTIONS",
                        fontSize = 10.sp,
                        color = dashColors().textMuted,
                        letterSpacing = 1.5.sp
                    )
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        modifier = Modifier.fillMaxWidth(),
                        horizontalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        QuickActionPill("Refresh", DashCyanPrimary, Modifier.weight(1f)) { refresh() }
                        QuickActionPill("Sensors", DashPurpleSecondary, Modifier.weight(1f)) { refresh() }
                        QuickActionPill("Processes", DashSuccessGreen, Modifier.weight(1f)) { refresh() }
                    }
                }
            }
        }
    }
}

@Composable
private fun ConnectionStatusCard(backendOk: Boolean, desktopConnected: Boolean, hostname: String, platform: String, pythonVersion: String) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp,
        backgroundColor = if (backendOk) DashSuccessGreen.copy(alpha = 0.06f) else DashErrorRed.copy(alpha = 0.06f),
        borderColor = if (backendOk) DashSuccessGreen.copy(alpha = 0.25f) else DashErrorRed.copy(alpha = 0.25f)
    ) {
        Column(modifier = Modifier.fillMaxWidth().padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("CONNECTION STATUS", fontSize = 11.sp, color = dashColors().textMuted, letterSpacing = 1.2.sp)
            StatusRow("Backend API", backendOk)
            StatusRow("Desktop Agent", desktopConnected)
            StatusRow("Device Paired", desktopConnected)
        }
    }
}

@Composable
private fun StatusRow(label: String, connected: Boolean) {
    Row(modifier = Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.SpaceBetween) {
        Text(label, style = MaterialTheme.typography.bodyMedium, color = dashColors().textPrimary)
        Row(verticalAlignment = Alignment.CenterVertically) {
            Icon(
                imageVector = if (connected) Icons.Default.CheckCircle else Icons.Default.Warning,
                contentDescription = null,
                tint = if (connected) DashSuccessGreen else DashErrorRed,
                modifier = Modifier.size(16.dp)
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = if (connected) "CONNECTED" else "OFFLINE",
                fontSize = 11.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold,
                color = if (connected) DashSuccessGreen else DashErrorRed
            )
        }
    }
}

@Composable
private fun QuickActionPill(label: String, color: Color, modifier: Modifier = Modifier, onClick: () -> Unit) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(color.copy(alpha = 0.1f))
            .border(1.dp, color.copy(alpha = 0.25f), RoundedCornerShape(12.dp))
            .padding(vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Text(
            text = label,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = color,
            fontFamily = FontFamily.Monospace
        )
    }
}

@Composable
private fun InfoRow(label: String, value: String) {
    Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.SpaceBetween, verticalAlignment = Alignment.CenterVertically) {
        Text(label, style = MaterialTheme.typography.bodySmall, color = dashColors().textSecondary)
        Text(value, fontSize = 12.sp, fontFamily = FontFamily.Monospace, color = DashCyanPrimary, maxLines = 1)
    }
}
