package com.example.ui.screens.subscreens

import android.util.Log
import androidx.compose.foundation.background
import androidx.compose.ui.platform.LocalContext
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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Share
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextField
import androidx.compose.material3.TextFieldDefaults
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.websocket.WebSocketManager
import com.example.ui.components.GlassCard
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.theme.DashWarningAmber
import com.example.ui.theme.dashColors

private val LOG_COMPONENTS = listOf(
    "backend" to "Backend",
    "voice" to "Voice",
    "automation" to "Automation",
    "agents" to "Agents",
    "system" to "System",
)

@Composable
fun DiagnosticsSubScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val haptic = LocalHapticFeedback.current
    val hm = LocalHapticManager.current
    val context = LocalContext.current
    val logLines by WebSocketManager.logLines.collectAsState()
    val logSubscribed by WebSocketManager.logSubscribed.collectAsState()
    var selectedComponent by remember { mutableStateOf("backend") }
    var searchQuery by remember { mutableStateOf("") }
    // Multi-select level toggles — all enabled by default
    var enabledLevels by remember { mutableStateOf(setOf("ERROR", "WARN", "INFO", "DEBUG")) }
    val listState = rememberLazyListState()

    // Filter logs by keyword and enabled levels
    val filteredLines = remember(logLines, searchQuery, enabledLevels) {
        logLines.filter { line ->
            // Keyword filter
            val matchesQuery = searchQuery.isBlank() || line.contains(searchQuery, ignoreCase = true)
            // Level filter — show if ANY enabled level matches
            val matchesLevel = enabledLevels.any { level ->
                line.contains(level, ignoreCase = true)
            }
            matchesQuery && matchesLevel
        }
    }

    // Subscribe to logs on first load
    LaunchedEffect(Unit) {
        WebSocketManager.subscribeToLogs(selectedComponent)
    }

    // Re-subscribe when component changes
    LaunchedEffect(selectedComponent) {
        WebSocketManager.clearLogs()
        WebSocketManager.subscribeToLogs(selectedComponent)
    }

    // Auto-scroll to bottom when new lines arrive (only when no filter active)
    LaunchedEffect(logLines.size) {
        if (logLines.isNotEmpty() && searchQuery.isBlank() && enabledLevels.size == 4) {
            listState.animateScrollToItem(filteredLines.size - 1)
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
    ) {
        SubScreenHeader(
            title = "Live Logs",
            subtitle = if (logSubscribed) "Streaming ${LOG_COMPONENTS.firstOrNull { it.first == selectedComponent }?.second ?: selectedComponent}" else "Connecting...",
            onBack = {
                haptic.performHapticFeedback(HapticFeedbackType.LongPress)
                onBack()
            }
        )

        // Component selector tabs
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 8.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            LOG_COMPONENTS.forEach { (key, label) ->
                val isSelected = key == selectedComponent
                Box(
                    modifier = Modifier
                        .weight(1f)
                        .clip(RoundedCornerShape(8.dp))
                        .background(
                            if (isSelected) DashCyanPrimary.copy(alpha = 0.15f)
                            else Color.White.copy(alpha = 0.04f)
                        )
                        .border(
                            1.dp,
                            if (isSelected) DashCyanPrimary.copy(alpha = 0.5f) else Color.White.copy(alpha = 0.08f),
                            RoundedCornerShape(8.dp)
                        )
                        .clickable {
                            hm.perform(HapticPattern.TAP)
                            selectedComponent = key
                        }
                        .padding(horizontal = 4.dp, vertical = 6.dp),
                    contentAlignment = Alignment.Center
                ) {
                    Text(
                        text = label,
                        fontSize = 10.sp,
                        fontWeight = if (isSelected) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (isSelected) DashCyanPrimary else dashColors().textSecondary
                    )
                }
            }
        }

        // Search bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            TextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = {
                    Text(
                        text = "Search logs...",
                        fontSize = 12.sp,
                        color = dashColors().textMuted
                    )
                },
                leadingIcon = {
                    Icon(
                        Icons.Default.Search,
                        contentDescription = "Search",
                        tint = dashColors().textMuted,
                        modifier = Modifier.size(18.dp)
                    )
                },
                trailingIcon = {
                    if (searchQuery.isNotEmpty()) {
                        IconButton(onClick = { searchQuery = "" }, modifier = Modifier.size(20.dp)) {
                            Icon(
                                Icons.Default.Close,
                                contentDescription = "Clear",
                                tint = dashColors().textMuted,
                                modifier = Modifier.size(14.dp)
                            )
                        }
                    }
                },
                singleLine = true,
                colors = TextFieldDefaults.colors(
                    focusedContainerColor = Color.White.copy(alpha = 0.04f),
                    unfocusedContainerColor = Color.White.copy(alpha = 0.04f),
                    focusedIndicatorColor = Color.Transparent,
                    unfocusedIndicatorColor = Color.Transparent,
                    cursorColor = DashCyanPrimary
                ),
                textStyle = androidx.compose.ui.text.TextStyle(
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace,
                    color = dashColors().textPrimary
                ),
                modifier = Modifier
                    .weight(1f)
                    .clip(RoundedCornerShape(8.dp))
            )
        }

        // Level filter toggle buttons (multi-select)
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 2.dp),
            horizontalArrangement = Arrangement.spacedBy(4.dp)
        ) {
            val levels = listOf(
                "ERROR" to DashErrorRed,
                "WARN" to DashWarningAmber,
                "INFO" to DashSuccessGreen,
                "DEBUG" to dashColors().textMuted
            )
            levels.forEach { (level, chipColor) ->
                val isEnabled = level in enabledLevels
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(6.dp))
                        .background(
                            if (isEnabled) chipColor.copy(alpha = 0.2f)
                            else Color.White.copy(alpha = 0.04f)
                        )
                        .border(
                            1.dp,
                            if (isEnabled) chipColor.copy(alpha = 0.5f) else Color.White.copy(alpha = 0.06f),
                            RoundedCornerShape(6.dp)
                        )
                        .clickable {
                            hm.perform(HapticPattern.TAP)
                            enabledLevels = if (isEnabled) enabledLevels - level
                            else enabledLevels + level
                        }
                        .padding(horizontal = 8.dp, vertical = 3.dp)
                ) {
                    Text(
                        text = level,
                        fontSize = 9.sp,
                        fontWeight = if (isEnabled) FontWeight.SemiBold else FontWeight.Normal,
                        color = if (isEnabled) chipColor else dashColors().textMuted,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
            // Select All / None
            Box(
                modifier = Modifier
                    .clip(RoundedCornerShape(6.dp))
                    .background(Color.White.copy(alpha = 0.04f))
                    .border(1.dp, Color.White.copy(alpha = 0.06f), RoundedCornerShape(6.dp))
                    .clickable {
                        hm.perform(HapticPattern.TAP)
                        enabledLevels = if (enabledLevels.size == 4) emptySet()
                        else setOf("ERROR", "WARN", "INFO", "DEBUG")
                    }
                    .padding(horizontal = 8.dp, vertical = 3.dp)
            ) {
                Text(
                    text = if (enabledLevels.size == 4) "NONE" else "ALL",
                    fontSize = 9.sp,
                    fontWeight = FontWeight.SemiBold,
                    color = DashCyanPrimary,
                    fontFamily = FontFamily.Monospace
                )
            }
            // Match count
            Spacer(modifier = Modifier.weight(1f))
            if (searchQuery.isNotEmpty() || enabledLevels.size < 4) {
                Text(
                    text = "${filteredLines.size}/${logLines.size}",
                    fontSize = 10.sp,
                    color = dashColors().textMuted,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        // Log actions bar
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 2.dp),
            horizontalArrangement = Arrangement.SpaceBetween,
            verticalAlignment = Alignment.CenterVertically
        ) {
            Text(
                text = "${filteredLines.size} lines${if (searchQuery.isNotEmpty() || enabledLevels.size < 4) " (filtered)" else ""}",
                fontSize = 11.sp,
                color = dashColors().textMuted,
                fontFamily = FontFamily.Monospace
            )
            Row {
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        WebSocketManager.clearLogs()
                        WebSocketManager.subscribeToLogs(selectedComponent)
                    },
                    modifier = Modifier.size(28.dp)
                ) {
                    Icon(
                        Icons.Default.Refresh,
                        contentDescription = "Refresh",
                        tint = DashCyanPrimary,
                        modifier = Modifier.size(16.dp)
                    )
                }
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        // Export filtered logs as text file
                        val timestamp = java.text.SimpleDateFormat("yyyy-MM-dd_HH-mm-ss", java.util.Locale.US).format(java.util.Date())
                        val header = buildString {
                            appendLine("DASH Log Export")
                            appendLine("Component: ${LOG_COMPONENTS.firstOrNull { it.first == selectedComponent }?.second ?: selectedComponent}")
                            appendLine("Exported: $timestamp")
                            appendLine("Lines: ${filteredLines.size}/${logLines.size}")
                            if (searchQuery.isNotBlank()) appendLine("Search: $searchQuery")
                            if (enabledLevels.size < 4) appendLine("Levels: ${enabledLevels.joinToString(", ")}")
                            appendLine("─".repeat(60))
                        }
                        val content = header + filteredLines.joinToString("\n")
                        val fileName = "dash_logs_${selectedComponent}_${timestamp}.txt"

                        // Save to Downloads via MediaStore
                        try {
                                val values = android.content.ContentValues().apply {
                                    put(android.provider.MediaStore.Downloads.DISPLAY_NAME, fileName)
                                    put(android.provider.MediaStore.Downloads.MIME_TYPE, "text/plain")
                                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                                        put(android.provider.MediaStore.Downloads.IS_PENDING, 1)
                                    }
                                }
                                val uri = context.contentResolver.insert(
                                    android.provider.MediaStore.Downloads.EXTERNAL_CONTENT_URI,
                                    values
                                )
                                uri?.let {
                                    context.contentResolver.openOutputStream(it)?.use { stream ->
                                        stream.write(content.toByteArray())
                                    }
                                    if (android.os.Build.VERSION.SDK_INT >= android.os.Build.VERSION_CODES.Q) {
                                        values.clear()
                                        values.put(android.provider.MediaStore.Downloads.IS_PENDING, 0)
                                        context.contentResolver.update(it, values, null, null)
                                    }
                                }
                                // Share via intent as well
                                val shareIntent = android.content.Intent(android.content.Intent.ACTION_SEND).apply {
                                    type = "text/plain"
                                    putExtra(android.content.Intent.EXTRA_TEXT, content)
                                    putExtra(android.content.Intent.EXTRA_SUBJECT, "DASH Logs - ${selectedComponent}")
                                }
                                context.startActivity(android.content.Intent.createChooser(shareIntent, "Export Logs"))
                            } catch (e: Exception) {
                                Log.e("Diagnostics", "Failed to export logs", e)
                            }
                    },
                    modifier = Modifier.size(28.dp)
                ) {
                    Icon(
                        Icons.Default.Share,
                        contentDescription = "Export logs",
                        tint = DashSuccessGreen,
                        modifier = Modifier.size(16.dp)
                    )
                }
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.DESTROY)
                        WebSocketManager.clearLogs()
                    },
                    modifier = Modifier.size(28.dp)
                ) {
                    Icon(
                        Icons.Default.Delete,
                        contentDescription = "Clear",
                        tint = DashErrorRed,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }
        }

        // Log viewer
        GlassCard(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp, vertical = 4.dp),
            backgroundColor = dashColors().surface.copy(alpha = 0.95f),
            cornerRadius = 12.dp
        ) {
            if (logLines.isEmpty()) {
                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center
                ) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text(
                            text = if (logSubscribed) "Waiting for logs..." else "Connecting to backend...",
                            color = dashColors().textMuted,
                            fontSize = 13.sp
                        )
                        if (!logSubscribed) {
                            Spacer(modifier = Modifier.height(8.dp))
                            Box(
                                modifier = Modifier
                                    .size(8.dp)
                                    .clip(CircleShape)
                                    .background(DashWarningAmber)
                            )
                        }
                    }
                }
            } else {
                LazyColumn(
                    state = listState,
                    modifier = Modifier.fillMaxSize(),
                    contentPadding = PaddingValues(8.dp),
                    verticalArrangement = Arrangement.spacedBy(1.dp)
                ) {
                    // No match state
                    if (logLines.isNotEmpty() && filteredLines.isEmpty()) {
                        item {
                            Box(
                                modifier = Modifier.fillMaxWidth().padding(24.dp),
                                contentAlignment = Alignment.Center
                            ) {
                                Text(
                                    text = "No matching logs",
                                    color = dashColors().textMuted,
                                    fontSize = 12.sp,
                                    fontFamily = FontFamily.Monospace
                                )
                            }
                        }
                    }
                    items(filteredLines, key = { "${logLines.indexOf(it)}_$it" }) { line ->
                        LogLine(line)
                    }
                }
            }
        }
    }
}

@Composable
private fun LogLine(line: String) {
    // Color-code based on log level
    val color = when {
        line.contains("ERROR", ignoreCase = true) || line.contains("FATAL", ignoreCase = true) -> DashErrorRed
        line.contains("WARNING", ignoreCase = true) || line.contains("WARN", ignoreCase = true) -> DashWarningAmber
        line.contains("DEBUG", ignoreCase = true) -> dashColors().textMuted
        line.contains("INFO", ignoreCase = true) -> DashSuccessGreen
        else -> dashColors().textSecondary
    }

    Text(
        text = line,
        color = color,
        fontSize = 10.sp,
        fontFamily = FontFamily.Monospace,
        lineHeight = 14.sp,
        maxLines = 3,
        overflow = TextOverflow.Ellipsis,
        modifier = Modifier
            .fillMaxWidth()
            .padding(horizontal = 4.dp, vertical = 1.dp)
    )
}
