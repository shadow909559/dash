package com.example.ui.theme

import android.content.Context
import android.content.SharedPreferences
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow

/**
 * Theme mode options.
 */
enum class ThemeMode(val label: String) {
    DARK("Dark"),
    LIGHT("Light"),
    SYSTEM("System")
}

/**
 * Manages theme mode preference with reactive state.
 */
object ThemePreference {
    private const val PREFS_NAME = "dash_theme"
    private const val KEY_THEME_MODE = "theme_mode"

    private var prefs: SharedPreferences? = null
    private val _themeMode = MutableStateFlow(ThemeMode.DARK)
    val themeMode: StateFlow<ThemeMode> = _themeMode.asStateFlow()

    fun init(context: Context) {
        prefs = context.getSharedPreferences(PREFS_NAME, Context.MODE_PRIVATE)
        val saved = prefs?.getString(KEY_THEME_MODE, ThemeMode.DARK.name)
        _themeMode.value = try {
            ThemeMode.valueOf(saved ?: ThemeMode.DARK.name)
        } catch (_: Exception) {
            ThemeMode.DARK
        }
    }

    fun setThemeMode(mode: ThemeMode) {
        _themeMode.value = mode
        prefs?.edit()?.putString(KEY_THEME_MODE, mode.name)?.apply()
    }

    /**
     * Returns true if the current effective theme is dark.
     */
    fun isDarkMode(): Boolean {
        return _themeMode.value == ThemeMode.DARK
    }
}
