package com.example.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.theme.*
import com.example.data.websocket.WebSocketManager
import com.example.ui.theme.dashColors

@Composable
fun DashTopBar(
    isSafeMode: Boolean = false,
    isPcLinked: Boolean = true,
    onSearchClick: () -> Unit = {},
    onProfileClick: () -> Unit = {},
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val connectionState by WebSocketManager.connectionState.collectAsState()

    val infiniteTransition = rememberInfiniteTransition(label = "status")
    val pulseAlpha by infiniteTransition.animateFloat(
        initialValue = 0.5f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1500, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "pulse"
    )

    val statusColor = when (connectionState) {
        WebSocketManager.ConnectionState.Authenticated -> DashSuccessGreen
        WebSocketManager.ConnectionState.Connected -> DashCyanPrimary
        else -> DashErrorRed
    }
    val statusText = when (connectionState) {
        WebSocketManager.ConnectionState.Authenticated -> "ONLINE"
        WebSocketManager.ConnectionState.Connected -> "SYNCING"
        WebSocketManager.ConnectionState.Disconnected -> "OFFLINE"
        else -> "CONNECTING"
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(dashColors().background)
            .statusBarsPadding()
            .padding(horizontal = 16.dp, vertical = 8.dp)
    ) {
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(28.dp)
                        .clip(RoundedCornerShape(8.dp))
                        .background(Brush.linearGradient(listOf(DashPrimary, DashCyanPrimary))),
                    contentAlignment = Alignment.Center
                ) {
                    Text("D", fontSize = 14.sp, fontWeight = FontWeight.Black, fontFamily = FontFamily.Monospace, color = Color.White)
                }
                Spacer(modifier = Modifier.width(10.dp))
                Text(
                    text = "DASH",
                    fontSize = 16.sp,
                    fontWeight = FontWeight.ExtraBold,
                    fontFamily = FontFamily.Monospace,
                    letterSpacing = 3.sp,
                    color = dashColors().textPrimary
                )
            }

            Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(16.dp))
                        .background(statusColor.copy(alpha = 0.1f))
                        .border(1.dp, statusColor.copy(alpha = 0.3f), RoundedCornerShape(16.dp))
                        .padding(horizontal = 10.dp, vertical = 4.dp)
                ) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Box(modifier = Modifier.size(6.dp).graphicsLayer { alpha = pulseAlpha }) {
                            Box(modifier = Modifier.fillMaxSize().background(statusColor, CircleShape))
                        }
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(statusText, fontSize = 9.sp, fontFamily = FontFamily.Monospace, fontWeight = FontWeight.Bold, color = statusColor)
                    }
                }

                Icon(
                    Icons.Default.Search, contentDescription = "Search",
                    tint = dashColors().textSecondary, modifier = Modifier.size(20.dp)
                        .clickable { hm.perform(HapticPattern.TAP); onSearchClick() }
                )

                Icon(
                    Icons.Default.Person, contentDescription = "Profile",
                    tint = dashColors().textSecondary, modifier = Modifier.size(20.dp)
                        .clickable { hm.perform(HapticPattern.TAP); onProfileClick() }
                )
            }
        }
    }
}
