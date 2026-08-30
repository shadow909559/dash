package com.example.ui.components

import android.content.Context
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.remember
import androidx.compose.ui.platform.LocalContext

/**
 * Haptic feedback manager with distinct vibration patterns for different action types.
 *
 * Uses Android's Vibrator service for precise control:
 * - TAP:      8ms single pulse — light navigation, list items
 * - CONFIRM:  8ms + 40ms gap + 12ms double pulse — send, approve, success
 * - DESTROY:  50ms strong pulse — delete, power off, clear all
 * - WARNING:  15ms + 30ms gap + 15ms + 30ms gap + 15ms triple pulse — error, denied
 */

enum class HapticPattern {
    /** Short single buzz — tab switches, navigation, list items, icons */
    TAP,
    /** Double buzz — confirmations, send actions, approvals, toggle on */
    CONFIRM,
    /** Strong long buzz — destructive actions, delete, power off, clear all */
    DESTROY,
    /** Triple buzz — errors, denied, warnings */
    WARNING
}

class HapticManager(context: Context) {
    private val vibrator: Vibrator? = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
        val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
        vm?.defaultVibrator
    } else {
        @Suppress("DEPRECATION")
        context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
    }

    private val hasVibrator: Boolean = vibrator?.hasVibrator() == true

    fun perform(pattern: HapticPattern) {
        if (!hasVibrator || !HapticPreference.isEnabled()) return
        val intensity = HapticPreference.getIntensity()
        val m = intensity.multiplier
        // Scale amplitude (1-255) by intensity
        val amp = (VibrationEffect.DEFAULT_AMPLITUDE * m).toInt().coerceIn(1, 255)
        when (pattern) {
            HapticPattern.TAP -> vibrate((8 * m).toLong().coerceAtLeast(1), amp)
            HapticPattern.CONFIRM -> pulse(
                doubleArrayOf(0.0, 8.0 * m, 40.0, 12.0 * m), amp
            )
            HapticPattern.DESTROY -> vibrate((50 * m).toLong().coerceAtLeast(1), amp)
            HapticPattern.WARNING -> pulse(
                doubleArrayOf(0.0, 15.0 * m, 30.0, 15.0 * m, 30.0, 15.0 * m), amp
            )
        }
    }

    private fun vibrate(durationMs: Long, amplitude: Int = VibrationEffect.DEFAULT_AMPLITUDE) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            vibrator?.vibrate(VibrationEffect.createOneShot(durationMs, amplitude))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(durationMs)
        }
    }

    private fun pulse(timings: DoubleArray, amplitude: Int = VibrationEffect.DEFAULT_AMPLITUDE) {
        if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
            // For waveform, alternate between amplitude and 0 for gaps
            val amps = timings.mapIndexed { i, t -> if (t > 0.0 && i % 2 == 1) amplitude else 0 }.toIntArray()
            vibrator?.vibrate(VibrationEffect.createWaveform(timings.map { it.toLong() }.toLongArray(), amps, -1))
        } else {
            @Suppress("DEPRECATION")
            vibrator?.vibrate(timings.map { it.toLong() }.toLongArray(), -1)
        }
    }
}

val LocalHapticManager = compositionLocalOf<HapticManager> {
    error("No HapticManager provided")
}

@Composable
fun ProvideHapticManager(content: @Composable () -> Unit) {
    val context = LocalContext.current
    val manager = remember { HapticManager(context) }
    CompositionLocalProvider(LocalHapticManager provides manager) {
        content()
    }
}
