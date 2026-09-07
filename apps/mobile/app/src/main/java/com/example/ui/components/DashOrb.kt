package com.example.ui.components

import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashCyanDim
import com.example.ui.theme.DashCyanFixed
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.dashColors
import com.example.ui.theme.DashErrorRedContainer
import com.example.ui.theme.DashPrimaryContainer
import com.example.ui.theme.DashPurpleContainer
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurfaceContainer
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTertiary
import com.example.ui.theme.DashTertiaryDim
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashCyanLight
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.size
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.CornerRadius
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.geometry.Size
import androidx.compose.ui.graphics.BlendMode
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.PathEffect
import androidx.compose.ui.graphics.StrokeCap
import androidx.compose.ui.graphics.drawscope.DrawScope
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.graphics.drawscope.rotate
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.unit.Dp
import androidx.compose.ui.unit.dp
import com.example.data.model.OrbState
import kotlin.math.cos
import kotlin.math.sin

/**
 * Cinematic DASH Orb — Marvel-level arc reactor energy core.
 *
 * 7 visual layers:
 *  1. Deep atmospheric glow (radial gradient, state-colored)
 *  2. Outer energy field ring (dashed, rotating)
 *  3. Expanding ripple rings (breathing, state-reactive)
 *  4. Rotating orbital bands (3 rings at different angles/speeds)
 *  5. Inner shell (dark sphere with subtle border)
 *  6. Core gradient sphere (bright, with specular highlight)
 *  7. Particle system (state-dependent spawn rate, upward drift)
 */
@Composable
fun DashOrb(
    state: OrbState,
    modifier: Modifier = Modifier,
    size: Dp = 220.dp,
    interactive: Boolean = true,
    onClick: (() -> Unit)? = null,
    audioAmplitude: Float = 0f  // 0..1 for TTS-driven speaking animation
) {
    val hm = LocalHapticManager.current
    val infiniteTransition = rememberInfiniteTransition(label = "orb")

    // Breathing scale
    val breathScale by infiniteTransition.animateFloat(
        initialValue = 0.97f,
        targetValue = 1.03f,
        animationSpec = infiniteRepeatable(
            animation = tween(
                durationMillis = (3000 / state.pulseSpeedMultiplier).toInt().coerceAtLeast(600),
                easing = FastOutSlowInEasing
            ),
            repeatMode = RepeatMode.Reverse
        ),
        label = "breath"
    )

    // Ring rotations (3 rings, different speeds/directions)
    val ring1 by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(
            tween((14000 / state.pulseSpeedMultiplier).toInt().coerceAtLeast(1400), easing = LinearEasing),
            RepeatMode.Restart
        ), label = "r1"
    )
    val ring2 by infiniteTransition.animateFloat(
        initialValue = 360f, targetValue = 0f,
        animationSpec = infiniteRepeatable(
            tween((20000 / state.pulseSpeedMultiplier).toInt().coerceAtLeast(2000), easing = LinearEasing),
            RepeatMode.Restart
        ), label = "r2"
    )
    val ring3 by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(
            tween((26000 / state.pulseSpeedMultiplier).toInt().coerceAtLeast(2600), easing = LinearEasing),
            RepeatMode.Restart
        ), label = "r3"
    )

    // Amplitude scale for speaking animation (needed by ripple speed)
    val ampScale = if (state == OrbState.SPEAKING) audioAmplitude.coerceIn(0f, 1f) else 0f
    val ampRingSpeed = 1f + ampScale * 2f

    // Expanding ripple
    val ripple by infiniteTransition.animateFloat(
        initialValue = 0.6f, targetValue = 1.4f,
        animationSpec = infiniteRepeatable(
            tween(
                if (state == OrbState.LISTENING || state == OrbState.SPEAKING) (1500 / ampRingSpeed).toInt().coerceAtLeast(300) else 3000,
                easing = FastOutSlowInEasing
            ),
            RepeatMode.Restart
        ), label = "ripple"
    )

    // Particle angle
    val particleAngle by infiniteTransition.animateFloat(
        initialValue = 0f, targetValue = 360f,
        animationSpec = infiniteRepeatable(
            tween((12000 / state.pulseSpeedMultiplier).toInt().coerceAtLeast(1200), easing = LinearEasing),
            RepeatMode.Restart
        ), label = "part"
    )

    // Energy pulse (subtle brightness oscillation)
    val energyPulse by infiniteTransition.animateFloat(
        initialValue = 0.7f, targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            tween(2000, easing = FastOutSlowInEasing),
            RepeatMode.Reverse
        ), label = "energy"
    )

    // Remaining amplitude-modulated values for Canvas rendering
    val ampBreathScale = (1f + ampScale * 0.08f) * breathScale
    val ampGlowAlpha = 0.35f + ampScale * 0.45f
    val ampEnergy = energyPulse * (0.7f + ampScale * 0.6f)
    val ampCoreSize = 0.52f + ampScale * 0.06f

    val interactionSource = remember { MutableInteractionSource() }
    val haptic = LocalHapticFeedback.current

    Box(
        modifier = modifier
            .size(size)
            .aspectRatio(1f)
            .testTag("dash_orb_${state.name.lowercase()}")
            .then(
                if (interactive && onClick != null) {
                    Modifier.clickable(
                        interactionSource = interactionSource,
                        indication = null,
                        onClick = {
                            hm.perform(HapticPattern.CONFIRM)
                            onClick()
                        }
                    )
                } else Modifier
            ),
        contentAlignment = Alignment.Center
    ) {
        Canvas(modifier = Modifier.fillMaxSize()) {
            val cx = this.size.width / 2f
            val cy = this.size.height / 2f
            val radius = (this.size.minDimension / 2f) * 0.72f * ampBreathScale

            val colors = stateColors(state)

            // ── LAYER 1: Deep atmospheric glow ──
            val glowR = radius * 2.0f
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        colors.glow.copy(alpha = ampGlowAlpha * ampEnergy),
                        colors.atmosphere,
                        Color.Transparent
                    ),
                    center = Offset(cx, cy),
                    radius = glowR
                ),
                radius = glowR,
                center = Offset(cx, cy)
            )

            // ── LAYER 2: Outer energy field ring ──
            drawCircle(
                color = colors.ring.copy(alpha = 0.12f),
                radius = radius * 1.08f,
                center = Offset(cx, cy),
                style = Stroke(
                    width = 1.2.dp.toPx(),
                    pathEffect = PathEffect.dashPathEffect(floatArrayOf(8f, 6f), 0f)
                )
            )

            // ── LAYER 3: Expanding ripple rings (3 concentric) ──
            for (i in 0 until 3) {
                val rAlpha = (1f - (ripple - 0.6f) / 0.8f).coerceIn(0f, 1f) * (0.25f - i * 0.06f)
                val rRadius = radius * (ripple + i * 0.08f)
                drawCircle(
                    color = colors.core.copy(alpha = rAlpha.coerceAtLeast(0f)),
                    radius = rRadius,
                    center = Offset(cx, cy),
                    style = Stroke(width = (1.5f - i * 0.3f).dp.toPx())
                )
            }

            // ── LAYER 4: Rotating orbital bands (3 rings) ──
            drawOrbitalBand(cx, cy, radius * 1.0f, ring1, colors.core, 0.30f, floatArrayOf(16f, 12f))
            drawOrbitalBand(cx, cy, radius * 1.12f, ring2, colors.secondary, 0.22f, floatArrayOf(10f, 14f))
            drawOrbitalBand(cx, cy, radius * 0.95f, ring3, colors.core, 0.18f, floatArrayOf(20f, 8f))

            // ── LAYER 5: Inner shell (dark sphere) ──
            drawCircle(
                color = Color(0xFF0B0D17),
                radius = radius * 0.86f,
                center = Offset(cx, cy)
            )
            drawCircle(
                color = colors.core.copy(alpha = (0.18f + ampScale * 0.15f) * ampEnergy),
                radius = radius * 0.86f,
                center = Offset(cx, cy),
                style = Stroke(width = 1.dp.toPx())
            )

            // ── LAYER 5.5: Concentric detail rings ──
            for (r in 0 until 4) {
                val rr = radius * (0.22f + r * 0.13f)
                drawCircle(
                    color = colors.core.copy(alpha = ((0.06f + ampScale * 0.08f) + 0.02f * sin(particleAngle + r)).coerceAtLeast(0f)),
                    radius = rr,
                    center = Offset(cx, cy),
                    style = Stroke(width = 0.7.dp.toPx())
                )
            }

            // ── LAYER 6: Core gradient sphere ──
            val coreR = radius * ampCoreSize
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        colors.core,
                        colors.core.copy(alpha = 0.5f),
                        colors.secondary.copy(alpha = 0.6f),
                        Color.Transparent
                    ),
                    center = Offset(cx - coreR * 0.2f, cy - coreR * 0.2f),
                    radius = coreR * 1.2f
                ),
                radius = coreR,
                center = Offset(cx, cy)
            )

            // Core specular hotspot
            drawCircle(
                brush = Brush.radialGradient(
                    colors = listOf(
                        Color.White.copy(alpha = (0.35f + ampScale * 0.25f) * ampEnergy),
                        Color.White.copy(alpha = 0.08f),
                        Color.Transparent
                    ),
                    center = Offset(cx - coreR * 0.25f, cy - coreR * 0.3f),
                    radius = coreR * 0.5f
                ),
                radius = coreR * 0.5f,
                center = Offset(cx - coreR * 0.25f, cy - coreR * 0.3f)
            )

            // ── LAYER 7: Particles ──
            drawCinematicParticles(cx, cy, radius, particleAngle, colors, state)
        }
    }
}

// ── State color palette ──

private data class OrbColors(
    val core: Color,
    val secondary: Color,
    val glow: Color,
    val atmosphere: Color,
    val ring: Color
)

private fun stateColors(state: OrbState): OrbColors = when (state) {
    OrbState.IDLE -> OrbColors(core = DashCyanPrimary, secondary = DashErrorRedContainer, glow = DashCyanPrimary, atmosphere = DashCyanPrimary.copy(alpha = 0.03f), ring = DashPrimaryContainer)
    OrbState.LISTENING -> OrbColors(core = DashTertiary, secondary = DashTertiaryDim, glow = DashTertiary, atmosphere = DashTertiary.copy(alpha = 0.03f), ring = DashTertiary)
    OrbState.THINKING -> OrbColors(core = DashCyanFixed, secondary = DashPrimaryContainer, glow = DashCyanFixed, atmosphere = DashCyanFixed.copy(alpha = 0.04f), ring = DashCyanDim)
    OrbState.SPEAKING -> OrbColors(core = DashCyanPrimary, secondary = DashCyanDim, glow = DashCyanPrimary, atmosphere = DashCyanPrimary.copy(alpha = 0.05f), ring = DashPrimaryContainer)
    OrbState.EXECUTING -> OrbColors(core = DashApprovalAmber, secondary = DashApprovalAmber, glow = DashApprovalAmber, atmosphere = DashApprovalAmber.copy(alpha = 0.03f), ring = DashApprovalAmber)
    OrbState.APPROVAL_REQUIRED -> OrbColors(core = DashApprovalAmber, secondary = DashTertiary, glow = DashApprovalAmber, atmosphere = DashApprovalAmber.copy(alpha = 0.03f), ring = DashApprovalAmber)
    OrbState.SUCCESS -> OrbColors(core = DashSuccessGreen, secondary = DashSuccessGreen, glow = DashSuccessGreen, atmosphere = DashSuccessGreen.copy(alpha = 0.03f), ring = DashSuccessGreen)
    OrbState.ERROR -> OrbColors(core = DashCyanFixed, secondary = DashErrorRedContainer, glow = DashCyanFixed, atmosphere = DashCyanFixed.copy(alpha = 0.02f), ring = DashPrimaryContainer)
    OrbState.OFFLINE -> OrbColors(core = Color(0xFF555B73), secondary = DashSurfaceContainerLow, glow = Color(0xFF555B73), atmosphere = Color(0xFF555B73).copy(alpha = 0.02f), ring = Color(0xFF555B73))
}

// ── Orbital band drawing ──

private fun DrawScope.drawOrbitalBand(
    cx: Float, cy: Float, radius: Float, rotation: Float,
    color: Color, alpha: Float, dashPattern: FloatArray
) {
    rotate(rotation, pivot = Offset(cx, cy)) {
        drawOval(
            color = color.copy(alpha = alpha),
            topLeft = Offset(cx - radius * 1.15f, cy - radius * 0.4f),
            size = Size(radius * 2.3f, radius * 0.8f),
            style = Stroke(
                width = 1.dp.toPx(),
                pathEffect = PathEffect.dashPathEffect(dashPattern, 0f)
            )
        )
    }
}

// ── Cinematic particle system ──

private fun DrawScope.drawCinematicParticles(
    cx: Float, cy: Float, radius: Float, angle: Float,
    colors: OrbColors, state: OrbState
) {
    val count = when (state) {
        OrbState.THINKING -> 18
        OrbState.SPEAKING -> 14
        OrbState.LISTENING -> 12
        OrbState.EXECUTING -> 10
        OrbState.APPROVAL_REQUIRED -> 10
        OrbState.ERROR -> 8
        else -> 6
    }

    for (i in 0 until count) {
        val phase = (i * 2.0 * Math.PI / count).toFloat()
        val speed = 1.0f + (i % 3) * 0.4f
        val baseAngle = angle * speed + phase
        val rad = baseAngle * Math.PI / 180.0

        val distRatio = 0.72f + (i % 5) * 0.06f
        val breatheOffset = sin(angle.toDouble() * 0.5 + i * 0.8).toFloat() * 0.04f
        val finalDist = (distRatio + breatheOffset).coerceIn(0.5f, 1.2f)

        val px = cx + (radius * finalDist * cos(rad.toDouble())).toFloat()
        val py = cy + (radius * finalDist * sin(rad.toDouble()) * 0.68f).toFloat()

        val pSize = (1.0f + (i % 3) * 0.8f).dp.toPx()
        val pAlpha = (0.20f + (i % 4) * 0.12f).coerceAtMost(0.65f)

        // Particle glow
        val glowRadius = pSize * 3f
        drawCircle(
            brush = Brush.radialGradient(
                colors = listOf(
                    colors.core.copy(alpha = pAlpha * 0.6f),
                    Color.Transparent
                ),
                center = Offset(px, py),
                radius = glowRadius
            ),
            radius = glowRadius,
            center = Offset(px, py)
        )

        // Particle core
        drawCircle(
            color = colors.core.copy(alpha = pAlpha),
            radius = pSize,
            center = Offset(px, py)
        )

        // Bright center dot
        drawCircle(
            color = Color.White.copy(alpha = pAlpha * 0.5f),
            radius = pSize * 0.35f,
            center = Offset(px, py)
        )
    }
}
