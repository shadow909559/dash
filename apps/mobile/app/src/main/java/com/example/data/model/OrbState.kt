package com.example.data.model

import androidx.compose.ui.graphics.Color
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashTextMuted

enum class OrbState(
    val label: String,
    val subLabel: String,
    val primaryColor: Color,
    val secondaryColor: Color,
    val pulseSpeedMultiplier: Float
) {
    IDLE(
        label = "DASH",
        subLabel = "Ready",
        primaryColor = DashCyanPrimary,
        secondaryColor = DashPurpleSecondary,
        pulseSpeedMultiplier = 1.0f
    ),
    LISTENING(
        label = "Listening...",
        subLabel = "Receiving audio stream",
        primaryColor = DashCyanPrimary,
        secondaryColor = Color(0xFF00E5FF),
        pulseSpeedMultiplier = 2.2f
    ),
    THINKING(
        label = "Thinking...",
        subLabel = "Synthesizing neural model",
        primaryColor = DashPurpleSecondary,
        secondaryColor = Color(0xFF6E208C),
        pulseSpeedMultiplier = 1.8f
    ),
    SPEAKING(
        label = "Speaking...",
        subLabel = "Transmitting response",
        primaryColor = DashCyanPrimary,
        secondaryColor = Color(0xFF9CF0FF),
        pulseSpeedMultiplier = 2.5f
    ),
    EXECUTING(
        label = "Executing...",
        subLabel = "Running orchestrator tools",
        primaryColor = DashCyanPrimary,
        secondaryColor = DashPurpleSecondary,
        pulseSpeedMultiplier = 3.0f
    ),
    APPROVAL_REQUIRED(
        label = "Approval Required",
        subLabel = "Awaiting user authorization",
        primaryColor = DashApprovalAmber,
        secondaryColor = Color(0xFFFF8F00),
        pulseSpeedMultiplier = 1.5f
    ),
    SUCCESS(
        label = "Complete",
        subLabel = "Operation succeeded",
        primaryColor = DashSuccessGreen,
        secondaryColor = Color(0xFF69F0AE),
        pulseSpeedMultiplier = 1.2f
    ),
    ERROR(
        label = "Something went wrong",
        subLabel = "Diagnostics available",
        primaryColor = DashErrorRed,
        secondaryColor = Color(0xFFB71C1C),
        pulseSpeedMultiplier = 2.0f
    ),
    OFFLINE(
        label = "DASH Offline",
        subLabel = "Reconnecting to Windows...",
        primaryColor = Color(0xFF555B73),
        secondaryColor = Color(0xFF37393E),
        pulseSpeedMultiplier = 0.5f
    )
}
