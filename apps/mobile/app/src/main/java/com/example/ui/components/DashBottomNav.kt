package com.example.ui.components

import androidx.compose.animation.core.*
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.interaction.MutableInteractionSource
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.Icon
import androidx.compose.material3.Text
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.theme.*
import com.example.ui.theme.dashColors

private data class NavItem(val destination: NavDestination, val icon: ImageVector)

private val navItems = listOf(
    NavItem(NavDestination.HOME, Icons.Default.Home),
    NavItem(NavDestination.CHAT, Icons.Default.Chat),
    NavItem(NavDestination.VOICE, Icons.Default.Mic),
    NavItem(NavDestination.AGENT, Icons.Default.AutoAwesome),
    NavItem(NavDestination.ACTIVITY, Icons.Default.List),
    NavItem(NavDestination.MORE, Icons.Default.MoreHoriz),
)

@Composable
fun DashBottomNav(
    currentDestination: NavDestination,
    onNavigate: (NavDestination) -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current

    Box(
        modifier = modifier
            .fillMaxWidth()
            .background(dashColors().background)
            .padding(horizontal = 8.dp, vertical = 8.dp)
    ) {
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(RoundedCornerShape(20.dp))
                .background(dashColors().surfaceContainerLow.copy(alpha = 0.85f))
                .border(1.dp, dashColors().borderGlass, RoundedCornerShape(20.dp))
                .padding(horizontal = 4.dp, vertical = 6.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceEvenly,
                verticalAlignment = Alignment.CenterVertically
            ) {
                navItems.forEach { item ->
                    val isSelected = item.destination == currentDestination
                    val color = if (isSelected) DashCyanPrimary else dashColors().textMuted

                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(14.dp))
                            .background(if (isSelected) DashCyanPrimary.copy(alpha = 0.12f) else Color.Transparent)
                            .clickable(
                                interactionSource = remember { MutableInteractionSource() },
                                indication = null
                            ) {
                                hm.perform(HapticPattern.TAP)
                                onNavigate(item.destination)
                            }
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.spacedBy(3.dp)) {
                            Icon(item.icon, contentDescription = item.destination.label, tint = color, modifier = Modifier.size(20.dp))
                            Text(
                                text = item.destination.label,
                                fontSize = 9.sp, fontFamily = FontFamily.Monospace,
                                fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                                color = color, letterSpacing = 0.5.sp
                            )
                            if (isSelected) {
                                GlowDot(color = DashCyanPrimary, size = 4.dp, pulsing = true)
                            }
                        }
                    }
                }
            }
        }
    }
}
