package com.example.ui.components

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Manages haptic feedback preference (on/off + intensity) with reactive state.
 * Persists across app restarts via SharedPreferences.
 */
enum class HapticIntensity(val label: String, val multiplier: Float) {
    LIGHT("Light", 0.5f),
    MEDIUM("Medium", 1.0f),
    STRONG("Strong", 1.8f)
}

object HapticPreference {
    private const val PREFS_NAME = "dash_haptic"
    private const val KEY_HAPTIC_ENABLED = "haptic_enabled"
    private const val KEY_HAPTIC_INTENSITY = "haptic_intensity"

    private var prefs: SharedPreferences? = null
    private val _enabled = MutableStateFlow(true)
    val enabled: StateFlow<Boolean> = _enabled.asStateFlow()
    private val _intensity = MutableStateFlow(HapticIntensity.MEDIUM)
    val intensity: StateFlow<HapticIntensity> = _intensity.asStateFlow()

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        _enabled.value = prefs?.getBoolean(KEY_HAPTIC_ENABLED, true) ?: true
        val saved = prefs?.getString(KEY_HAPTIC_INTENSITY, null)
        _intensity.value = try { HapticIntensity.valueOf(saved ?: "MEDIUM") } catch (_: Exception) { HapticIntensity.MEDIUM }
    }

    fun setEnabled(value: Boolean) {
        _enabled.value = value
        prefs?.edit()?.putBoolean(KEY_HAPTIC_ENABLED, value)?.apply()
    }

    fun toggle() {
        setEnabled(!_enabled.value)
    }

    fun setIntensity(value: HapticIntensity) {
        _intensity.value = value
        prefs?.edit()?.putString(KEY_HAPTIC_INTENSITY, value.name)?.apply()
    }

    fun isEnabled(): Boolean = _enabled.value
    fun getIntensity(): HapticIntensity = _intensity.value
}
