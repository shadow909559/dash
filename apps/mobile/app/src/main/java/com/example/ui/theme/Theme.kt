package com.example.ui.theme

import android.app.Activity
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.background
import androidx.compose.foundation.isSystemInDarkTheme
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.darkColorScheme
import androidx.compose.material3.lightColorScheme
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.SideEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.graphics.toArgb
import androidx.compose.ui.platform.LocalView
import androidx.core.view.WindowCompat
import androidx.core.view.WindowInsetsControllerCompat
import com.example.ui.theme.DashColorProvider
import com.example.ui.theme.dashColors
import kotlinx.coroutines.delay

private val UltronDarkScheme = darkColorScheme(
    primary = DashPrimary, onPrimary = Color.White,
    primaryContainer = DashPrimaryContainer, onPrimaryContainer = DashPrimaryLight,
    secondary = DashCyanPrimary, onSecondary = Color.Black,
    secondaryContainer = Color(0xFF0A1A1F), onSecondaryContainer = DashCyanLight,
    tertiary = DashPurplePrimary, onTertiary = Color.White,
    tertiaryContainer = DashPurpleContainer, onTertiaryContainer = DashPurplePrimary,
    error = DashErrorRed, onError = Color.White,
    errorContainer = DashErrorContainer, onErrorContainer = DashErrorRed,
    background = Color(0xFF050507), onBackground = DashTextPrimary,
    surface = Color(0xFF0A0A0F), onSurface = DashTextPrimary,
    surfaceVariant = DashSurfaceContainerLow, onSurfaceVariant = DashTextSecondary,
    outline = DashBorderGlass, outlineVariant = DashBorderSubtle,
)

private val UltronLightScheme = lightColorScheme(
    primary = Color(0xFF0097A7), onPrimary = Color.White,
    primaryContainer = Color(0xFFB2EBF2), onPrimaryContainer = Color(0xFF00363A),
    secondary = Color(0xFF0097A7), onSecondary = Color.White,
    secondaryContainer = Color(0xFFE0F7FA), onSecondaryContainer = Color(0xFF00363A),
    tertiary = Color(0xFF6200EA), onTertiary = Color.White,
    tertiaryContainer = Color(0xFFEDE7F6), onTertiaryContainer = Color(0xFF1A0060),
    error = Color(0xFFD50000), onError = Color.White,
    errorContainer = Color(0xFFFFDAD6), onErrorContainer = Color(0xFF410002),
    background = Color(0xFFF5F6FA), onBackground = Color(0xFF1A1D2E),
    surface = Color.White, onSurface = Color(0xFF1A1D2E),
    surfaceVariant = Color(0xFFEEF0F6), onSurfaceVariant = Color(0xFF5A6178),
    outline = Color(0xFFD8DAE5), outlineVariant = Color(0xFFE8EAF0),
)

@Composable
fun DashTheme(
    isDarkTheme: Boolean = true,
    content: @Composable () -> Unit
) {
    val view = LocalView.current
    if (!view.isInEditMode) {
        SideEffect {
            val window = (view.context as? Activity)?.window ?: return@SideEffect
            window.statusBarColor = Color.Transparent.toArgb()
            window.navigationBarColor = if (isDarkTheme) Color(0xFF0B0D17).toArgb() else Color(0xFFF5F6FA).toArgb()
            WindowCompat.setDecorFitsSystemWindows(window, false)
            val controller = WindowInsetsControllerCompat(window, window.decorView)
            controller.isAppearanceLightStatusBars = !isDarkTheme
            controller.isAppearanceLightNavigationBars = !isDarkTheme
        }
    }

    // Animate Material3 color scheme for smooth transition
    val targetScheme = if (isDarkTheme) UltronDarkScheme else UltronLightScheme
    val animSpec = androidx.compose.animation.core.tween<androidx.compose.ui.graphics.Color>(500, easing = androidx.compose.animation.core.FastOutSlowInEasing)
    val animatedScheme = targetScheme.copy(
        background = androidx.compose.animation.animateColorAsState(targetScheme.background, animSpec, label = "m3_bg").value,
        surface = androidx.compose.animation.animateColorAsState(targetScheme.surface, animSpec, label = "m3_surface").value,
        onBackground = androidx.compose.animation.animateColorAsState(targetScheme.onBackground, animSpec, label = "m3_onBg").value,
        onSurface = androidx.compose.animation.animateColorAsState(targetScheme.onSurface, animSpec, label = "m3_onSurface").value,
        primary = androidx.compose.animation.animateColorAsState(targetScheme.primary, animSpec, label = "m3_primary").value,
        secondary = androidx.compose.animation.animateColorAsState(targetScheme.secondary, animSpec, label = "m3_secondary").value,
        surfaceVariant = androidx.compose.animation.animateColorAsState(targetScheme.surfaceVariant, animSpec, label = "m3_surfaceVariant").value,
    )

    // Flash overlay animation for theme transition
    var flashAlpha by remember { mutableFloatStateOf(0f) }
    var previousIsDark by remember { mutableStateOf(isDarkTheme) }

    LaunchedEffect(isDarkTheme) {
        if (previousIsDark != isDarkTheme) {
            flashAlpha = 0.3f // Brief flash on change
            delay(50)
            flashAlpha = 0f   // Fade out quickly
        }
        previousIsDark = isDarkTheme
    }

    DashColorProvider(isDark = isDarkTheme) {
        Box(modifier = Modifier.fillMaxSize()) {
            MaterialTheme(
                colorScheme = animatedScheme,
                typography = Typography,
                content = content
            )
            // Subtle flash overlay during theme switch
            if (flashAlpha > 0f) {
                Box(
                    modifier = Modifier
                        .fillMaxSize()
                        .graphicsLayer { alpha = flashAlpha }
                        .background(if (isDarkTheme) Color.White else Color.Black)
                )
            }
        }
    }
}
