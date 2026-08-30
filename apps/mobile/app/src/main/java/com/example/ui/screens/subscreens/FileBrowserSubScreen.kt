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
import androidx.compose.material.icons.automirrored.filled.NavigateNext
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Folder
import androidx.compose.material.icons.filled.Image
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Terminal
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
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.DashApiService
import com.example.data.api.FileItem
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
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

@Composable
fun FileBrowserSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var files by remember { mutableStateOf<List<FileItem>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var error by remember { mutableStateOf<String?>(null) }
    var currentPath by remember { mutableStateOf<String?>(null) }
    var parentPath by remember { mutableStateOf<String?>(null) }
    var searchQuery by remember { mutableStateOf("") }
    var isSearchMode by remember { mutableStateOf(false) }
    var pathHistory by remember { mutableStateOf<List<String>>(emptyList()) }

    fun loadFiles(path: String? = null) {
        scope.launch {
            isLoading = true
            error = null
            try {
                val response = DashApiService.browseFiles(path)
                files = response.files
                val newPath = response.path
                parentPath = response.parent
                if (newPath != null) {
                    currentPath = newPath
                    if (pathHistory.isEmpty() || pathHistory.last() != newPath) {
                        pathHistory = pathHistory + newPath
                    }
                }
            } catch (e: Exception) {
                error = e.message ?: "Failed to browse files"
            }
            isLoading = false
        }
    }

    fun searchFiles(query: String) {
        scope.launch {
            isLoading = true
            error = null
            try {
                val response = DashApiService.searchFiles(query)
                files = response.files
            } catch (e: Exception) {
                error = e.message ?: "Search failed"
            }
            isLoading = false
        }
    }

    // Initial load
    remember { loadFiles(null); Unit }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("file_browser_screen")
    ) {
        SubScreenHeader(
            title = "File Browser",
            subtitle = "Browse desktop files",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        // Breadcrumb path chips
        if (currentPath != null && !isSearchMode) {
            LazyRow(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                horizontalArrangement = Arrangement.spacedBy(4.dp)
            ) {
                val segments = currentPath!!.replace("\\", "/").split("/").filter { it.isNotBlank() }
                item {
                    Box(
                        modifier = Modifier
                            .clip(RoundedCornerShape(10.dp))
                            .background(DashCyanPrimary.copy(alpha = 0.1f))
                            .border(1.dp, DashCyanPrimary.copy(alpha = 0.25f), RoundedCornerShape(10.dp))
                            .clickable { loadFiles(null) }
                            .padding(horizontal = 10.dp, vertical = 4.dp)
                    ) {
                        Text("Root", fontSize = 10.sp, fontFamily = FontFamily.Monospace, color = DashCyanPrimary)
                    }
                }
                items(segments.size) { index ->
                    Row(verticalAlignment = Alignment.CenterVertically) {
                        Icon(
                            Icons.AutoMirrored.Filled.NavigateNext,
                            null,
                            tint = dashColors().textMuted.copy(alpha = 0.5f),
                            modifier = Modifier.size(12.dp)
                        )
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(10.dp))
                                .background(
                                    if (index == segments.lastIndex) DashCyanPrimary.copy(alpha = 0.15f)
                                    else Color.White.copy(alpha = 0.04f)
                                )
                                .border(
                                    1.dp,
                                    if (index == segments.lastIndex) DashCyanPrimary.copy(alpha = 0.3f)
                                    else Color.White.copy(alpha = 0.08f),
                                    RoundedCornerShape(10.dp)
                                )
                                .clickable {
                                    val pathToNav = segments.take(index + 1).joinToString("/")
                                    loadFiles(pathToNav)
                                }
                                .padding(horizontal = 10.dp, vertical = 4.dp)
                        ) {
                            Text(
                                segments[index],
                                fontSize = 10.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = if (index == segments.lastIndex) FontWeight.Bold else FontWeight.Normal,
                                color = if (index == segments.lastIndex) DashCyanPrimary else dashColors().textSecondary
                            )
                        }
                    }
                }
            }
        }

        if (isSearchMode) {
            OutlinedTextField(
                value = searchQuery,
                onValueChange = { searchQuery = it },
                placeholder = { Text("Search files...", color = dashColors().textMuted) },
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 8.dp),
                shape = RoundedCornerShape(14.dp),
                singleLine = true,
                colors = OutlinedTextFieldDefaults.colors(
                    focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                    focusedTextColor = dashColors().textPrimary, unfocusedTextColor = dashColors().textPrimary,
                    focusedContainerColor = dashColors().surface.copy(alpha = 0.5f),
                    unfocusedContainerColor = dashColors().surface.copy(alpha = 0.5f)
                ),
                trailingIcon = {
                    IconButton(onClick = { if (searchQuery.isNotBlank()) searchFiles(searchQuery) }) {
                        Icon(Icons.Default.Search, "Search", tint = DashCyanPrimary)
                    }
                }
            )
        }

        when {
            isLoading -> {
                Box(modifier = Modifier.fillMaxSize(), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        CircularProgressIndicator(color = DashCyanPrimary, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Scanning filesystem...", color = dashColors().textSecondary)
                    }
                }
            }
            error != null -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.Search, null, tint = DashErrorRed, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(12.dp))
                        Text("Access Denied or Error", color = DashErrorRed, fontWeight = FontWeight.Bold)
                        Spacer(modifier = Modifier.height(4.dp))
                        Text(error ?: "", color = dashColors().textSecondary, fontSize = 12.sp)
                    }
                }
            }
            files.isEmpty() -> {
                Box(modifier = Modifier.fillMaxSize().padding(32.dp), contentAlignment = Alignment.Center) {
                    Column(horizontalAlignment = Alignment.CenterHorizontally) {
                        Icon(Icons.Default.Folder, null, tint = dashColors().textMuted, modifier = Modifier.size(48.dp))
                        Spacer(modifier = Modifier.height(8.dp))
                        Text("No files found", color = dashColors().textMuted)
                    }
                }
            }
            else -> {
                // File count badge
                Row(
                    modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 6.dp),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "${files.size} items",
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
                    if (files.isEmpty()) {
                        item { ShimmerListSkeleton(cardCount = 6) }
                    }
                    items(files, key = { it.path }) { file ->
                        FileItemCard(file = file, onClick = {
                            if (file.type == "directory") loadFiles(file.path)
                        })
                    }
                }
            }
        }
    }
}

private fun getFileTypeIcon(file: FileItem): ImageVector {
    if (file.type == "directory") return Icons.Default.Folder
    val ext = file.name.substringAfterLast('.', "").lowercase()
    return when (ext) {
        "kt", "java", "py", "js", "ts", "tsx", "jsx", "go", "rs", "c", "cpp", "h" -> Icons.Default.Code
        "png", "jpg", "jpeg", "gif", "bmp", "svg", "webp" -> Icons.Default.Image
        "bat", "ps1", "sh", "cmd", "zsh", "fish" -> Icons.Default.Terminal
        else -> Icons.Default.Description
    }
}

private fun getFileTypeColor(file: FileItem): Color {
    if (file.type == "directory") return DashCyanPrimary
    val ext = file.name.substringAfterLast('.', "").lowercase()
    return when (ext) {
        "kt", "java" -> Color(0xFF7C4DFF)
        "py" -> Color(0xFFFFD54F)
        "js", "ts", "tsx", "jsx" -> Color(0xFFFFEB3B)
        "go", "rs" -> Color(0xFF00BCD4)
        "png", "jpg", "jpeg", "gif", "svg" -> DashPurpleSecondary
        "bat", "ps1", "sh", "cmd" -> DashSuccessGreen
        "json", "yaml", "yml", "toml", "xml" -> DashPurpleSecondary
        "md", "txt", "log" -> Color(0xFF8B92A8)
        else -> DashPurpleSecondary
    }
}

@Composable
private fun FileItemCard(file: FileItem, onClick: () -> Unit) {
    val isDir = file.type == "directory"
    val icon = getFileTypeIcon(file)
    val accentColor = getFileTypeColor(file)

    GlassCard(modifier = Modifier.fillMaxWidth(), cornerRadius = 14.dp, onClick = onClick) {
        Row(
            modifier = Modifier.fillMaxWidth().padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier.size(38.dp).clip(CircleShape).background(accentColor.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = icon,
                    contentDescription = null, tint = accentColor, modifier = Modifier.size(18.dp)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    file.name,
                    style = MaterialTheme.typography.bodyLarge,
                    fontWeight = FontWeight.SemiBold,
                    color = dashColors().textPrimary,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )
                Row(verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                    if (!isDir && file.size > 0) {
                        Text(formatFileSize(file.size), fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = dashColors().textMuted)
                    }
                    val ext = file.name.substringAfterLast('.', "").lowercase()
                    if (ext.isNotBlank() && !isDir) {
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(4.dp))
                                .background(accentColor.copy(alpha = 0.1f))
                                .padding(horizontal = 6.dp, vertical = 2.dp)
                        ) {
                            Text(
                                text = ext.uppercase(),
                                fontSize = 9.sp,
                                fontFamily = FontFamily.Monospace,
                                fontWeight = FontWeight.Bold,
                                color = accentColor
                            )
                        }
                    }
                }
            }
            if (isDir) {
                Icon(Icons.AutoMirrored.Filled.NavigateNext, "Open", tint = dashColors().textMuted, modifier = Modifier.size(18.dp))
            }
        }
    }
}

private fun formatFileSize(bytes: Long): String = when {
    bytes < 1024 -> "$bytes B"
    bytes < 1048576 -> "${bytes / 1024} KB"
    bytes < 1073741824 -> "${bytes / 1048576} MB"
    else -> "${bytes / 1073741824} GB"
}
