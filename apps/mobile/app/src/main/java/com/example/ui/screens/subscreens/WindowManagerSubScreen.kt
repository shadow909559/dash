package com.example.ui.screens.subscreens

import androidx.compose.foundation.background
import androidx.compose.foundation.border
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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.CropFree
import androidx.compose.material.icons.filled.Fullscreen
import androidx.compose.material.icons.filled.Layers
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material.icons.filled.ViewCompact
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.DashApiService
import com.example.ui.components.GlassCard
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

@Composable
fun WindowManagerSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var windowsList by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }

    fun loadWindows() {
        scope.launch {
            isLoading = true
            error = null
            try {
                val response = DashApiService.listWindows()
                val details = response.details
                @Suppress("UNCHECKED_CAST")
                val wins = details["windows"] as? List<Map<String, Any>> ?: emptyList()
                windowsList = wins
            } catch (e: Exception) {
                error = e.message ?: "Failed to load windows"
            }
            isLoading = false
        }
    }

    // Auto-load windows on entry
    androidx.compose.runtime.LaunchedEffect(Unit) {
        loadWindows()
    }

    fun focusWindow(title: String) {
        scope.launch { viewModel.focusWindow(title) }
    }

    fun closeWindow(title: String) {
        scope.launch { viewModel.closeWindow(title) }
    }

    fun minimizeWindow(title: String) {
        scope.launch { viewModel.minimizeWindow(title) }
    }

    fun maximizeWindow(title: String) {
        scope.launch { viewModel.maximizeWindow(title) }
    }

    remember { loadWindows(); Unit }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("window_manager_screen")
    ) {
        SubScreenHeader(
            title = "Window Manager",
            subtitle = "List & control windows",
            subtitleColor = DashPurpleSecondary,
            onBack = onBack
        )

        when {
            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = DashCyanPrimary, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Scanning windows...", color = dashColors().textSecondary)
                    }
                }
            }
            error != null -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Text("Error", color = DashErrorRed, fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(error ?: "", color = dashColors().textSecondary)
                    }
                }
            }
            windowsList.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Text("No windows found", color = dashColors().textMuted)
                }
            }
            else -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                    contentPadding = PaddingValues(top = 12.dp, bottom = 100.dp),
                    verticalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    items(windowsList.size) { index ->
                        val win = windowsList[index]
                        val title = win["title"] as? String ?: win["name"] as? String ?: "Unknown"
                        val process = win["process"] as? String ?: win["process_name"] as? String ?: ""
                        val isActive = win["active"] as? Boolean ?: false

                        WindowCard(
                            title = title,
                            process = process,
                            isActive = isActive,
                            onFocus = { focusWindow(title) },
                            onClose = { closeWindow(title) },
                            onMinimize = { minimizeWindow(title) },
                            onMaximize = { maximizeWindow(title) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun WindowCard(
    title: String,
    process: String,
    isActive: Boolean,
    onFocus: () -> Unit,
    onClose: () -> Unit,
    onMinimize: () -> Unit,
    onMaximize: () -> Unit
) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 16.dp,
        borderColor = if (isActive) DashCyanPrimary.copy(alpha = 0.4f) else dashColors().borderGlass,
        backgroundColor = if (isActive) DashCyanPrimary.copy(alpha = 0.06f) else dashColors().surfaceContainerLow.copy(alpha = 0.7f)
    ) {
        Column(
            modifier = Modifier.fillMaxWidth().padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(10.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier.size(36.dp).clip(CircleShape).background(DashPurpleSecondary.copy(alpha = 0.12f)),
                    contentAlignment = Alignment.Center
                ) {
                    Icon(Icons.Default.Layers, null, tint = DashPurpleSecondary, modifier = Modifier.size(18.dp))
                }
                Spacer(modifier = Modifier.width(10.dp))
                Column(modifier = Modifier.weight(1f)) {
                    Text(title, style = MaterialTheme.typography.bodyLarge, fontWeight = FontWeight.SemiBold,
                        color = dashColors().textPrimary, maxLines = 1, overflow = TextOverflow.Ellipsis)
                    if (process.isNotBlank()) {
                        Text(process, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = dashColors().textMuted)
                    }
                }
                if (isActive) {
                    Box(
                        modifier = Modifier.clip(CircleShape).background(DashCyanPrimary.copy(alpha = 0.15f)).padding(horizontal = 8.dp, vertical = 3.dp)
                    ) {
                        Text("ACTIVE", fontSize = 9.sp, fontWeight = FontWeight.Bold, color = DashCyanPrimary)
                    }
                }
            }

            // Action buttons
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                WindowActionButton("Focus", DashCyanPrimary, Icons.Default.CropFree, onFocus)
                WindowActionButton("Minimize", dashColors().textSecondary, Icons.Default.ViewCompact, onMinimize)
                WindowActionButton("Maximize", dashColors().textSecondary, Icons.Default.Fullscreen, onMaximize)
                WindowActionButton("Close", DashErrorRed, Icons.Default.Close, onClose)
            }
        }
    }
}

@Composable
private fun WindowActionButton(label: String, color: Color, icon: androidx.compose.ui.graphics.vector.ImageVector, onClick: () -> Unit) {
    IconButton(
        onClick = onClick,
        modifier = Modifier
            .size(36.dp)
            .clip(RoundedCornerShape(10.dp))
            .background(color.copy(alpha = 0.1f))
            .border(1.dp, color.copy(alpha = 0.2f), RoundedCornerShape(10.dp))
    ) {
        Icon(icon, label, tint = color, modifier = Modifier.size(16.dp))
    }
}
