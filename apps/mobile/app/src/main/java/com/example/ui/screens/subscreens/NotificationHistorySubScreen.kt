package com.example.ui.screens.subscreens

import androidx.compose.animation.core.Animatable
import androidx.compose.animation.core.Spring
import androidx.compose.animation.core.spring
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.detectHorizontalDragGestures
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.offset
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.DoneAll
import androidx.compose.material.icons.filled.Notifications
import androidx.compose.material.icons.outlined.Archive
import androidx.compose.material.icons.outlined.MarkEmailRead
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.draw.shadow
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.IntOffset
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.local.entity.NotificationEntity
import com.example.ui.components.GlassCard
import com.example.ui.components.ShimmerListSkeleton
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.dashColors
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import java.text.SimpleDateFormat
import java.util.Date
import java.util.Locale
import kotlin.math.roundToInt

@Composable
fun NotificationHistorySubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val notifications by viewModel.notifications.collectAsState()
    val unreadCount by viewModel.unreadNotificationCount.collectAsState()
    val colors = dashColors()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(colors.background)
    ) {
        SubScreenHeader(
            title = "Notification History",
            subtitle = if (unreadCount > 0) "$unreadCount unread" else "${notifications.size} notifications",
            onBack = {
                hm.perform(HapticPattern.TAP)
                onBack()
            }
        )

        // Action bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(12.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Mark all read
            IconButton(
                onClick = {
                    hm.perform(HapticPattern.TAP)
                    viewModel.markAllNotificationsRead()
                }
            ) {
                Icon(
                    Icons.Default.DoneAll,
                    contentDescription = "Mark all read",
                    tint = if (unreadCount > 0) colors.cyanPrimary else colors.textMuted,
                    modifier = Modifier.size(22.dp)
                )
            }

            // Clear all
            IconButton(
                onClick = {
                    hm.perform(HapticPattern.DESTROY)
                    viewModel.clearAllNotifications()
                }
            ) {
                Icon(
                    Icons.Default.Delete,
                    contentDescription = "Clear all",
                    tint = colors.errorRed,
                    modifier = Modifier.size(22.dp)
                )
            }
        }

        // Show skeleton briefly during initial load
        var showSkeleton by remember { mutableStateOf(true) }
        LaunchedEffect(Unit) {
            kotlinx.coroutines.delay(1500)
            showSkeleton = false
        }

        if (showSkeleton && notifications.isEmpty()) {
            ShimmerListSkeleton(cardCount = 5)
        } else if (notifications.isEmpty()) {
            // Empty state
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.Notifications,
                        contentDescription = "Notifications",
                        tint = colors.textMuted,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(12.dp))
                    Text(
                        "No notifications yet",
                        color = colors.textMuted,
                        fontSize = 14.sp
                    )
                    Text(
                        "Desktop notifications will appear here",
                        color = colors.textMuted.copy(alpha = 0.85f),
                        fontSize = 12.sp
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.fillMaxSize(),
                contentPadding = androidx.compose.foundation.layout.PaddingValues(
                    horizontal = 16.dp,
                    vertical = 4.dp
                ),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(notifications, key = { it.id }) { notification ->
                    SwipeableNotificationItem(
                        notification = notification,
                        onMarkRead = {
                            hm.perform(HapticPattern.CONFIRM)
                            viewModel.markNotificationRead(notification.id)
                        },
                        onDelete = {
                            hm.perform(HapticPattern.DESTROY)
                            viewModel.deleteNotification(notification.id)
                        }
                    )
                }
            }
        }
    }
}

@Composable
private fun SwipeableNotificationItem(
    notification: NotificationEntity,
    onMarkRead: () -> Unit,
    onDelete: () -> Unit,
    modifier: Modifier = Modifier
) {
    val colors = dashColors()
    val timeText = formatNotificationTime(notification.timestamp)
    val swipeThreshold = 120f
    val scope = rememberCoroutineScope()
    val offsetX = remember { Animatable(0f) }
    var hasTriggered by remember { mutableStateOf(false) }

    // Reset trigger flag when offset returns to 0
    LaunchedEffect(offsetX.value) {
        if (kotlin.math.abs(offsetX.value) < 5f) hasTriggered = false
    }

    Box(
        modifier = modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
    ) {
        // Background reveal layer — two halves side by side
        Row(
            modifier = Modifier.fillMaxSize(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            // Right swipe → Mark read (green, left half)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxSize()
                    .background(colors.successGreen.copy(alpha = 0.15f)),
                contentAlignment = Alignment.CenterStart
            ) {
                Row(
                    modifier = Modifier.padding(start = 20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        Icons.Outlined.MarkEmailRead,
                        contentDescription = "Mark as read",
                        tint = colors.successGreen,
                        modifier = Modifier.size(20.dp)
                    )
                    Text(
                        text = "Mark read",
                        color = colors.successGreen,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                }
            }
            // Left swipe → Delete (red, right half)
            Box(
                modifier = Modifier
                    .weight(1f)
                    .fillMaxSize()
                    .background(colors.errorRed.copy(alpha = 0.15f)),
                contentAlignment = Alignment.CenterEnd
            ) {
                Row(
                    modifier = Modifier.padding(end = 20.dp),
                    verticalAlignment = Alignment.CenterVertically,
                    horizontalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Text(
                        text = "Delete",
                        color = colors.errorRed,
                        fontSize = 12.sp,
                        fontWeight = FontWeight.SemiBold
                    )
                    Icon(
                        Icons.Outlined.Archive,
                        contentDescription = "Archive",
                        tint = colors.errorRed,
                        modifier = Modifier.size(20.dp)
                    )
                }
            }
        }

        // Foreground card that slides
        GlassCard(
            modifier = Modifier
                .fillMaxWidth()
                .offset { IntOffset(offsetX.value.roundToInt(), 0) }
                .pointerInput(notification.id) {
                    detectHorizontalDragGestures(
                        onDragEnd = {
                            scope.launch {
                                val target = when {
                                    offsetX.value > swipeThreshold && !hasTriggered -> {
                                        hasTriggered = true
                                        onMarkRead()
                                        0f
                                    }
                                    offsetX.value < -swipeThreshold && !hasTriggered -> {
                                        hasTriggered = true
                                        onDelete()
                                        -size.width.toFloat()
                                    }
                                    else -> 0f
                                }
                                offsetX.animateTo(
                                    targetValue = target,
                                    animationSpec = spring(
                                        dampingRatio = Spring.DampingRatioMediumBouncy,
                                        stiffness = Spring.StiffnessMedium
                                    )
                                )
                                // If deleted, slide fully off then reset
                                if (target == -size.width.toFloat()) {
                                    // Card already removed by delete callback
                                }
                            }
                        },
                        onHorizontalDrag = { _, dragAmount ->
                            scope.launch {
                                val newValue = (offsetX.value + dragAmount).coerceIn(-swipeThreshold * 1.5f, swipeThreshold * 1.5f)
                                offsetX.snapTo(newValue)
                            }
                        }
                    )
                }
                .shadow(4.dp, RoundedCornerShape(16.dp))
                .clip(RoundedCornerShape(16.dp))
                .background(colors.surface),
            borderColor = if (!notification.isRead) colors.cyanPrimary.copy(alpha = 0.4f) else colors.borderGlass
        ) {
            Column(
                modifier = Modifier.padding(14.dp)
            ) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.Top
                ) {
                    // Unread indicator + title
                    Row(
                        modifier = Modifier.weight(1f),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        if (!notification.isRead) {
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(colors.cyanPrimary)
                            )
                            Spacer(modifier = Modifier.width(8.dp))
                        }
                        Text(
                            text = notification.title,
                            color = if (!notification.isRead) colors.textPrimary else colors.textSecondary,
                            fontSize = 14.sp,
                            fontWeight = if (!notification.isRead) FontWeight.SemiBold else FontWeight.Normal,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }

                    // Swipe hint
                    Text(
                        text = "swipe ← →",
                        color = colors.textMuted.copy(alpha = 0.75f),
                        fontSize = 9.sp,
                        modifier = Modifier.padding(start = 8.dp, top = 2.dp)
                    )
                }

                // Body
                if (notification.body.isNotBlank()) {
                    Text(
                        text = notification.body,
                        color = colors.textSecondary,
                        fontSize = 12.sp,
                        maxLines = 3,
                        overflow = TextOverflow.Ellipsis,
                        modifier = Modifier.padding(top = 4.dp)
                    )
                }

                // Timestamp + app name
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(top = 8.dp),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    if (notification.appName.isNotBlank()) {
                        Text(
                            text = notification.appName,
                            color = colors.textMuted,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Medium,
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(colors.surface)
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        )
                    }
                    Text(
                        text = timeText,
                        color = colors.textMuted,
                        fontSize = 10.sp
                    )
                }
            }
        }
    }
}

private fun formatNotificationTime(timestamp: Long): String {
    val now = System.currentTimeMillis()
    val diff = now - timestamp
    return when {
        diff < 60_000 -> "Just now"
        diff < 3_600_000 -> "${diff / 60_000}m ago"
        diff < 86_400_000 -> "${diff / 3_600_000}h ago"
        else -> {
            val sdf = SimpleDateFormat("MMM d, h:mm a", Locale.getDefault())
            sdf.format(Date(timestamp))
        }
    }
}
