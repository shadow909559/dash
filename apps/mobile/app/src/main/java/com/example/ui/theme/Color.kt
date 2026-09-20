package com.example.ui.theme

import androidx.compose.ui.graphics.Color

// ═══════════════════════════════════════════════════════════════
// DASH JARVIS — Premium Dark Theme with Cyan/Blue accents
// ═══════════════════════════════════════════════════════════════

// ── Background Layers (deepest to lightest) — engineered-instrument pass,
//    aligned with the desktop/website identity (decisions.md #112) ──
val DashBackground      = Color(0xFF06090F)
val DashSurface         = Color(0xFF0D1219)
val DashSurfaceLowest   = Color(0xFF080B11)
val DashSurfaceContainerLow = Color(0xFF10151D)
val DashSurfaceContainer = Color(0xFF151B26)
val DashSurfaceContainerHigh = Color(0xFF1A2230)
val DashSurfaceContainerHighest = Color(0xFF202A3C)

// ── Text Hierarchy ──
val DashTextPrimary     = Color(0xFFEDF4FC)
val DashTextSecondary   = Color(0xFF8FB2D4)
val DashTextMuted       = Color(0xFF4D6A8A)
val DashTextDisabled    = Color(0xFF35485C)

// ── Primary: JARVIS Cyan/Blue (energy core) ──
val DashPrimary         = Color(0xFF3FA9F5)
val DashPrimaryLight    = Color(0xFF5AB8F5)
val DashPrimaryContainer = Color(0xFF0A1A2A)
val DashPrimaryFixed    = Color(0xFF3FA9F5)

// ── Accent: Electric Cyan (JARVIS energy) ──
val DashCyanPrimary     = Color(0xFF00D4FF)
val DashCyanLight       = Color(0xFF00E5FF)
val DashCyanDark        = Color(0xFF2F8FD6)
val DashCyanFixed       = Color(0xFF00F5FF)
val DashCyanGlow        = Color(0x403FA9F5)

// ── Tertiary: Purple (luxury) ──
val DashPurplePrimary   = Color(0xFF8B5CF6)
val DashPurpleSecondary = Color(0xFF7C3AED)
val DashPurpleContainer = Color(0xFF1A0D2E)
val DashPurpleGlow      = Color(0x408B5CF6)

// ── Semantic Status ──
val DashSuccessGreen    = Color(0xFF22C55E)
val DashSuccessDark     = Color(0xFF16A34A)
val DashSuccessContainer = Color(0xFF0A1F0F)
val DashWarningAmber    = Color(0xFFF59E0B)
val DashApprovalAmber   = Color(0xFFFBBF24)
val DashWarningContainer = Color(0xFF1F1A0A)
val DashErrorRed        = Color(0xFFEF4444)
val DashErrorDark       = Color(0xFFDC2626)
val DashErrorContainer  = Color(0xFF1F0A0A)

// ── Border & Divider ──
val DashBorderGlass     = Color(0x18FFFFFF)
val DashBorderSubtle    = Color(0x10FFFFFF)
val DashBorderCrimson   = Color(0x303FA9F5)
val DashBorderCyan      = Color(0x303FA9F5)

// ── Glow & Shadow (for JARVIS effects) ──
val DashGlowCrimson     = Color(0x253FA9F5)
val DashGlowCyan        = Color(0x203FA9F5)
val DashGlowPurple      = Color(0x208B5CF6)

// ── Overlay ──
val DashOverlay         = Color(0xCC050507)
val DashScrim           = Color(0x80000000)

// ── Legacy aliases for compatibility ──
val DashTertiary        = DashPurplePrimary
val DashCyanSecondary   = DashCyanDark
val DashBorder          = DashBorderGlass
val DashCardBg          = DashSurfaceContainer


// ── Lowest surface ──
val DashSurfaceContainerLowest = DashSurfaceLowest

// ── Dim/Muted variants for orb states ──
val DashCyanDim         = DashCyanDark.copy(alpha = 0.5f)
val DashErrorRedContainer = DashErrorContainer
val DashTertiaryDim     = DashPurplePrimary.copy(alpha = 0.5f)
val DashPrimaryDim      = DashPrimary.copy(alpha = 0.5f)

// ── Orb State Colors ──
val OrbIdle             = DashCyanPrimary
val OrbListening        = DashPurplePrimary
val OrbThinking         = DashWarningAmber
val OrbSpeaking         = DashSuccessGreen
val OrbExecuting        = DashPrimaryLight
val OrbError            = DashErrorRed
