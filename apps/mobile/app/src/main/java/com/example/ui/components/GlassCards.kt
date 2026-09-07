package com.example.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.interaction.collectIsPressedAsState
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import com.valentinilk.shimmer.shimmer
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.StrokeCap
import com.example.ui.theme.*
import com.example.ui.theme.dashColors

// ═══════════════════════════════════════════════════════════════
// DASH Premium Glass Components
// ═══════════════════════════════════════════════════════════════

@Composable
fun GlassCard(
    modifier: Modifier = Modifier,
    cornerRadius: Dp = 16.dp,
    backgroundColor: Color = dashColors().surfaceContainer.copy(alpha = 0.6f),
    borderColor: Color = dashColors().borderGlass,
    glowColor: Color = Color.Transparent,
    onClick: (() -> Unit)? = null,
    content: @Composable ColumnScope.() -> Unit = {}
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.98f else 1f,
        animationSpec = spring(dampingRatio = 0.7f, stiffness = 300f),
        label = "scale"
    )
    val shape = RoundedCornerShape(cornerRadius)

    Column(
        modifier = modifier
            .graphicsLayer {
                scaleX = scale
                scaleY = scale
            }
            .shadow(
                elevation = if (glowColor != Color.Transparent) 12.dp else 4.dp,
                shape = shape,
                ambientColor = glowColor,
                spotColor = glowColor
            )
            .clip(shape)
            .background(backgroundColor)
            .then(
                if (borderColor != Color.Transparent) {
                    Modifier.border(1.dp, borderColor, shape)
                } else Modifier
            )
            .then(
                if (onClick != null) {
                    Modifier.clickable(
                        interactionSource = interactionSource,
                        indication = null,
                        onClick = {
                            hm.perform(HapticPattern.TAP)
                            onClick()
                        }
                    )
                } else Modifier
            )
            .padding(16.dp),
        content = content
    )
}

@Composable
fun SectionHeader(
    title: String,
    icon: String = "",
    accentColor: Color = DashCyanPrimary
) {
    Row(
        verticalAlignment = Alignment.CenterVertically,
        modifier = Modifier.padding(bottom = 8.dp)
    ) {
        if (icon.isNotEmpty()) {
            Text(
                text = icon,
                fontSize = 14.sp,
                modifier = Modifier.padding(end = 8.dp)
            )
        }
        Text(
            text = title,
            style = MaterialTheme.typography.labelSmall,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 2.sp,
            color = accentColor.copy(alpha = 0.8f)
        )
        Spacer(modifier = Modifier.width(8.dp))
        Box(
            modifier = Modifier
                .weight(1f)
                .height(1.dp)
                .background(
                    Brush.horizontalGradient(
                        colors = listOf(accentColor.copy(alpha = 0.4f), Color.Transparent)
                    )
                )
        )
    }
}

@Composable
fun StatusPill(
    label: String,
    value: String,
    color: Color = DashCyanPrimary,
    modifier: Modifier = Modifier
) {
    Box(
        modifier = modifier
            .clip(RoundedCornerShape(20.dp))
            .background(color.copy(alpha = 0.1f))
            .border(1.dp, color.copy(alpha = 0.3f), RoundedCornerShape(20.dp))
            .padding(horizontal = 10.dp, vertical = 4.dp)
    ) {
        Text(
            text = "$label: $value",
            fontSize = 10.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Medium,
            color = color
        )
    }
}

@Composable
fun MetricCard(
    label: String,
    value: String,
    icon: String = "",
    color: Color = DashCyanPrimary,
    modifier: Modifier = Modifier,
    loading: Boolean = false
) {
    GlassCard(
        modifier = modifier,
        cornerRadius = 12.dp,
        borderColor = color.copy(alpha = 0.2f),
        glowColor = color.copy(alpha = 0.1f)
    ) {
        if (loading) {
            // Shimmer skeleton placeholder
            Column(modifier = Modifier.shimmer()) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Box(
                        modifier = Modifier
                            .size(14.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color.White.copy(alpha = 0.08f))
                    )
                    Spacer(modifier = Modifier.width(6.dp))
                    Box(
                        modifier = Modifier
                            .height(10.dp)
                            .width(32.dp)
                            .clip(RoundedCornerShape(4.dp))
                            .background(Color.White.copy(alpha = 0.08f))
                    )
                }
                Spacer(modifier = Modifier.height(8.dp))
                Box(
                    modifier = Modifier
                        .height(24.dp)
                        .width(48.dp)
                        .clip(RoundedCornerShape(6.dp))
                        .background(Color.White.copy(alpha = 0.08f))
                )
            }
        } else {
            Column {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (icon.isNotEmpty()) {
                        Text(text = icon, fontSize = 14.sp, modifier = Modifier.padding(end = 6.dp))
                    }
                    Text(
                        text = label,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        letterSpacing = 1.sp,
                        color = dashColors().textMuted
                    )
                }
                Spacer(modifier = Modifier.height(4.dp))
                Text(
                    text = value,
                    fontSize = 22.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    color = color
                )
            }
        }
    }
}

@Composable
fun ActionButton(
    label: String,
    icon: String = "",
    color: Color = DashCyanPrimary,
    enabled: Boolean = true,
    onClick: () -> Unit
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val interactionSource = remember { MutableInteractionSource() }
    val isPressed by interactionSource.collectIsPressedAsState()
    val scale by animateFloatAsState(
        targetValue = if (isPressed) 0.95f else 1f,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = 400f),
        label = "btn_scale"
    )

    Box(
        modifier = Modifier
            .graphicsLayer { scaleX = scale; scaleY = scale }
            .clip(RoundedCornerShape(12.dp))
            .background(
                if (enabled) color.copy(alpha = 0.12f)
                else dashColors().surfaceContainer
            )
            .border(
                1.dp,
                if (enabled) color.copy(alpha = 0.3f) else DashBorderSubtle,
                RoundedCornerShape(12.dp)
            )
            .clickable(
                interactionSource = interactionSource,
                indication = null,
                enabled = enabled,
                onClick = {
                    hm.perform(HapticPattern.TAP)
                    onClick()
                }
            )
            .padding(horizontal = 16.dp, vertical = 10.dp),
        contentAlignment = Alignment.Center
    ) {
        Row(verticalAlignment = Alignment.CenterVertically) {
            if (icon.isNotEmpty()) {
                Text(text = icon, fontSize = 14.sp, modifier = Modifier.padding(end = 6.dp))
            }
            Text(
                text = label,
                fontSize = 12.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.SemiBold,
                color = if (enabled) color else DashTextDisabled
            )
        }
    }
}

@Composable
fun GlowDot(
    color: Color = DashCyanPrimary,
    size: Dp = 8.dp,
    pulsing: Boolean = true
) {
    val infiniteTransition = rememberInfiniteTransition(label = "glow_dot")
    val alpha by infiniteTransition.animateFloat(
        initialValue = 0.4f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1000, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "dot_alpha"
    )

    Box(
        modifier = Modifier
            .size(size)
            .graphicsLayer { this.alpha = if (pulsing) alpha else 1f }
    ) {
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(color, shape = androidx.compose.foundation.shape.CircleShape)
        )
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(
                    Brush.radialGradient(
                        colors = listOf(color.copy(alpha = 0.6f), Color.Transparent)
                    )
                )
        )
    }
}



@Composable
fun RadialGauge(
    value: Float,
    label: String,
    accentColor: Color = DashCyanPrimary,
    size: Dp = 80.dp
) {
    val animatedValue by animateFloatAsState(targetValue = value / 100f, animationSpec = tween(800), label = "gauge")
    Box(modifier = Modifier.size(size), contentAlignment = Alignment.Center) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val stroke = 6f
            val radius = (size.toPx() / 2f) - stroke
            // Background arc
            drawArc(
                color = accentColor.copy(alpha = 0.1f),
                startAngle = 135f, sweepAngle = 270f, useCenter = false,
                style = Stroke(stroke, cap = StrokeCap.Round)
            )
            // Value arc
            drawArc(
                color = accentColor,
                startAngle = 135f, sweepAngle = 270f * animatedValue, useCenter = false,
                style = Stroke(stroke, cap = StrokeCap.Round)
            )
        }
        Column(horizontalAlignment = Alignment.CenterHorizontally) {
            Text("${value.toInt()}%", fontSize = 12.sp, fontWeight = FontWeight.Bold, fontFamily = FontFamily.Monospace, color = accentColor)
            Text(label, fontSize = 7.sp, fontFamily = FontFamily.Monospace, color = dashColors().textMuted)
        }
    }
}

// ═══════════════════════════════════════════════════════════════
// Navigation Destinations
// ═══════════════════════════════════════════════════════════════

enum class NavDestination(val route: String, val label: String) {
    HOME("home", "Home"),
    CHAT("chat", "Chat"),
    VOICE("voice", "Voice"),
    AGENT("agent", "Agent"),
    ACTIVITY("activity", "Activity"),
    MORE("more", "More"),
}
