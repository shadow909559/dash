package com.example.ui.components

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Manages conversation mode preference — when enabled, DASH auto-listens
 * after speaking, enabling back-and-forth dialogue without tapping the mic.
 *
 * Auto-stops after SILENCE_TIMEOUT_MS of silence (user stops responding).
 */
object ConversationMode {
    private const val PREFS_NAME = "dash_conversation"
    private const val KEY_ENABLED = "conversation_enabled"

    /** How long to wait for user response before ending conversation (ms) */
    const val SILENCE_TIMEOUT_MS = 10_000L

    /** Max consecutive turns before forcing a pause (prevents infinite loops) */
    const val MAX_TURNS = 20

    private var prefs: SharedPreferences? = null
    private val _enabled = MutableStateFlow(false)
    val enabled: StateFlow<Boolean> = _enabled.asStateFlow()

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        _enabled.value = prefs?.getBoolean(KEY_ENABLED, false) ?: false
    }

    fun setEnabled(value: Boolean) {
        _enabled.value = value
        prefs?.edit()?.putBoolean(KEY_ENABLED, value)?.apply()
    }

    fun toggle() {
        setEnabled(!_enabled.value)
    }

    fun isEnabled(): Boolean = _enabled.value
}
