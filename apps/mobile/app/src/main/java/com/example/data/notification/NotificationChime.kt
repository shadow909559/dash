package com.example.data.notification

import android.media.AudioAttributes
import android.media.AudioManager
import android.media.ToneGenerator
import android.os.Build
import android.os.VibrationEffect
import android.os.Vibrator
import android.os.VibratorManager
import android.content.Context
import android.util.Log
import com.example.ui.components.HapticPreference

/**
 * Plays a soft notification chime synchronized with the DESTROY haptic pattern.
 * Uses ToneGenerator for a clean system chime — no audio file required.
 *
 * The chime consists of two tones:
 * - Short high tone (notification attention)
 * - Brief pause
 * - Lower tone (confirmation)
 *
 * Played through the notification stream at low volume for subtlety.
 */
object NotificationChime {
    private const val TAG = "NotificationChime"
    private var toneGenerator: ToneGenerator? = null
    private var vibrator: Vibrator? = null
    private var soundEnabled = true
    private var hapticEnabled = true

    fun init(context: Context) {
        try {
            toneGenerator = ToneGenerator(
                AudioManager.STREAM_NOTIFICATION,
                80 // Volume: 0-100 (60 = moderate)
            )
        } catch (e: Exception) {
            Log.e(TAG, "Failed to init ToneGenerator: ${e.message}")
        }

        vibrator = if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.S) {
            val vm = context.getSystemService(Context.VIBRATOR_MANAGER_SERVICE) as? VibratorManager
            vm?.defaultVibrator
        } else {
            @Suppress("DEPRECATION")
            context.getSystemService(Context.VIBRATOR_SERVICE) as? Vibrator
        }
    }

    fun setEnabled(enabled: Boolean) {
        soundEnabled = enabled
        hapticEnabled = enabled
    }

    fun setSoundEnabled(enabled: Boolean) {
        soundEnabled = enabled
    }

    fun setHapticEnabled(enabled: Boolean) {
        hapticEnabled = enabled
    }

    /**
     * Play the notification chime with synchronized DESTROY haptic pattern.
     * - Tone 1: 120ms high C5 tone
     * - Haptic: 50ms strong pulse (DESTROY pattern)
     * - Tone 2: 100ms lower E4 tone (after 80ms gap)
     */
    fun play() {
        // Check preferences directly for real-time toggle
        val soundOn = NotificationSoundPreference.enabled.value
        val hapticOn = HapticPreference.enabled.value
        if (!soundOn && !hapticOn) return

        try {
            // Play two-tone chime (only if sound enabled)
            if (soundOn) {
                toneGenerator?.startTone(ToneGenerator.TONE_PROP_ACK, 120)
            }
            // Haptic synchronized with first tone (only if haptic enabled)
            if (hapticOn) {
                vibrateDestroy()
            }

            // Second tone after brief gap (only if sound enabled)
            if (soundOn) {
                android.os.Handler(android.os.Looper.getMainLooper()).postDelayed({
                    try {
                        toneGenerator?.startTone(ToneGenerator.TONE_PROP_BEEP2, 100)
                    } catch (e: Exception) {
                        Log.e(TAG, "Second tone failed: ${e.message}")
                    }
                }, 80)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Chime play failed: ${e.message}")
        }
    }

    /**
     * Play a lighter chime for non-critical notifications.
     * Single tone + soft haptic.
     */
    fun playLight() {
        val soundOn = NotificationSoundPreference.enabled.value
        val hapticOn = HapticPreference.enabled.value
        if (!soundOn && !hapticOn) return

        try {
            if (soundOn) {
                toneGenerator?.startTone(ToneGenerator.TONE_PROP_BEEP, 80)
            }
            // Light haptic
            if (hapticOn) {
                if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                    vibrator?.vibrate(VibrationEffect.createOneShot(10, VibrationEffect.DEFAULT_AMPLITUDE))
                } else {
                    @Suppress("DEPRECATION")
                    vibrator?.vibrate(10)
                }
            }
        } catch (e: Exception) {
            Log.e(TAG, "Light chime failed: ${e.message}")
        }
    }

    private fun vibrateDestroy() {
        try {
            if (Build.VERSION.SDK_INT >= Build.VERSION_CODES.O) {
                vibrator?.vibrate(VibrationEffect.createOneShot(50, VibrationEffect.DEFAULT_AMPLITUDE))
            } else {
                @Suppress("DEPRECATION")
                vibrator?.vibrate(50)
            }
        } catch (e: Exception) {
            Log.e(TAG, "Haptic failed: ${e.message}")
        }
    }

    fun release() {
        try {
            toneGenerator?.release()
        } catch (_: Exception) {}
        toneGenerator = null
    }
}
