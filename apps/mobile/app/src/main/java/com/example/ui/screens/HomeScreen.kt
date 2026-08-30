package com.example.ui.screens

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material3.Icon
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.components.*
import com.example.ui.theme.*
import com.example.ui.viewmodel.DashViewModel
import com.example.data.model.OrbState
import com.example.ui.theme.dashColors


@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HomeScreen(
    viewModel: DashViewModel,
    onNavigate: (String) -> Unit = {},
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val orbState by viewModel.orbState.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()
    val scope = rememberCoroutineScope()
    var isRefreshing by remember { mutableStateOf(false) }
    val metrics by viewModel.systemMetrics.collectAsState()

    // Ambient glow animation
    val infiniteTransition = rememberInfiniteTransition(label = "ambient")
    val glowIntensity by infiniteTransition.animateFloat(
        initialValue = 0.03f, targetValue = 0.08f,
        animationSpec = infiniteRepeatable(tween(3000, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "glow"
    )

    Box(modifier = modifier.fillMaxSize()) {
    // Refresh handler
    LaunchedEffect(isRefreshing) {
        if (isRefreshing) {
            viewModel.refreshMetrics()
            kotlinx.coroutines.delay(1500)
            isRefreshing = false
        }
    }

    PullToRefreshBox(
        isRefreshing = isRefreshing,
        onRefresh = {
            hm.perform(HapticPattern.CONFIRM)
            isRefreshing = true
        },
        modifier = Modifier.fillMaxSize()
    ) {
    LazyColumn(
        modifier = Modifier
            .fillMaxSize()
            .background(dashColors().background),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        // ── Hero Orb Section ──
        item {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .height(240.dp),
                contentAlignment = Alignment.Center
            ) {
                // Background glow
                Box(
                    modifier = Modifier
                        .size(300.dp)
                        .background(
                            Brush.radialGradient(
                                colors = listOf(
                                    DashCyanPrimary.copy(alpha = glowIntensity),
                                    DashPrimary.copy(alpha = glowIntensity * 0.5f),
                                    Color.Transparent
                                )
                            )
                        )
                )
                // Orb
                DashOrb(
                    state = orbState,
                    size = 120.dp,
                    interactive = true,
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        onNavigate("voice")
                    }
                )

                // Refresh button — top right
                if (!isRefreshing) {
                    Box(
                        modifier = Modifier
                            .align(Alignment.TopEnd)
                            .padding(top = 20.dp, end = 20.dp)
                            .size(36.dp)
                            .clip(CircleShape)
                            .background(Color.White.copy(alpha = 0.06f))
                            .border(1.dp, Color.White.copy(alpha = 0.08f), CircleShape)
                            .clickable {
                                hm.perform(HapticPattern.CONFIRM)
                                isRefreshing = true
                            },
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = Icons.Default.Refresh,
                            contentDescription = "Refresh metrics",
                            tint = dashColors().textMuted,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }

        // ── System Metrics ──
        item {
            SectionHeader(title = "SYSTEM", icon = "⚡", accentColor = DashCyanPrimary)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                MetricCard(
                    label = "CPU",
                    value = "${metrics.cpuUsage.toFloat().toInt()}%",
                    icon = "🔥",
                    color = if (metrics.cpuUsage.toFloat() > 80) DashErrorRed else DashCyanPrimary,
                    modifier = Modifier.weight(1f),
                    loading = isRefreshing
                )
                MetricCard(
                    label = "RAM",
                    value = "${metrics.ramUsage.toFloat().toInt()}%",
                    icon = "💾",
                    color = if (metrics.ramUsage.toFloat() > 85) DashWarningAmber else DashCyanPrimary,
                    modifier = Modifier.weight(1f),
                    loading = isRefreshing
                )
                MetricCard(
                    label = "DISK",
                    value = "${metrics.storageUsage.toFloat().toInt()}%",
                    icon = "💿",
                    color = if (metrics.storageUsage.toFloat() > 90) DashErrorRed else DashCyanPrimary,
                    modifier = Modifier.weight(1f),
                    loading = isRefreshing
                )
            }
        }

        item { Spacer(modifier = Modifier.height(16.dp)) }

        // ── Quick Actions ──
        item {
            SectionHeader(title = "QUICK ACTIONS", icon = "🚀", accentColor = DashPurplePrimary)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                QuickActionCard("Chat", "💬", "Talk to AI", DashCyanPrimary, Modifier.weight(1f)) {
                    onNavigate("chat")
                }
                QuickActionCard("Voice", "🎙️", "Voice Control", DashPurplePrimary, Modifier.weight(1f)) {
                    onNavigate("voice")
                }
                QuickActionCard("Control", "🖥️", "Remote PC", DashPrimary, Modifier.weight(1f)) {
                    onNavigate("computer_control")
                }
            }
        }

        item { Spacer(modifier = Modifier.height(16.dp)) }

        // ── Feature Grid ──
        item {
            SectionHeader(title = "FEATURES", icon = "🧩", accentColor = DashCyanPrimary)
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FeatureCard("Files", "📁", Modifier.weight(1f)) { onNavigate("file_browser") }
                FeatureCard("Memory", "🧠", Modifier.weight(1f)) { onNavigate("memory") }
                FeatureCard("Browser", "🌐", Modifier.weight(1f)) { onNavigate("app_launcher") }
            }
            Spacer(modifier = Modifier.height(8.dp))
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                FeatureCard("Agents", "🤖", Modifier.weight(1f)) { onNavigate("ai_providers") }
                FeatureCard("Projects", "📂", Modifier.weight(1f)) { onNavigate("projects") }
                FeatureCard("Planner", "📋", Modifier.weight(1f)) { onNavigate("planner") }
            }
        }

        item { Spacer(modifier = Modifier.height(16.dp)) }

        // ── AI Status ──
        item {
            SectionHeader(title = "AI ENGINE", icon = "🧠", accentColor = DashSuccessGreen)
            GlassCard(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp),
                borderColor = DashSuccessGreen.copy(alpha = 0.2f)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        GlowDot(color = DashSuccessGreen, size = 10.dp)
                        Spacer(modifier = Modifier.width(10.dp))
                        Column {
                            Text(
                                text = "Ollama LLM",
                                fontSize = 13.sp,
                                fontWeight = FontWeight.SemiBold,
                                fontFamily = FontFamily.Monospace,
                                color = dashColors().textPrimary
                            )
                            Text(
                                text = "llama3.2:1b • Ready",
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                color = dashColors().textMuted
                            )
                        }
                    }
                    StatusPill(label = "STATUS", value = "READY", color = DashSuccessGreen)
                }
            }
        }

        item { Spacer(modifier = Modifier.height(8.dp)) }
    }
    } // PullToRefreshBox
    }
}

@Composable
private fun QuickActionCard(
    label: String, icon: String, subtitle: String, color: Color,
    modifier: Modifier = Modifier, onClick: () -> Unit
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    GlassCard(
        modifier = modifier,
        cornerRadius = 14.dp,
        borderColor = color.copy(alpha = 0.2f),
        glowColor = color.copy(alpha = 0.05f),
        onClick = {
            hm.perform(HapticPattern.TAP)
            onClick()
        }
    ) {
        Column(
            modifier = Modifier.fillMaxWidth(),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            Text(text = icon, fontSize = 24.sp)
            Text(
                text = label,
                fontSize = 12.sp,
                fontWeight = FontWeight.Bold,
                fontFamily = FontFamily.Monospace,
                color = dashColors().textPrimary
            )
            Text(
                text = subtitle,
                fontSize = 9.sp,
                fontFamily = FontFamily.Monospace,
                color = dashColors().textMuted
            )
        }
    }
}

@Composable
private fun FeatureCard(
    label: String, icon: String, modifier: Modifier = Modifier, onClick: () -> Unit
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(12.dp))
            .background(dashColors().surfaceContainer.copy(alpha = 0.5f))
            .border(1.dp, dashColors().borderGlass, RoundedCornerShape(12.dp))
            .clickable(
                interactionSource = remember { androidx.compose.foundation.interaction.MutableInteractionSource() },
                indication = null,
                onClick = {
                    hm.perform(HapticPattern.TAP)
                    onClick()
                }
            )
            .padding(12.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            Text(text = icon, fontSize = 16.sp)
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = label,
                fontSize = 11.sp,
                fontWeight = FontWeight.SemiBold,
                fontFamily = FontFamily.Monospace,
                color = dashColors().textPrimary
            )
        }
    }
}
