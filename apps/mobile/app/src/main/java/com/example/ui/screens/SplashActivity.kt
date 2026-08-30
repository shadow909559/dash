package com.example.ui.screens

import android.animation.ValueAnimator
import android.content.Intent
import android.os.Bundle
import android.view.animation.AccelerateDecelerateInterpolator
import android.view.animation.OvershootInterpolator
import androidx.activity.ComponentActivity
import androidx.activity.compose.setContent
import androidx.compose.animation.core.*
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.*
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.*
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.MainActivity
import com.example.ui.theme.*
import kotlinx.coroutines.delay
import kotlin.math.*
import kotlin.random.Random
import com.example.ui.theme.dashColors

class SplashActivity : ComponentActivity() {
    override fun onCreate(savedInstanceState: Bundle?) {
        super.onCreate(savedInstanceState)
        setContent {
            DashTheme {
                SplashScreen(onComplete = {
                    startActivity(Intent(this, MainActivity::class.java))
                    finish()
                })
            }
        }
    }
}

@Composable
private fun SplashScreen(onComplete: () -> Unit) {
    val haptic = LocalHapticFeedback.current
    var phase by remember { mutableIntStateOf(0) } // 0=boot, 1=logo, 2=ready

    // Boot sequence text
    val bootLines = listOf(
        "INITIALIZING DASH CORE...",
        "LOADING NEURAL INTERFACE...",
        "CONNECTING TO AI NETWORK...",
        "ESTABLISHING SECURE TUNNEL...",
        "LOADING SYSTEM MODULES...",
        "ACTIVATING VOICE ENGINE...",
        "SYNCING AGENT FLEET...",
        "ALL SYSTEMS ONLINE",
    )
    var currentLine by remember { mutableIntStateOf(0) }
    var displayedText by remember { mutableStateOf("") }

    // Animate logo scale
    val logoScale by animateFloatAsState(
        targetValue = if (phase >= 1) 1f else 0f,
        animationSpec = spring(dampingRatio = 0.6f, stiffness = 200f),
        label = "logo_scale"
    )

    // Glow pulse
    val infiniteTransition = rememberInfiniteTransition(label = "glow")
    val glowAlpha by infiniteTransition.animateFloat(
        initialValue = 0.3f, targetValue = 1f,
        animationSpec = infiniteRepeatable(tween(1800, easing = FastOutSlowInEasing), RepeatMode.Reverse),
        label = "glow"
    )

    // Rotation for orbiting particles
    val rotation by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(tween(12000, easing = LinearEasing), RepeatMode.Restart),
        label = "rotation"
    )

    // Boot text animation
    LaunchedEffect(Unit) {
        for (i in bootLines.indices) {
            currentLine = i
            // Typewriter effect
            for (j in 0..bootLines[i].length) {
                displayedText = bootLines[i].substring(0, j)
                delay(25)
            }
            delay(120)
        }
        phase = 1
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        delay(1800)
        phase = 2
        haptic.performHapticFeedback(HapticFeedbackType.LongPress)
        delay(400)
        onComplete()
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .background(dashColors().background),
        contentAlignment = Alignment.Center
    ) {
        // Matrix rain background
        MatrixRainBackground(rotation)

        // Orbital rings
        if (phase >= 1) {
            OrbitalRings(rotation, glowAlpha)
        }

        // Central content
        Column(
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.Center,
            modifier = Modifier.fillMaxSize()
        ) {
            // Logo hexagon
            Box(
                modifier = Modifier
                    .size((120 * logoScale).dp)
                    .graphicsLayer { alpha = logoScale },
                contentAlignment = Alignment.Center
            ) {
                Canvas(modifier = Modifier.fillMaxSize()) {
                    val cx = size.width / 2
                    val cy = size.height / 2
                    val radius = size.width / 2 * 0.8f

                    // Outer hexagon
                    drawHexagon(cx, cy, radius, DashCyanPrimary.copy(alpha = glowAlpha * 0.4f), 2f)
                    // Inner hexagon
                    drawHexagon(cx, cy, radius * 0.7f, DashPrimary.copy(alpha = glowAlpha * 0.6f), 1.5f)
                    // Core dot
                    drawCircle(DashCyanFixed.copy(alpha = glowAlpha), radius * 0.15f)
                    // Glow
                    drawCircle(
                        Brush.radialGradient(
                            colors = listOf(DashCyanPrimary.copy(alpha = 0.3f * glowAlpha), Color.Transparent),
                            center = Offset(cx, cy),
                            radius = radius
                        ),
                        radius = radius * 1.2f
                    )
                }
            }

            Spacer(modifier = Modifier.height(32.dp))

            // DASH text
            Text(
                text = "DASH",
                fontSize = (36 * logoScale).sp,
                fontWeight = FontWeight.Black,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 12.sp,
                color = dashColors().textPrimary,
                modifier = Modifier.graphicsLayer { alpha = logoScale }
            )

            Spacer(modifier = Modifier.height(4.dp))

            Text(
                text = "A I  O P E R A T I N G  S Y S T E M",
                fontSize = (10 * logoScale).sp,
                fontWeight = FontWeight.Light,
                fontFamily = FontFamily.Monospace,
                letterSpacing = 3.sp,
                color = DashCyanPrimary.copy(alpha = 0.7f),
                modifier = Modifier.graphicsLayer { alpha = logoScale }
            )

            Spacer(modifier = Modifier.height(48.dp))

            // Boot text console
            if (phase == 0) {
                Column(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 40.dp),
                    verticalArrangement = Arrangement.spacedBy(2.dp)
                ) {
                    // Show last few lines
                    val startLine = maxOf(0, currentLine - 2)
                    for (i in startLine..currentLine) {
                        val isCurrent = i == currentLine
                        val lineAlpha = if (isCurrent) 1f else 0.3f
                        Text(
                            text = "> $displayedText${if (isCurrent && displayedText.length < bootLines[i].length) "█" else ""}",
                            fontSize = 10.sp,
                            fontFamily = FontFamily.Monospace,
                            color = if (isCurrent) DashCyanPrimary.copy(alpha = lineAlpha)
                                    else dashColors().textMuted.copy(alpha = lineAlpha),
                        )
                    }
                }
            }

            if (phase >= 1) {
                // Progress bar
                val progress by animateFloatAsState(
                    targetValue = if (phase >= 2) 1f else 0.85f,
                    animationSpec = tween(600),
                    label = "progress"
                )
                Box(
                    modifier = Modifier
                        .width(200.dp)
                        .height(2.dp)
                        .graphicsLayer { alpha = logoScale }
                ) {
                    Box(
                        modifier = Modifier
                            .fillMaxHeight()
                            .fillMaxWidth(fraction = progress)
                            .background(
                                Brush.horizontalGradient(
                                    colors = listOf(DashPrimary, DashCyanPrimary)
                                )
                            )
                    )
                    Box(
                        modifier = Modifier
                            .fillMaxHeight()
                            .fillMaxWidth()
                            .background(DashBorderSubtle)
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                Text(
                    text = if (phase >= 2) "SYSTEMS ONLINE" else "LOADING...",
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Medium,
                    letterSpacing = 4.sp,
                    color = if (phase >= 2) DashSuccessGreen else DashCyanPrimary
                )
            }
        }
    }
}

@Composable
private fun MatrixRainBackground(rotation: Float) {
    val columnData = remember {
        val rng = Random(42)
        List(12) { i ->
            Triple(i, 0.3f + rng.nextFloat() * 0.7f, rng.nextFloat() * 100f)
        }
    }
    Canvas(modifier = Modifier.fillMaxSize().graphicsLayer { alpha = 0.12f }) {
        val colWidth = size.width / 12f
        columnData.forEach { (i, speed, phase) ->
            val x = colWidth * i + colWidth * 0.5f
            val yOffset = ((rotation * speed * 1.5f + phase) % (size.height * 1.5f)) - size.height * 0.3f
            for (j in 0..1) {
                val y = (yOffset + j * 50f) % size.height
                drawRect(
                    color = DashCyanPrimary.copy(alpha = (0.25f - j * 0.08f).coerceIn(0f, 1f)),
                    topLeft = Offset(x, y),
                    size = androidx.compose.ui.geometry.Size(1.5f, 6f)
                )
            }
        }
    }
}

@Composable
private fun OrbitalRings(rotation: Float, glowAlpha: Float) {
    Canvas(
        modifier = Modifier
            .fillMaxSize()
            .graphicsLayer { alpha = 0.4f }
    ) {
        val cx = size.width / 2
        val cy = size.height / 2

        // Outer ring
        rotate(rotation, Offset(cx, cy)) {
            drawCircle(
                color = DashCyanPrimary.copy(alpha = glowAlpha * 0.2f),
                radius = size.width * 0.35f,
                style = Stroke(width = 1f)
            )
        }

        // Inner ring (opposite direction)
        rotate(-rotation * 0.7f, Offset(cx, cy)) {
            drawCircle(
                color = DashPrimary.copy(alpha = glowAlpha * 0.3f),
                radius = size.width * 0.28f,
                style = Stroke(width = 1.5f)
            )
        }

        // Dot merged into outer ring rotation (no separate trig)
    }
}

private fun androidx.compose.ui.graphics.drawscope.DrawScope.drawHexagon(
    cx: Float, cy: Float, radius: Float, color: Color, strokeWidth: Float
) {
    val path = Path()
    for (i in 0..5) {
        val angle = Math.toRadians((60.0 * i - 30))
        val x = cx + (radius * cos(angle)).toFloat()
        val y = cy + (radius * sin(angle)).toFloat()
        if (i == 0) path.moveTo(x, y) else path.lineTo(x, y)
    }
    path.close()
    drawPath(path, color, style = Stroke(strokeWidth))
}
