package com.example.ui.screens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowForward
import androidx.compose.material.icons.filled.Apps
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.Computer
import androidx.compose.material.icons.filled.EventNote
import androidx.compose.material.icons.filled.FolderOpen
import androidx.compose.material.icons.filled.FolderSpecial
import androidx.compose.material.icons.filled.Layers
import androidx.compose.material.icons.filled.Notifications
import com.example.data.notification.NotificationChime
import com.example.data.notification.NotificationSoundPreference
import androidx.compose.material.icons.filled.PermDeviceInformation
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.QrCodeScanner
import androidx.compose.material.icons.filled.ReportProblem
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.Icon
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Switch
import androidx.compose.material3.SwitchDefaults
import androidx.compose.ui.focus.FocusRequester
import androidx.compose.ui.focus.focusRequester
import androidx.compose.material.icons.filled.Edit
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.IconButton
import androidx.compose.material.icons.filled.Check
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticIntensity
import com.example.ui.components.HapticPattern
import com.example.ui.components.HapticPreference
import com.example.data.audio.WakeWordDetector
import com.example.ui.components.ConversationMode
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.components.GlassCard
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.dashColors
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.theme.ThemeMode
import com.example.ui.theme.ThemePreference
import com.example.ui.theme.AccentColor
import com.example.ui.theme.AccentColorPreference
import com.example.ui.theme.DashCyanLight
import com.example.ui.theme.DashTertiary
import com.example.ui.viewmodel.DashViewModel
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.runtime.rememberCoroutineScope
import kotlinx.coroutines.launch
import androidx.compose.material.icons.filled.Vibration
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.ui.geometry.Offset

@Composable
private fun ThemeToggleCard() {
    val hm = LocalHapticManager.current
    val themeMode by ThemePreference.themeMode.collectAsState()

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Theme Mode",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "Switch between dark and light appearance",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                ThemeMode.values().forEach { mode ->
                    val isSelected = themeMode == mode
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(
                                if (isSelected) DashCyanPrimary.copy(alpha = 0.15f)
                                else Color.White.copy(alpha = 0.04f)
                            )
                            .border(
                                1.dp,
                                if (isSelected) DashCyanPrimary.copy(alpha = 0.5f) else Color.White.copy(alpha = 0.08f),
                                RoundedCornerShape(12.dp)
                            )
                            .clickable { ThemePreference.setThemeMode(mode) }
                            .padding(horizontal = 8.dp, vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = mode.label,
                            fontSize = 12.sp,
                            fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                            color = if (isSelected) DashCyanPrimary else dashColors().textSecondary
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun HapticToggleCard() {
    val hm = LocalHapticManager.current
    val enabled by HapticPreference.enabled.collectAsState()
    val scope = rememberCoroutineScope()
    var testing by remember { mutableStateOf(false) }

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Toggle row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        hm.perform(HapticPattern.CONFIRM)
                        HapticPreference.toggle()
                    }
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = "Haptic Feedback",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = if (enabled) "Vibration on for all interactions" else "Vibration disabled",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }

                Box(
                    modifier = Modifier
                        .size(width = 52.dp, height = 28.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(
                            if (enabled) DashCyanPrimary
                            else dashColors().surfaceContainerLow
                        )
                        .clickable {
                            hm.perform(HapticPattern.CONFIRM)
                            HapticPreference.toggle()
                        },
                    contentAlignment = if (enabled) Alignment.CenterEnd else Alignment.CenterStart
                ) {
                    Box(
                        modifier = Modifier
                            .padding(3.dp)
                            .size(22.dp)
                            .clip(CircleShape)
                            .background(Color.White)
                    )
                }
            }

            // Test vibration button — only visible when enabled
            if (enabled) {
                Box(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(dashColors().surfaceContainerLow)
                        .clickable(enabled = !testing) {
                            testing = true
                            scope.launch {
                                hm.perform(HapticPattern.TAP)
                                kotlinx.coroutines.delay(600)
                                hm.perform(HapticPattern.CONFIRM)
                                kotlinx.coroutines.delay(600)
                                hm.perform(HapticPattern.DESTROY)
                                kotlinx.coroutines.delay(600)
                                hm.perform(HapticPattern.WARNING)
                                kotlinx.coroutines.delay(200)
                                testing = false
                            }
                        }
                        .padding(vertical = 10.dp),
                    contentAlignment = Alignment.Center
                ) {
                    if (testing) {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            CircularProgressIndicator(
                                modifier = Modifier.size(14.dp),
                                color = DashCyanPrimary,
                                strokeWidth = 1.5.dp
                            )
                            Text(
                                text = "Testing: TAP \u2192 CONFIRM \u2192 DESTROY \u2192 WARNING",
                                fontSize = 11.sp,
                                color = DashCyanPrimary,
                                fontFamily = FontFamily.Monospace
                            )
                        }
                    } else {
                        Row(
                            verticalAlignment = Alignment.CenterVertically,
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Icon(
                                Icons.Default.Vibration,
                                contentDescription = "Vibrate",
                                tint = DashCyanPrimary,
                                modifier = Modifier.size(14.dp)
                            )
                            Text(
                                text = "Test vibration patterns",
                                fontSize = 12.sp,
                                color = DashCyanPrimary,
                                fontWeight = FontWeight.Medium
                            )
                        }
                    }
                }
                Spacer(modifier = Modifier.height(4.dp))

                // Intensity selector row
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = "Intensity",
                        fontSize = 12.sp,
                        color = dashColors().textSecondary,
                        fontWeight = FontWeight.Medium
                    )
                    Row(horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        val currentIntensity by HapticPreference.intensity.collectAsState()
                        HapticIntensity.entries.forEach { level ->
                            val isSelected = currentIntensity == level
                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(8.dp))
                                    .background(
                                        if (isSelected) DashCyanPrimary.copy(alpha = 0.15f)
                                        else dashColors().surfaceContainerLow
                                    )
                                    .border(
                                        width = 1.dp,
                                        color = if (isSelected) DashCyanPrimary.copy(alpha = 0.5f) else Color.Transparent,
                                        shape = RoundedCornerShape(8.dp)
                                    )
                                    .clickable {
                                        hm.perform(HapticPattern.TAP)
                                        HapticPreference.setIntensity(level)
                                    }
                                    .padding(horizontal = 12.dp, vertical = 6.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = level.label,
                                    fontSize = 11.sp,
                                    fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                                    color = if (isSelected) DashCyanPrimary else dashColors().textMuted
                                )
                            }
                        }
                    }
                }
            }
        }
    }
}

@Composable
private fun WakeWordToggleCard() {
    val hm = LocalHapticManager.current
    val enabled by WakeWordDetector.isWakeWordEnabled.collectAsState()
    val customPhrase by WakeWordDetector.customPhrase.collectAsState()
    var editingPhrase by remember { mutableStateOf(customPhrase) }
    val focusRequester = remember { FocusRequester() }

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Column(modifier = Modifier.fillMaxWidth()) {
            // Toggle row
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .clickable {
                        hm.perform(HapticPattern.CONFIRM)
                        WakeWordDetector.setWakeWordEnabled(!enabled)
                    }
                    .padding(16.dp),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Text(
                            text = "Wake Word",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Medium,
                            color = dashColors().textPrimary
                        )
                        Spacer(modifier = Modifier.width(8.dp))
                        Text(
                            text = "BETA",
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Bold,
                            color = Color.White,
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(DashPurpleSecondary)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                    Text(
                        text = if (enabled) "Say '$customPhrase' to activate" else "Voice activation disabled",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }

                Box(
                    modifier = Modifier
                        .size(width = 52.dp, height = 28.dp)
                        .clip(RoundedCornerShape(14.dp))
                        .background(
                            if (enabled) DashPurpleSecondary
                            else dashColors().surfaceContainerLow
                        )
                        .clickable {
                            hm.perform(HapticPattern.CONFIRM)
                            WakeWordDetector.setWakeWordEnabled(!enabled)
                        },
                    contentAlignment = if (enabled) Alignment.CenterEnd else Alignment.CenterStart
                ) {
                    Box(
                        modifier = Modifier
                            .padding(3.dp)
                            .size(22.dp)
                            .clip(CircleShape)
                            .background(Color.White)
                    )
                }
            }

            // Custom phrase editor
            if (enabled) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                        .clip(RoundedCornerShape(12.dp))
                        .background(dashColors().surfaceContainerLow)
                        .padding(12.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    Icon(
                        Icons.Default.Edit,
                        contentDescription = "Edit",
                        tint = DashPurpleSecondary,
                        modifier = Modifier.size(16.dp)
                    )
                    OutlinedTextField(
                        value = editingPhrase,
                        onValueChange = { editingPhrase = it },
                        modifier = Modifier
                            .weight(1f)
                            .focusRequester(focusRequester),
                        textStyle = MaterialTheme.typography.bodyMedium.copy(
                            color = dashColors().textPrimary,
                            fontFamily = FontFamily.Monospace
                        ),
                        placeholder = {
                            Text("Hey DASH", color = dashColors().textMuted, fontSize = 13.sp)
                        },
                        singleLine = true,
                        shape = RoundedCornerShape(10.dp),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = DashPurpleSecondary,
                            unfocusedBorderColor = dashColors().borderGlass,
                            focusedContainerColor = Color.Transparent,
                            unfocusedContainerColor = Color.Transparent
                        )
                    )
                    IconButton(
                        onClick = {
                            hm.perform(HapticPattern.CONFIRM)
                            WakeWordDetector.setCustomPhrase(editingPhrase)
                        },
                        modifier = Modifier.size(36.dp)
                    ) {
                        Icon(
                            Icons.Default.Check,
                            contentDescription = "Save",
                            tint = DashPurpleSecondary,
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }
        }
    }
}


@Composable
private fun ConversationToggleCard() {
    val hm = LocalHapticManager.current
    val enabled by ConversationMode.enabled.collectAsState()

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable {
                    hm.perform(HapticPattern.CONFIRM)
                    ConversationMode.toggle()
                }
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Text(
                        text = "Conversation Mode",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                }
                Text(
                    text = if (enabled) "Auto-listens after speaking" else "Tap mic each time",
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                    color = dashColors().textSecondary
                )
            }

            Box(
                modifier = Modifier
                    .size(width = 52.dp, height = 28.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(
                        if (enabled) DashCyanPrimary
                        else dashColors().surfaceContainerLow
                    )
                    .clickable {
                        hm.perform(HapticPattern.CONFIRM)
                        ConversationMode.toggle()
                    },
                contentAlignment = if (enabled) Alignment.CenterEnd else Alignment.CenterStart
            ) {
                Box(
                    modifier = Modifier
                        .padding(3.dp)
                        .size(22.dp)
                        .clip(CircleShape)
                        .background(Color.White)
                )
            }
        }
    }
}

@Composable
private fun AccentColorPickerCard() {
    val hm = LocalHapticManager.current
    val selected by AccentColorPreference.accentColor.collectAsState()

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Accent Color",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "Choose your theme accent",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }
            }

            // Preset colors (first row)
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                AccentColor.entries.forEach { color ->
                    val isSelected = color == selected
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(
                                if (isSelected) color.darkPrimary.copy(alpha = 0.15f)
                                else Color.White.copy(alpha = 0.04f)
                            )
                            .border(
                                if (isSelected) 2.dp else 1.dp,
                                if (isSelected) color.darkPrimary else Color.White.copy(alpha = 0.08f),
                                RoundedCornerShape(12.dp)
                            )
                            .clickable {
                                hm.perform(HapticPattern.CONFIRM)
                                AccentColorPreference.setAccentColor(color)
                            }
                            .padding(vertical = 8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            Box(
                                modifier = Modifier
                                    .size(20.dp)
                                    .clip(CircleShape)
                                    .background(color.preview)
                            )
                            Spacer(modifier = Modifier.height(3.dp))
                            Text(
                                text = color.label,
                                fontSize = 9.sp,
                                fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                                color = if (isSelected) color.darkPrimary else dashColors().textSecondary
                            )
                        }
                    }
                }
            }

        }
    }
}

@Composable
private fun NotifCategoryFilterCard(viewModel: DashViewModel) {
    val hm = LocalHapticManager.current
    val processEnabled by viewModel.notifPrefsProcess.collectAsState()
    val errorEnabled by viewModel.notifPrefsError.collectAsState()
    val systemEnabled by viewModel.notifPrefsSystem.collectAsState()

    // Load prefs on first composition
    androidx.compose.runtime.LaunchedEffect(Unit) { viewModel.loadNotificationPrefs() }

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 14.dp
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(dashColors().errorRed.copy(alpha = 0.1f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        Icons.Default.Notifications,
                        contentDescription = "Notifications",
                        tint = dashColors().errorRed,
                        modifier = Modifier.size(18.dp)
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = "Notification Filters",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "Choose which categories to receive",
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }
            }

            // Process events toggle
            NotifCategoryRow(
                title = "Process Events",
                subtitle = "App launch & close events",
                enabled = processEnabled,
                onToggle = { hm.perform(HapticPattern.TAP); viewModel.toggleNotifCategory("process", it) }
            )

            // Error notifications toggle
            NotifCategoryRow(
                title = "Errors",
                subtitle = "Error & failure notifications",
                enabled = errorEnabled,
                onToggle = { hm.perform(HapticPattern.TAP); viewModel.toggleNotifCategory("error", it) }
            )

            // System alerts toggle
            NotifCategoryRow(
                title = "System Alerts",
                subtitle = "System warnings & alerts",
                enabled = systemEnabled,
                onToggle = { hm.perform(HapticPattern.TAP); viewModel.toggleNotifCategory("system", it) }
            )
        }
    }
}

@Composable
private fun NotifCategoryRow(
    title: String,
    subtitle: String,
    enabled: Boolean,
    onToggle: (Boolean) -> Unit
) {
    Row(
        modifier = Modifier.fillMaxWidth(),
        verticalAlignment = Alignment.CenterVertically,
        horizontalArrangement = Arrangement.SpaceBetween
    ) {
        Column(modifier = Modifier.weight(1f)) {
            Text(
                text = title,
                style = MaterialTheme.typography.bodyMedium,
                fontWeight = FontWeight.Medium,
                color = dashColors().textPrimary
            )
            Text(
                text = subtitle,
                style = MaterialTheme.typography.bodySmall,
                color = dashColors().textSecondary,
                fontSize = 11.sp
            )
        }
        androidx.compose.material3.Switch(
            checked = enabled,
            onCheckedChange = onToggle,
            colors = androidx.compose.material3.SwitchDefaults.colors(
                checkedTrackColor = dashColors().cyanPrimary.copy(alpha = 0.3f),
                checkedThumbColor = dashColors().cyanPrimary,
                uncheckedTrackColor = dashColors().surfaceContainerLow,
                uncheckedThumbColor = dashColors().textMuted
            )
        )
    }
}

@Composable
private fun NotificationChimeToggleCard() {
    val hm = LocalHapticManager.current
    val chimeEnabled by NotificationSoundPreference.enabled.collectAsState()

    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .clickable {
                    hm.perform(HapticPattern.CONFIRM)
                    NotificationSoundPreference.toggle()
                }
                .padding(16.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = "Notification Sound",
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Medium,
                    color = dashColors().textPrimary
                )
                Text(
                    text = if (chimeEnabled) "Chime tone on new notifications" else "Silent notifications",
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis,
                    style = MaterialTheme.typography.bodySmall,
                    color = dashColors().textSecondary
                )
            }

            Box(
                modifier = Modifier
                    .size(width = 52.dp, height = 28.dp)
                    .clip(RoundedCornerShape(14.dp))
                    .background(
                        if (chimeEnabled) DashCyanPrimary
                        else dashColors().surfaceContainerLow
                    )
                    .clickable {
                        hm.perform(HapticPattern.CONFIRM)
                        NotificationSoundPreference.toggle()
                    },
                contentAlignment = if (chimeEnabled) Alignment.CenterEnd else Alignment.CenterStart
            ) {
                Box(
                    modifier = Modifier
                        .padding(3.dp)
                        .size(22.dp)
                        .clip(CircleShape)
                        .background(Color.White)
                )
            }
        }
    }
}

enum class MoreSubScreen {
    MAIN_MENU,
    COMPUTER_CONTROL,
    PROJECTS,
    APPROVALS,
    MEMORY,
    PLANNER,
    KNOWLEDGE_RESEARCH,
    DEVICE_PAIRING,
    CLOUD_AWS,
    DIAGNOSTICS,
    AI_PROVIDERS,
    FILE_BROWSER,
    WINDOW_MANAGER,
    APP_LAUNCHER,
    DEVICE_STATUS,
    REMOTE_CONTROL,
    NOTIFICATION_HISTORY,
    OLLAMA_CHAT
}

@Composable
fun MoreScreen(
    viewModel: DashViewModel,
    onNavigateSub: (MoreSubScreen) -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val approvals by viewModel.approvals.collectAsState()
    val isSafeMode by viewModel.isSafeModeActive.collectAsState()
    val systemMetrics by viewModel.systemMetrics.collectAsState()
    val unreadNotificationCount by viewModel.unreadNotificationCount.collectAsState()
    val haptic = LocalHapticFeedback.current

    val pendingApprovals = approvals.filter { it.status == "PENDING" }

    LazyColumn(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("more_screen"),
        contentPadding = PaddingValues(start = 20.dp, end = 20.dp, top = 12.dp, bottom = 100.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        // Header
        item {
            Column {
                Text(
                    text = "Settings",
                    style = MaterialTheme.typography.headlineLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = dashColors().textPrimary
                )
                Text(
                    text = "System & preferences",
                    style = MaterialTheme.typography.bodySmall,
                    color = dashColors().textMuted
                )
            }
        }

        // Safe Mode
        item {
            GlassCard(
                modifier = Modifier.fillMaxWidth().testTag("safe_mode_card"),
                cornerRadius = 16.dp,
                backgroundColor = if (isSafeMode) DashErrorRed.copy(alpha = 0.1f) else dashColors().surfaceContainerLow,
                borderColor = if (isSafeMode) DashErrorRed.copy(alpha = 0.3f) else dashColors().borderGlass
            ) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(14.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        modifier = Modifier.weight(1f)
                    ) {
                        Box(
                            modifier = Modifier
                                .size(36.dp)
                                .clip(CircleShape)
                                .background(
                                    if (isSafeMode) DashErrorRed.copy(alpha = 0.2f)
                                    else Color.White.copy(alpha = 0.05f)
                                ),
                            contentAlignment = Alignment.Center
                        ) {
                            Icon(
                                imageVector = Icons.Default.ReportProblem,
                                contentDescription = "Safe Mode",
                                tint = if (isSafeMode) DashErrorRed else DashApprovalAmber,
                                modifier = Modifier.size(18.dp)
                            )
                        }
                        Spacer(modifier = Modifier.width(12.dp))
                        Column {
                            Text(
                                text = if (isSafeMode) "SAFE MODE" else "Emergency Safe Mode",
                                style = MaterialTheme.typography.titleMedium,
                                fontWeight = FontWeight.Medium,
                                color = if (isSafeMode) DashErrorRed else dashColors().textPrimary
                            )
                            Text(
                                text = if (isSafeMode) "All agents suspended" else "Lock PC & revoke sessions",
                                style = MaterialTheme.typography.bodySmall,
                                color = dashColors().textSecondary
                            )
                        }
                    }

                    Switch(
                        checked = isSafeMode,
                        onCheckedChange = {
                            if (it) viewModel.triggerSafeMode() else viewModel.disableSafeMode()
                        },
                        colors = SwitchDefaults.colors(
                            checkedThumbColor = DashErrorRed,
                            checkedTrackColor = DashErrorRed.copy(alpha = 0.3f),
                            uncheckedThumbColor = dashColors().textMuted,
                            uncheckedTrackColor = Color.White.copy(alpha = 0.08f)
                        )
                    )
                }
            }
        }

        // Appearance
        item {
            Text(
                text = "APPEARANCE",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.sp
            )
        }

        item {
            ThemeToggleCard()
        }

        item {
            AccentColorPickerCard()
        }

        item {
            HapticToggleCard()
        }

        item {
            NotificationChimeToggleCard()
        }

        item {
            NotifCategoryFilterCard(viewModel)
        }

        item {
            WakeWordToggleCard()
        }

        item {
            ConversationToggleCard()
        }

        // System & Hardware
        item {
            Text(
                text = "SYSTEM & HARDWARE",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.sp
            )
        }

        item {
            MoreRow(
                title = "Computer Control",
                subtitle = "Full remote desktop control",
                icon = Icons.Default.Computer,
                accentColor = DashCyanPrimary,
                badge = "${systemMetrics.cpuUsage}% CPU",
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.COMPUTER_CONTROL) }
            )
        }

        item {
            MoreRow(
                title = "Wake PC",
                subtitle = "Power, WoL & auto-connect",
                icon = Icons.Default.Computer,
                accentColor = DashErrorRed,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.REMOTE_CONTROL) }
            )
        }

        item {
            MoreRow(
                title = "Device Status",
                subtitle = "Health & connection",
                icon = Icons.Default.PermDeviceInformation,
                accentColor = DashSuccessGreen,
                badge = if (systemMetrics.isPcOnline) "ONLINE" else "OFFLINE",
                badgeColor = if (systemMetrics.isPcOnline) DashSuccessGreen else DashErrorRed,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.DEVICE_STATUS) }
            )
        }

        item {
            MoreRow(
                title = "Window Manager",
                subtitle = "List, focus, close windows",
                icon = Icons.Default.Layers,
                accentColor = DashPurpleSecondary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.WINDOW_MANAGER) }
            )
        }

        item {
            MoreRow(
                title = "File Browser",
                subtitle = "Browse desktop files",
                icon = Icons.Default.FolderOpen,
                accentColor = DashTertiary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.FILE_BROWSER) }
            )
        }

        item {
            MoreRow(
                title = "App Launcher",
                subtitle = "Launch Windows apps",
                icon = Icons.Default.Apps,
                accentColor = DashCyanPrimary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.APP_LAUNCHER) }
            )
        }

        item {
            MoreRow(
                title = "Approvals",
                subtitle = "Security authorization",
                icon = Icons.Default.Shield,
                accentColor = DashApprovalAmber,
                badge = if (pendingApprovals.isNotEmpty()) "${pendingApprovals.size} PENDING" else "CLEAR",
                badgeColor = if (pendingApprovals.isNotEmpty()) DashApprovalAmber else DashSuccessGreen,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.APPROVALS) }
            )
        }

        item {
            MoreRow(
                title = "Projects",
                subtitle = "Repositories & code",
                icon = Icons.Default.FolderSpecial,
                accentColor = DashCyanLight,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.PROJECTS) }
            )
        }

        // Intelligence
        item {
            Text(
                text = "INTELLIGENCE",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.sp
            )
        }

        item {
            MoreRow(
                title = "Memory & Context",
                subtitle = "Preferences & rules",
                icon = Icons.Default.Psychology,
                accentColor = DashPurpleSecondary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.MEMORY) }
            )
        }

        item {
            MoreRow(
                title = "Planner & Tasks",
                subtitle = "Daily schedule",
                icon = Icons.Default.EventNote,
                accentColor = DashCyanPrimary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.PLANNER) }
            )
        }

        item {
            MoreRow(
                title = "Knowledge & Research",
                subtitle = "RAG documents & reports",
                icon = Icons.Default.Search,
                accentColor = DashPurpleSecondary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.KNOWLEDGE_RESEARCH) }
            )
        }

        // Connectivity
        item {
            Text(
                text = "CONNECTIVITY",
                style = MaterialTheme.typography.labelSmall,
                color = dashColors().textMuted,
                letterSpacing = 1.sp
            )
        }

        item {
            MoreRow(
                title = "Device Pairing",
                subtitle = "Link & manage devices",
                icon = Icons.Default.QrCodeScanner,
                accentColor = DashCyanPrimary,
                badge = "PAIRED",
                badgeColor = DashSuccessGreen,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.DEVICE_PAIRING) }
            )
        }

        item {
            MoreRow(
                title = "Cloud & AWS",
                subtitle = "Backup & logs",
                icon = Icons.Default.Cloud,
                accentColor = DashApprovalAmber,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.CLOUD_AWS) }
            )
        }

        item {
            MoreRow(
                title = "Diagnostics",
                subtitle = "System health audit",
                icon = Icons.Default.PermDeviceInformation,
                accentColor = DashSuccessGreen,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.DIAGNOSTICS) }
            )
        }

        item {
            MoreRow(
                title = "AI Providers",
                subtitle = "Ollama, Gemini, etc.",
                icon = Icons.Default.Tune,
                accentColor = DashCyanPrimary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.AI_PROVIDERS) }
            )
        }

        item {
            MoreRow(
                title = "Ollama Chat",
                subtitle = "Direct AI chat with your PC",
                icon = Icons.Default.SmartToy,
                accentColor = DashCyanPrimary,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.OLLAMA_CHAT) }
            )
        }

        item {
            MoreRow(
                title = "Notifications",
                subtitle = "Desktop notification history",
                icon = Icons.Default.Notifications,
                accentColor = DashPurpleSecondary,
                badge = if (unreadNotificationCount > 0) "$unreadNotificationCount" else null,
                badgeColor = DashErrorRed,
                onClick = { hm.perform(HapticPattern.TAP); onNavigateSub(MoreSubScreen.NOTIFICATION_HISTORY) }
            )
        }
    }
}

@Composable
fun MoreRow(
    title: String,
    subtitle: String,
    icon: ImageVector,
    accentColor: Color,
    badge: String? = null,
    badgeColor: Color = DashCyanPrimary,
    onClick: () -> Unit
) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 14.dp,
        onClick = onClick
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Row(
                verticalAlignment = Alignment.CenterVertically,
                modifier = Modifier.weight(1f)
            ) {
                Box(
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(accentColor.copy(alpha = 0.1f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(
                        imageVector = icon,
                        contentDescription = title,
                        tint = accentColor,
                        modifier = Modifier.size(18.dp)
                    )
                }
                Spacer(modifier = Modifier.width(12.dp))
                Column {
                    Text(
                        text = title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Medium,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = subtitle,
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textSecondary
                    )
                }
            }

            Row(verticalAlignment = Alignment.CenterVertically) {
                if (badge != null) {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(6.dp))
                            .background(badgeColor.copy(alpha = 0.1f))
                            .padding(horizontal = 6.dp, vertical = 2.dp)
                    ) {
                        Text(
                            text = badge,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 9.sp,
                            fontWeight = FontWeight.Medium,
                            color = badgeColor
                        )
                    }
                    Spacer(modifier = Modifier.width(6.dp))
                }

                Icon(
                    imageVector = Icons.AutoMirrored.Filled.ArrowForward,
                    contentDescription = "Open",
                    tint = dashColors().textMuted,
                    modifier = Modifier.size(14.dp)
                )
            }
        }
    }
}

