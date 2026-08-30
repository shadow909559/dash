package com.example.ui.theme

import androidx.compose.animation.animateColorAsState
import androidx.compose.animation.core.AnimationSpec
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.tween
import androidx.compose.material3.MaterialTheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.CompositionLocalProvider
import androidx.compose.runtime.Immutable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.compositionLocalOf
import androidx.compose.runtime.getValue
import androidx.compose.ui.graphics.Color
import com.example.ui.theme.dashColors

/**
 * Theme-aware DASH color scheme.
 * Provides both dark and light variants that change when the user switches themes.
 * Colors animate smoothly between dark and light modes.
 */
@Immutable
data class DashColorScheme(
    val background: Color,
    val surface: Color,
    val surfaceContainer: Color,
    val surfaceContainerLow: Color,
    val textPrimary: Color,
    val textSecondary: Color,
    val textMuted: Color,
    val borderGlass: Color,
    val borderSubtle: Color,
    val primary: Color,
    val cyanPrimary: Color,
    val purplePrimary: Color,
    val successGreen: Color,
    val errorRed: Color,
    val warningAmber: Color,
    val approvalAmber: Color,
)

val DarkDashColors = DashColorScheme(
    background = Color(0xFF0B0D17),
    surface = Color(0xFF111322),
    surfaceContainer = Color(0xFF161930),
    surfaceContainerLow = Color(0xFF12142A),
    textPrimary = Color(0xFFE8ECF4),
    textSecondary = Color(0xFF8B92A8),
    textMuted = Color(0xFF555B73),
    borderGlass = Color(0xFF1E2140),
    borderSubtle = Color(0xFF14162C),
    primary = Color(0xFF1A1F3D),
    cyanPrimary = Color(0xFF00E5FF),
    purplePrimary = Color(0xFF7C4DFF),
    successGreen = Color(0xFF00E676),
    errorRed = Color(0xFFFF1744),
    warningAmber = Color(0xFFFFD740),
    approvalAmber = Color(0xFFFFB300),
)

val LightDashColors = DashColorScheme(
    background = Color(0xFFF5F6FA),
    surface = Color.White,
    surfaceContainer = Color(0xFFEEF0F6),
    surfaceContainerLow = Color(0xFFF0F2F8),
    textPrimary = Color(0xFF1A1D2E),
    textSecondary = Color(0xFF5A6178),
    textMuted = Color(0xFF8B92A8),
    borderGlass = Color(0xFFD8DAE5),
    borderSubtle = Color(0xFFE8EAF0),
    primary = Color(0xFF1A1F3D),
    cyanPrimary = Color(0xFF0097A7),
    purplePrimary = Color(0xFF6200EA),
    successGreen = Color(0xFF00A152),
    errorRed = Color(0xFFD50000),
    warningAmber = Color(0xFFFF8F00),
    approvalAmber = Color(0xFFF57F17),
)

/** Use compositionLocalOf (not static) so theme changes trigger recomposition */
val LocalDashColors = compositionLocalOf { DarkDashColors }

/** Access current theme-aware DASH colors from any Composable */
@Composable
fun dashColors(): DashColorScheme = LocalDashColors.current

/** Animation spec for theme transitions — 500ms smooth crossfade with natural easing */
private val themeTransition: AnimationSpec<Color> = tween(
    durationMillis = 500,
    easing = FastOutSlowInEasing
)

/** Provide theme-aware DASH colors to the composition tree with smooth animation */
@Composable
fun DashColorProvider(
    isDark: Boolean,
    content: @Composable () -> Unit
) {
    // Apply user-selected accent color
    val accentColor by AccentColorPreference.accentColor.collectAsState()
    val (darkAccent, lightAccent) = AccentColorPreference.getResolvedColors()
    val baseTarget = if (isDark) DarkDashColors else LightDashColors
    val target = baseTarget.copy(
        cyanPrimary = if (isDark) darkAccent else lightAccent
    )

    // Animate every color property individually for smooth crossfade
    val background by animateColorAsState(target.background, themeTransition, label = "bg")
    val surface by animateColorAsState(target.surface, themeTransition, label = "surface")
    val surfaceContainer by animateColorAsState(target.surfaceContainer, themeTransition, label = "surfaceContainer")
    val surfaceContainerLow by animateColorAsState(target.surfaceContainerLow, themeTransition, label = "surfaceContainerLow")
    val textPrimary by animateColorAsState(target.textPrimary, themeTransition, label = "textPrimary")
    val textSecondary by animateColorAsState(target.textSecondary, themeTransition, label = "textSecondary")
    val textMuted by animateColorAsState(target.textMuted, themeTransition, label = "textMuted")
    val borderGlass by animateColorAsState(target.borderGlass, themeTransition, label = "borderGlass")
    val borderSubtle by animateColorAsState(target.borderSubtle, themeTransition, label = "borderSubtle")
    val primary by animateColorAsState(target.primary, themeTransition, label = "primary")
    val cyanPrimary by animateColorAsState(target.cyanPrimary, themeTransition, label = "cyanPrimary")
    val purplePrimary by animateColorAsState(target.purplePrimary, themeTransition, label = "purplePrimary")
    val successGreen by animateColorAsState(target.successGreen, themeTransition, label = "successGreen")
    val errorRed by animateColorAsState(target.errorRed, themeTransition, label = "errorRed")
    val warningAmber by animateColorAsState(target.warningAmber, themeTransition, label = "warningAmber")
    val approvalAmber by animateColorAsState(target.approvalAmber, themeTransition, label = "approvalAmber")

    val animatedColors = DashColorScheme(
        background = background,
        surface = surface,
        surfaceContainer = surfaceContainer,
        surfaceContainerLow = surfaceContainerLow,
        textPrimary = textPrimary,
        textSecondary = textSecondary,
        textMuted = textMuted,
        borderGlass = borderGlass,
        borderSubtle = borderSubtle,
        primary = primary,
        cyanPrimary = cyanPrimary,
        purplePrimary = purplePrimary,
        successGreen = successGreen,
        errorRed = errorRed,
        warningAmber = warningAmber,
        approvalAmber = approvalAmber,
    )

    CompositionLocalProvider(LocalDashColors provides animatedColors) {
        content()
    }
}
