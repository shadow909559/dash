package com.example.ui.theme

import android.content.Context
import android.content.SharedPreferences
import androidx.compose.ui.graphics.Color
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * User-selectable accent color options.
 * Each provides a primary accent color used across the entire UI.
 * CUSTOM uses the user-selected color stored as ARGB.
 */
enum class AccentColor(
    val label: String,
    val darkPrimary: Color,
    val lightPrimary: Color,
    val preview: Color,
) {
    CYAN("Cyan", Color(0xFF00E5FF), Color(0xFF0097A7), Color(0xFF00E5FF)),
    PURPLE("Purple", Color(0xFF7C4DFF), Color(0xFF6200EA), Color(0xFF7C4DFF)),
    RED("Crimson", Color(0xFFFF1744), Color(0xFFD50000), Color(0xFFFF1744)),
    GREEN("Emerald", Color(0xFF00E676), Color(0xFF00A152), Color(0xFF00E676)),
    AMBER("Amber", Color(0xFFFFD740), Color(0xFFFF8F00), Color(0xFFFFD740)),
    PINK("Rose", Color(0xFFFF4081), Color(0xFFC51162), Color(0xFFFF4081)),
}

/**
 * Manages accent color preference with reactive state.
 * Persists across app restarts via SharedPreferences.
 * Supports both preset colors and custom ARGB values.
 */
object AccentColorPreference {
    private const val PREFS_NAME = "dash_accent"
    private const val KEY_ACCENT_COLOR = "accent_color"

    private var prefs: SharedPreferences? = null
    private val _accentColor = MutableStateFlow(AccentColor.CYAN)
    val accentColor: StateFlow<AccentColor> = _accentColor.asStateFlow()



    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val saved = prefs?.getString(KEY_ACCENT_COLOR, AccentColor.CYAN.name)
        _accentColor.value = try {
            AccentColor.valueOf(saved ?: AccentColor.CYAN.name)
        } catch (_: Exception) {
            AccentColor.CYAN
        }

    }

    fun setAccentColor(color: AccentColor) {
        _accentColor.value = color
        prefs?.edit()?.putString(KEY_ACCENT_COLOR, color.name)?.apply()
    }

    fun getAccentColor(): AccentColor = _accentColor.value

    fun getResolvedColors(): Pair<Color, Color> {
        val current = _accentColor.value
        return current.darkPrimary to current.lightPrimary
    }
}
