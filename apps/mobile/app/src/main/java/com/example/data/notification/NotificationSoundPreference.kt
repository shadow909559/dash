package com.example.data.notification

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Persisted preference for notification chime sounds (separate from haptics).
 * Controls whether the ToneGenerator plays audio on new notifications.
 */
object NotificationSoundPreference {
    private const val PREFS_NAME = "dash_notification_sound"
    private const val KEY_ENABLED = "sound_enabled"

    private val _enabled = MutableStateFlow(true)
    val enabled = _enabled.asStateFlow()

    private var prefs: SharedPreferences? = null

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        _enabled.value = prefs?.getBoolean(KEY_ENABLED, true) ?: true
    }

    fun setEnabled(enabled: Boolean) {
        _enabled.value = enabled
        prefs?.edit()?.putBoolean(KEY_ENABLED, enabled)?.apply()
    }

    fun toggle() {
        setEnabled(!_enabled.value)
    }
}
