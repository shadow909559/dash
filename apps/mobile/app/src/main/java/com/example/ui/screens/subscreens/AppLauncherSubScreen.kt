package com.example.ui.screens.subscreens

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
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Apps
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Launch
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
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
import com.example.data.api.AppInfo
import com.example.data.api.DashApiService
import com.example.ui.components.GlassCard
import com.example.ui.components.ShimmerListSkeleton
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

private data class QuickLaunchApp(
    val name: String,
    val displayName: String,
    val color: Color
)

@Composable
fun AppLauncherSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var searchQuery by remember { mutableStateOf("") }
    var apps by remember { mutableStateOf<List<AppInfo>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var hasSearched by remember { mutableStateOf(false) }
    var launchFeedback by remember { mutableStateOf<String?>(null) }

    val quickLaunchApps = listOf(
        QuickLaunchApp("chrome", "Chrome", Color(0xFF4285F4)),
        QuickLaunchApp("code", "VS Code", Color(0xFF007ACC)),
        QuickLaunchApp("explorer", "Explorer", DashCyanPrimary),
        QuickLaunchApp("notepad", "Notepad", dashColors().textSecondary),
        QuickLaunchApp("cmd", "Terminal", DashSuccessGreen),
        QuickLaunchApp("spotify", "Spotify", Color(0xFF1DB954)),
        QuickLaunchApp("discord", "Discord", Color(0xFF5865F2)),
        QuickLaunchApp("slack", "Slack", Color(0xFF4A154B)),
    )

    fun searchApps(query: String) {
        scope.launch {
            isLoading = true
            error = null
            launchFeedback = null
            try {
                apps = DashApiService.searchApplications(query)
                hasSearched = true
            } catch (e: Exception) {
                error = e.message ?: "Search failed"
            }
            isLoading = false
        }
    }

    fun launchApp(name: String) {
        scope.launch {
            try {
                DashApiService.launchApplication(name)
                launchFeedback = "Launched $name"
            } catch (e: Exception) {
                launchFeedback = "Failed: ${e.message}"
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("app_launcher_screen")
    ) {
        SubScreenHeader(
            title = "Application Launcher",
            subtitle = "Search & launch apps",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        // Search bar
        OutlinedTextField(
            value = searchQuery,
            onValueChange = { searchQuery = it },
            placeholder = { Text("Search applications...", color = dashColors().textMuted) },
            modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
            shape = RoundedCornerShape(14.dp),
            singleLine = true,
            colors = OutlinedTextFieldDefaults.colors(
                focusedBorderColor = DashCyanPrimary,
                unfocusedBorderColor = dashColors().borderGlass,
                focusedTextColor = dashColors().textPrimary,
                unfocusedTextColor = dashColors().textPrimary,
                focusedContainerColor = dashColors().surface.copy(alpha = 0.5f),
                unfocusedContainerColor = dashColors().surface.copy(alpha = 0.5f)
            ),
            trailingIcon = {
                IconButton(onClick = { if (searchQuery.isNotBlank()) searchApps(searchQuery) }) {
                    Icon(Icons.Default.Search, "Search", tint = DashCyanPrimary)
                }
            }
        )

        // Launch feedback
        launchFeedback?.let {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(
                        if (it.startsWith("Launched")) DashSuccessGreen.copy(alpha = 0.1f)
                        else DashErrorRed.copy(alpha = 0.1f)
                    )
                    .padding(10.dp)
            ) {
                Text(
                    text = it,
                    color = if (it.startsWith("Launched")) DashSuccessGreen else DashErrorRed,
                    fontSize = 12.sp,
                    fontFamily = FontFamily.Monospace
                )
            }
        }

        when {
            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = DashCyanPrimary, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Searching applications...", color = dashColors().textSecondary)
                    }
                }
            }
            error != null -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.Search, contentDescription = "Search error", tint = DashErrorRed, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Error", color = DashErrorRed, fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(error ?: "", color = dashColors().textSecondary)
                    }
                }
            }
            !hasSearched -> {
                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                    contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
                    verticalArrangement = Arrangement.spacedBy(14.dp)
                ) {
                    // Popular Quick Launch Section
                    item {
                        Text(
                            text = "QUICK LAUNCH",
                            fontSize = 10.sp,
                            color = dashColors().textMuted,
                            letterSpacing = 1.5.sp
                        )
                        Spacer(modifier = Modifier.height(6.dp))
                        LazyRow(
                            horizontalArrangement = Arrangement.spacedBy(10.dp)
                        ) {
                            items(quickLaunchApps) { app ->
                                QuickLaunchChip(
                                    name = app.displayName,
                                    color = app.color,
                                    onClick = { launchApp(app.name) }
                                )
                            }
                        }
                    }

                    item {
                        GlassCard(modifier = Modifier.fillMaxWidth()) {
                            Column(
                                modifier = Modifier.fillMaxWidth().padding(24.dp),
                                horizontalAlignment = Alignment.CenterHorizontally,
                                verticalArrangement = Arrangement.spacedBy(8.dp)
                            ) {
                                Icon(
                                    Icons.Default.Apps,
                                    null,
                                    tint = dashColors().textMuted,
                                    modifier = Modifier.size(48.dp)
                                )
                                Text(
                                    "Type to search for applications",
                                    color = dashColors().textPrimary,
                                    fontWeight = FontWeight.SemiBold
                                )
                                Text(
                                    "e.g. Chrome, VS Code, Terminal",
                                    fontSize = 12.sp,
                                    color = dashColors().textMuted
                                )
                            }
                        }
                    }
                }
            }
            apps.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.Apps, contentDescription = "No apps found", tint = dashColors().textMuted, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("No applications found", color = dashColors().textMuted)
                    }
                }
            }
            else -> {
                // Result count
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${apps.size} applications found",
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        color = dashColors().textMuted,
                        letterSpacing = 1.sp
                    )
                }

                LazyColumn(
                    modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
                    contentPadding = PaddingValues(top = 4.dp, bottom = 100.dp),
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    // Skeleton loading
                    if (apps.isEmpty()) {
                        item { ShimmerListSkeleton(cardCount = 6) }
                    }
                    items(apps, key = { it.name + it.path }) { app ->
                        AppCard(
                            app = app,
                            onLaunch = { launchApp(app.name) }
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun QuickLaunchChip(name: String, color: Color, onClick: () -> Unit) {
    Box(
        modifier = Modifier
            .clip(RoundedCornerShape(16.dp))
            .background(color.copy(alpha = 0.12f))
            .border(1.dp, color.copy(alpha = 0.3f), RoundedCornerShape(16.dp))
            .clickable { onClick() }
            .padding(horizontal = 16.dp, vertical = 10.dp)
    ) {
        Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(6.dp)) {
            Box(modifier = Modifier.size(8.dp).clip(CircleShape).background(color))
            Text(
                text = name,
                fontSize = 12.sp,
                fontWeight = FontWeight.SemiBold,
                color = color
            )
        }
    }
}

@Composable
private fun AppCard(app: AppInfo, onLaunch: () -> Unit) {
    GlassCard(modifier = Modifier.fillMaxWidth(), cornerRadius = 14.dp) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier.size(38.dp).clip(CircleShape).background(DashPurpleSecondary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(Icons.Default.Apps, contentDescription = "Category", tint = DashPurpleSecondary, modifier = Modifier.size(18.dp))
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    app.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = dashColors().textPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                if (app.path.isNotBlank()) {
                    Text(
                        app.path,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        color = dashColors().textMuted,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }
            }
            IconButton(
                onClick = onLaunch,
                modifier = Modifier
                    .size(36.dp)
                    .clip(RoundedCornerShape(10.dp))
                    .background(DashCyanPrimary.copy(alpha = 0.12f))
                    .border(1.dp, DashCyanPrimary.copy(alpha = 0.25f), RoundedCornerShape(10.dp))
            ) {
                Icon(Icons.Default.Launch, "Launch", tint = DashCyanPrimary, modifier = Modifier.size(16.dp))
            }
        }
    }
}
