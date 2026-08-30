package com.example.ui.screens.subscreens

import androidx.compose.animation.animateContentSize
import androidx.compose.foundation.background
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.*
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.vector.ImageVector
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.platform.LocalFocusManager
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.DashApiService
import com.example.data.config.AppConfig
import com.example.data.websocket.WebSocketManager
import com.example.ui.components.GlassCard
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.*
import kotlinx.coroutines.delay
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors

/**
 * Complete Command Center — full remote control of the desktop from Android.
 * Keyboard, mouse, files, apps, clipboard, screenshot, notifications, task execution.
 */
@Composable
fun CommandCenterScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    val focusManager = LocalFocusManager.current

    var selectedTab by remember { mutableIntStateOf(0) }
    val tabs = listOf("Keyboard", "Mouse", "Files", "Apps", "Clipboard", "Tasks")

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
    ) {
        SubScreenHeader(
            title = "Command Center",
            subtitle = "Full desktop control",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        // Tab bar
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(tabs.size) { index ->
                val isSelected = selectedTab == index
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(20.dp))
                        .background(if (isSelected) DashCyanPrimary.copy(alpha = 0.15f) else dashColors().surfaceContainer)
                        .clickable { selectedTab = index }
                        .padding(horizontal = 16.dp, vertical = 8.dp)
                ) {
                    Text(
                        text = tabs[index],
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Medium,
                        color = if (isSelected) DashCyanPrimary else dashColors().textMuted
                    )
                }
            }
        }

        Spacer(Modifier.height(12.dp))

        // Content
        when (selectedTab) {
            0 -> KeyboardTab(scope)
            1 -> MouseTab(scope)
            2 -> FilesTab(scope)
            3 -> AppsTab(scope)
            4 -> ClipboardTab(scope)
            5 -> TasksTab(scope)
        }
    }
}

// ─── KEYBOARD TAB ─────────────────────────────────────────────
@Composable
private fun KeyboardTab(scope: kotlinx.coroutines.CoroutineScope) {
    var textToType by remember { mutableStateOf("") }
    val focusManager = LocalFocusManager.current
    var statusMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        // Type text
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("TYPE TEXT", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    OutlinedTextField(
                        value = textToType,
                        onValueChange = { textToType = it },
                        placeholder = { Text("Type anything...", color = dashColors().textMuted) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        textStyle = MaterialTheme.typography.bodyMedium.copy(color = dashColors().textPrimary),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                            focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                        ),
                        keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                        keyboardActions = KeyboardActions(onSend = {
                            if (textToType.isNotBlank()) {
                                scope.launch {
                                    try {
                                        DashApiService.typeText(textToType)
                                        statusMessage = "Typed: ${textToType.take(30)}..."
                                        textToType = ""
                                    } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                }
                            }
                            focusManager.clearFocus()
                        })
                    )
                    Button(
                        onClick = {
                            if (textToType.isNotBlank()) {
                                scope.launch {
                                    try {
                                        DashApiService.typeText(textToType)
                                        statusMessage = "Typed: ${textToType.take(30)}..."
                                        textToType = ""
                                    } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = DashCyanPrimary)
                    ) {
                        Icon(Icons.AutoMirrored.Filled.Send, null, Modifier.size(16.dp))
                        Spacer(Modifier.width(8.dp))
                        Text("Type on Desktop", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }

        // Quick keys
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("QUICK KEYS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    val quickKeys = listOf(
                        Triple("Enter", "↵") { scope.launch { DashApiService.pressKey("enter") }; Unit },
                        Triple("Tab", "⇥") { scope.launch { DashApiService.pressKey("tab") }; Unit },
                        Triple("Escape", "Esc") { scope.launch { DashApiService.pressKey("escape") }; Unit },
                        Triple("Backspace", "⌫") { scope.launch { DashApiService.pressKey("backspace") }; Unit },
                        Triple("Delete", "Del") { scope.launch { DashApiService.pressKey("delete") }; Unit },
                        Triple("Space", "␣") { scope.launch { DashApiService.pressKey("space") }; Unit },
                    )
                    LazyRow(horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        items(quickKeys) { (name, symbol, action) ->
                            GlassCard(
                                modifier = Modifier.size(72.dp, 48.dp),
                                cornerRadius = 10.dp,
                                onClick = action
                            ) {
                                Column(Modifier.fillMaxSize(), horizontalAlignment = Alignment.CenterHorizontally, verticalArrangement = Arrangement.Center) {
                                    Text(symbol, fontSize = 16.sp, fontWeight = FontWeight.Bold, color = DashCyanPrimary)
                                    Text(name, fontSize = 9.sp, color = dashColors().textMuted)
                                }
                            }
                        }
                    }
                }
            }
        }

        // Hotkeys
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("HOTKEYS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    val hotkeys = listOf(
                        Triple("Ctrl+C", "Copy") { scope.launch { DashApiService.hotkey(listOf("ctrl", "c")) }; Unit },
                        Triple("Ctrl+V", "Paste") { scope.launch { DashApiService.hotkey(listOf("ctrl", "v")) }; Unit },
                        Triple("Ctrl+X", "Cut") { scope.launch { DashApiService.hotkey(listOf("ctrl", "x")) }; Unit },
                        Triple("Ctrl+Z", "Undo") { scope.launch { DashApiService.hotkey(listOf("ctrl", "z")) }; Unit },
                        Triple("Ctrl+S", "Save") { scope.launch { DashApiService.hotkey(listOf("ctrl", "s")) }; Unit },
                        Triple("Ctrl+A", "Select All") { scope.launch { DashApiService.hotkey(listOf("ctrl", "a")) }; Unit },
                        Triple("Alt+Tab", "Switch App") { scope.launch { DashApiService.hotkey(listOf("alt", "tab")) }; Unit },
                        Triple("Win+D", "Show Desktop") { scope.launch { DashApiService.hotkey(listOf("win", "d")) }; Unit },
                        Triple("Win+L", "Lock") { scope.launch { DashApiService.hotkey(listOf("win", "l")) }; Unit },
                    )
                    hotkeys.chunked(3).forEach { row ->
                        Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                            row.forEach { (combo, label, action) ->
                                GlassCard(
                                    modifier = Modifier.weight(1f),
                                    cornerRadius = 10.dp,
                                    onClick = action
                                ) {
                                    Column(Modifier.padding(10.dp), horizontalAlignment = Alignment.CenterHorizontally) {
                                        Text(combo, fontSize = 11.sp, fontWeight = FontWeight.Bold, color = DashCyanPrimary)
                                        Text(label, fontSize = 9.sp, color = dashColors().textMuted)
                                    }
                                }
                            }
                        }
                    }
                }
            }
        }

        if (statusMessage.isNotBlank()) {
            item {
                Text(statusMessage, fontSize = 11.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace)
            }
        }
    }
}

// ─── MOUSE TAB ────────────────────────────────────────────────
@Composable
private fun MouseTab(scope: kotlinx.coroutines.CoroutineScope) {
    var statusMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        // Mouse click buttons
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("MOUSE CLICKS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ControlButton("Left Click", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseClick("left"); statusMessage = "Left click" }
                        }
                        ControlButton("Right Click", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseClick("right"); statusMessage = "Right click" }
                        }
                    }
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ControlButton("Double Click", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseDoubleClick(); statusMessage = "Double click" }
                        }
                        ControlButton("Middle Click", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseClick("middle"); statusMessage = "Middle click" }
                        }
                    }
                }
            }
        }

        // Scroll
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("SCROLL", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        ControlButton("⬆ Scroll Up", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseScroll(-3); statusMessage = "Scrolled up" }
                        }
                        ControlButton("⬇ Scroll Down", Modifier.weight(1f)) {
                            scope.launch { DashApiService.mouseScroll(3); statusMessage = "Scrolled down" }
                        }
                    }
                }
            }
        }

        // Mouse position
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("MOUSE POSITION", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    var pos by remember { mutableStateOf("Tap to get position") }
                    ControlButton("Get Position", Modifier.fillMaxWidth()) {
                        scope.launch {
                            try {
                                val resp = DashApiService.getMousePosition()
                                pos = "X: ${resp.details["x"]}, Y: ${resp.details["y"]}"
                                statusMessage = pos
                            } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                        }
                    }
                    Text(pos, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = DashCyanPrimary)
                }
            }
        }

        if (statusMessage.isNotBlank()) {
            item { Text(statusMessage, fontSize = 11.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace) }
        }
    }
}

// ─── FILES TAB ────────────────────────────────────────────────
@Composable
private fun FilesTab(scope: kotlinx.coroutines.CoroutineScope) {
    var currentPath by remember { mutableStateOf("") }
    var files by remember { mutableStateOf<List<Map<String, Any>>>(emptyList()) }
    var isLoading by remember { mutableStateOf(false) }
    var statusMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        // Path bar
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("FILE EXPLORER", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = currentPath,
                            onValueChange = { currentPath = it },
                            placeholder = { Text("Path (e.g. C:\\Users)", color = dashColors().textMuted, fontSize = 12.sp) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp),
                            textStyle = MaterialTheme.typography.bodySmall.copy(fontFamily = FontFamily.Monospace, color = DashCyanPrimary),
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                            )
                        )
                        ControlButton("Go") {
                            scope.launch {
                                isLoading = true
                                try {
                                    val resp = DashApiService.browseFiles(currentPath)
                                    files = resp.files.map { mapOf("name" to it.name, "type" to it.type, "path" to it.path) }
                                    statusMessage = "Found ${files.size} items"
                                } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                isLoading = false
                            }
                        }
                    }

                    // Quick folders
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("Desktop", "Documents", "Downloads", "C:\\").forEach { folder ->
                            GlassCard(
                                modifier = Modifier.weight(1f),
                                cornerRadius = 8.dp,
                                onClick = {
                                    currentPath = folder
                                    scope.launch {
                                        isLoading = true
                                        try {
                                            val resp = DashApiService.browseFiles(folder)
                                            files = resp.files.map { mapOf("name" to it.name, "type" to it.type, "path" to it.path) }
                                        } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                        isLoading = false
                                    }
                                }
                            ) {
                                Text(folder, fontSize = 10.sp, color = DashCyanPrimary, modifier = Modifier.padding(6.dp), maxLines = 1, overflow = TextOverflow.Ellipsis)
                            }
                        }
                    }
                }
            }
        }

        // File list
        if (files.isNotEmpty()) {
            items(files) { file ->
                val name = file["name"] as? String ?: ""
                val type = file["type"] as? String ?: ""
                val path = file["path"] as? String ?: ""
                val icon = if (type == "folder") Icons.Default.Folder else Icons.Default.InsertDriveFile

                GlassCard(
                    Modifier.fillMaxWidth(),
                    cornerRadius = 10.dp,
                    onClick = {
                        if (type == "folder") {
                            currentPath = path
                            scope.launch {
                                isLoading = true
                                try {
                                    val resp = DashApiService.browseFiles(path)
                                    files = resp.files.map { mapOf("name" to it.name, "type" to it.type, "path" to it.path) }
                                } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                isLoading = false
                            }
                        }
                    }
                ) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(icon, null, Modifier.size(20.dp), tint = if (type == "folder") DashApprovalAmber else dashColors().textSecondary)
                        Spacer(Modifier.width(10.dp))
                        Text(name, fontSize = 13.sp, color = dashColors().textPrimary, modifier = Modifier.weight(1f), maxLines = 1, overflow = TextOverflow.Ellipsis)
                        if (type != "folder") {
                            GlassCard(Modifier.size(28.dp), cornerRadius = 6.dp, onClick = {
                                scope.launch {
                                    try { DashApiService.deleteFile(path, false); statusMessage = "Deleted: $name"; files = files.filter { it["path"] != path } }
                                    catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                }
                            }) {
                                Icon(Icons.Default.Delete, null, Modifier.size(14.dp).padding(4.dp), tint = DashErrorRed)
                            }
                        }
                    }
                }
            }
        }

        if (isLoading) {
            item { CircularProgressIndicator(Modifier.size(24.dp), color = DashCyanPrimary, strokeWidth = 2.dp) }
        }
        if (statusMessage.isNotBlank()) {
            item { Text(statusMessage, fontSize = 11.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace) }
        }
    }
}

// ─── APPS TAB ─────────────────────────────────────────────────
@Composable
private fun AppsTab(scope: kotlinx.coroutines.CoroutineScope) {
    var searchQuery by remember { mutableStateOf("") }
    var apps by remember { mutableStateOf<List<com.example.data.api.AppInfo>>(emptyList()) }
    var statusMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("APPLICATION MANAGER", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    Row(Modifier.fillMaxWidth(), verticalAlignment = Alignment.CenterVertically, horizontalArrangement = Arrangement.spacedBy(8.dp)) {
                        OutlinedTextField(
                            value = searchQuery,
                            onValueChange = { searchQuery = it },
                            placeholder = { Text("Search apps...", color = dashColors().textMuted) },
                            modifier = Modifier.weight(1f),
                            shape = RoundedCornerShape(10.dp),
                            textStyle = MaterialTheme.typography.bodyMedium.copy(color = dashColors().textPrimary),
                            singleLine = true,
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                                focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                            )
                        )
                        ControlButton("Search") {
                            scope.launch {
                                try {
                                    apps = DashApiService.searchApplications(searchQuery)
                                    statusMessage = "Found ${apps.size} apps"
                                } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                            }
                        }
                    }

                    // Quick launch buttons
                    Row(Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.spacedBy(6.dp)) {
                        listOf("notepad", "chrome", "explorer", "cmd", "code").forEach { app ->
                            GlassCard(
                                modifier = Modifier.weight(1f),
                                cornerRadius = 8.dp,
                                onClick = {
                                    scope.launch {
                                        try { DashApiService.launchApplication(app); statusMessage = "Launched: $app" }
                                        catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                                    }
                                }
                            ) {
                                Text(app, fontSize = 10.sp, color = DashCyanPrimary, modifier = Modifier.padding(6.dp))
                            }
                        }
                    }
                }
            }
        }

        // App list
        if (apps.isNotEmpty()) {
            items(apps) { app ->
                val name = app.name
                val path = app.path

                GlassCard(Modifier.fillMaxWidth(), cornerRadius = 10.dp) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        Icon(Icons.Default.Apps, null, Modifier.size(20.dp), tint = DashCyanPrimary)
                        Spacer(Modifier.width(10.dp))
                        Column(Modifier.weight(1f)) {
                            Text(name, fontSize = 13.sp, color = dashColors().textPrimary)
                            if (path.isNotBlank()) Text(path, fontSize = 9.sp, color = dashColors().textMuted, maxLines = 1, overflow = TextOverflow.Ellipsis)
                        }
                        ControlButton("Launch") {
                            scope.launch {
                                try { DashApiService.launchApplication(name); statusMessage = "Launched: $name" }
                                catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                            }
                        }
                    }
                }
            }
        }
        if (statusMessage.isNotBlank()) {
            item { Text(statusMessage, fontSize = 11.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace) }
        }
    }
}

// ─── CLIPBOARD TAB ────────────────────────────────────────────
@Composable
private fun ClipboardTab(scope: kotlinx.coroutines.CoroutineScope) {
    var clipboardText by remember { mutableStateOf("") }
    var inputText by remember { mutableStateOf("") }
    var statusMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("CLIPBOARD", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    ControlButton("Read Clipboard", Modifier.fillMaxWidth()) {
                        scope.launch {
                            try {
                                val resp = DashApiService.readClipboard()
                                clipboardText = resp.text
                                statusMessage = "Clipboard loaded (${clipboardText.length} chars)"
                            } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                        }
                    }
                    if (clipboardText.isNotBlank()) {
                        Text(clipboardText, fontSize = 11.sp, fontFamily = FontFamily.Monospace, color = dashColors().textSecondary, maxLines = 10)
                    }
                }
            }
        }

        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("WRITE TO CLIPBOARD", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    OutlinedTextField(
                        value = inputText,
                        onValueChange = { inputText = it },
                        placeholder = { Text("Text to copy...", color = dashColors().textMuted) },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        textStyle = MaterialTheme.typography.bodyMedium.copy(color = dashColors().textPrimary),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                            focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                        )
                    )
                    ControlButton("Write to Clipboard", Modifier.fillMaxWidth()) {
                        scope.launch {
                            try { DashApiService.writeClipboard(inputText); statusMessage = "Clipboard set!" }
                            catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                        }
                    }
                }
            }
        }

        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("SCREENSHOT", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    ControlButton("Capture Screenshot", Modifier.fillMaxWidth()) {
                        scope.launch {
                            try {
                                val resp = DashApiService.takeScreenshot()
                                statusMessage = "Screenshot captured (${resp.details["size"]} bytes)"
                            } catch (e: Exception) { statusMessage = "Error: ${e.message}" }
                        }
                    }
                }
            }
        }

        if (statusMessage.isNotBlank()) {
            item { Text(statusMessage, fontSize = 11.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace) }
        }
    }
}

// ─── TASKS TAB ────────────────────────────────────────────────
@Composable
private fun TasksTab(scope: kotlinx.coroutines.CoroutineScope) {
    var taskInput by remember { mutableStateOf("") }
    var isExecuting by remember { mutableStateOf(false) }
    var resultMessage by remember { mutableStateOf("") }

    LazyColumn(
        modifier = Modifier.fillMaxSize().padding(horizontal = 16.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp),
        contentPadding = PaddingValues(bottom = 100.dp)
    ) {
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    Text("AI TASK EXECUTOR", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    Text("Describe what you want the PC to do. DASH will plan and execute.", fontSize = 12.sp, color = dashColors().textSecondary)
                    OutlinedTextField(
                        value = taskInput,
                        onValueChange = { taskInput = it },
                        placeholder = { Text("e.g. Create a Python script that monitors CPU usage...", color = dashColors().textMuted) },
                        modifier = Modifier.fillMaxWidth(),
                        minLines = 3,
                        shape = RoundedCornerShape(12.dp),
                        textStyle = MaterialTheme.typography.bodyMedium.copy(color = dashColors().textPrimary),
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = DashCyanPrimary, unfocusedBorderColor = dashColors().borderGlass,
                            focusedContainerColor = dashColors().surfaceContainerLow, unfocusedContainerColor = dashColors().surfaceContainerLow
                        )
                    )
                    Button(
                        onClick = {
                            if (taskInput.isNotBlank()) {
                                isExecuting = true
                                scope.launch {
                                    try {
                                        WebSocketManager.sendChatMessage(taskInput)
                                        resultMessage = "Command accepted! DASH is planning and executing..."
                                        taskInput = ""
                                    } catch (e: Exception) { resultMessage = "Error: ${e.message}" }
                                    isExecuting = false
                                }
                            }
                        },
                        modifier = Modifier.fillMaxWidth(),
                        shape = RoundedCornerShape(12.dp),
                        colors = ButtonDefaults.buttonColors(containerColor = DashCyanPrimary),
                        enabled = !isExecuting
                    ) {
                        if (isExecuting) {
                            CircularProgressIndicator(Modifier.size(16.dp), color = Color.White, strokeWidth = 2.dp)
                            Spacer(Modifier.width(8.dp))
                            Text("Executing...", color = Color.White)
                        } else {
                            Icon(Icons.Default.Send, null, Modifier.size(16.dp))
                            Spacer(Modifier.width(8.dp))
                            Text("Execute Task", color = Color.White, fontWeight = FontWeight.Bold)
                        }
                    }
                }
            }
        }

        if (resultMessage.isNotBlank()) {
            item {
                GlassCard(Modifier.fillMaxWidth()) {
                    Text(resultMessage, fontSize = 12.sp, color = DashSuccessGreen, fontFamily = FontFamily.Monospace, modifier = Modifier.padding(16.dp))
                }
            }
        }

        // Common tasks
        item {
            GlassCard(Modifier.fillMaxWidth()) {
                Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
                    Text("QUICK TASKS", style = MaterialTheme.typography.labelSmall, color = dashColors().textMuted, letterSpacing = 1.2.sp)
                    val quickTasks = listOf(
                        "Check system health and report all hardware status",
                        "List all running processes and their CPU usage",
                        "Create a new project folder structure on Desktop",
                        "Open Chrome and search for 'DASH AI assistant'",
                        "Take a screenshot and describe what's on screen",
                        "Write a Python script to monitor network traffic",
                        "Clean up the Downloads folder",
                        "Create a backup of important documents",
                    )
                    quickTasks.forEach { task ->
                        GlassCard(
                            Modifier.fillMaxWidth(),
                            cornerRadius = 8.dp,
                            onClick = {
                                taskInput = task
                                scope.launch {
                                    isExecuting = true
                                    WebSocketManager.sendChatMessage(task)
                                    resultMessage = "Command accepted! DASH is executing..."
                                    isExecuting = false
                                }
                            }
                        ) {
                            Row(Modifier.padding(10.dp), verticalAlignment = Alignment.CenterVertically) {
                                Icon(Icons.Default.PlayArrow, null, Modifier.size(14.dp), tint = DashCyanPrimary)
                                Spacer(Modifier.width(8.dp))
                                Text(task, fontSize = 11.sp, color = dashColors().textSecondary, maxLines = 2)
                            }
                        }
                    }
                }
            }
        }
    }
}

// ─── SHARED COMPONENT ─────────────────────────────────────────
@Composable
private fun ControlButton(
    text: String,
    modifier: Modifier = Modifier,
    onClick: () -> Unit
) {
    GlassCard(modifier = modifier, cornerRadius = 10.dp, onClick = onClick) {
        Text(
            text,
            fontSize = 11.sp,
            fontWeight = FontWeight.SemiBold,
            color = DashCyanPrimary,
            modifier = Modifier.padding(horizontal = 12.dp, vertical = 8.dp)
        )
    }
}
