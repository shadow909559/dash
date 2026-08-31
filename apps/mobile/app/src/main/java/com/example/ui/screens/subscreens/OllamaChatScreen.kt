package com.example.ui.screens.subscreens

import androidx.compose.animation.AnimatedVisibility
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
import androidx.compose.foundation.layout.imePadding
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.lazy.rememberLazyListState
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.text.KeyboardActions
import androidx.compose.foundation.text.KeyboardOptions
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.Send
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.SmartToy
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.rememberCoroutineScope
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.api.OllamaChatApi
import com.example.data.api.OllamaMessage
import com.example.data.api.OllamaModel
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurfaceContainerLowest
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.launch

@Composable
fun OllamaChatScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val haptic = LocalHapticFeedback.current
    val scope = rememberCoroutineScope()

    // State
    var ollamaStatus by remember { mutableStateOf("Checking...") }
    var isOllamaRunning by remember { mutableStateOf(false) }
    var models by remember { mutableStateOf<List<OllamaModel>>(emptyList()) }
    var selectedModel by remember { mutableStateOf("llama3.2:1b") }
    var isLoading by remember { mutableStateOf(false) }
    var textInput by remember { mutableStateOf("") }
    var isStreaming by remember { mutableStateOf(false) }
    var streamTokens by remember { mutableStateOf("") }

    val messages = remember { mutableStateListOf<ChatEntry>() }
    val listState = rememberLazyListState()

    // Load status and models on startup
    LaunchedEffect(Unit) {
        scope.launch(Dispatchers.IO) {
            try {
                val status = OllamaChatApi.getStatus()
                isOllamaRunning = status.local_running
                ollamaStatus = if (status.local_running) "Connected" else "Offline"

                val modelsResp = OllamaChatApi.getModels()
                models = modelsResp.models.filter {
                    it.name.contains("embed", ignoreCase = true).not() // exclude embedding models
                }
                if (models.isNotEmpty() && models.none { it.name == selectedModel }) {
                    selectedModel = models.first().name
                }
            } catch (e: Exception) {
                ollamaStatus = "Error: ${e.message}"
                isOllamaRunning = false
            }
        }
    }

    // Auto-scroll to bottom when new messages arrive
    LaunchedEffect(messages.size, streamTokens) {
        if (messages.isNotEmpty() || streamTokens.isNotEmpty()) {
            listState.animateScrollToItem(
                messages.size + if (streamTokens.isNotEmpty() && !isLoading) 0 else if (streamTokens.isNotEmpty()) 1 else 0
            )
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(com.example.ui.theme.dashColors().background)
    ) {
        // Header
        SubScreenHeader(
            title = "Ollama AI Chat",
            subtitle = ollamaStatus,
            subtitleColor = if (isOllamaRunning) DashSuccessGreen else DashCyanPrimary,
            onBack = onBack,
            trailingContent = {
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        scope.launch(Dispatchers.IO) {
                            try {
                                val status = OllamaChatApi.getStatus()
                                isOllamaRunning = status.local_running
                                ollamaStatus = if (status.local_running) "Connected" else "Offline"
                                val modelsResp = OllamaChatApi.getModels()
                                models = modelsResp.models.filter {
                                    it.name.contains("embed", ignoreCase = true).not()
                                }
                            } catch (e: Exception) {
                                ollamaStatus = "Error: ${e.message}"
                            }
                        }
                    },
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.05f))
                ) {
                    Icon(
                        imageVector = Icons.Default.Refresh,
                        contentDescription = "Refresh",
                        tint = DashCyanPrimary,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        )

        // Model selector
        AnimatedVisibility(visible = models.isNotEmpty()) {
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 6.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                items(models) { model ->
                    ModelChip(
                        model = model,
                        isSelected = model.name == selectedModel,
                        onClick = {
                            hm.perform(HapticPattern.TAP)
                            selectedModel = model.name
                        }
                    )
                }
            }
        }

        // Messages
        LazyColumn(
            state = listState,
            modifier = Modifier
                .weight(1f)
                .fillMaxWidth()
                .padding(horizontal = 16.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
            contentPadding = PaddingValues(top = 8.dp, bottom = 12.dp)
        ) {
            // Welcome message
            if (messages.isEmpty() && streamTokens.isEmpty()) {
                item {
                    WelcomeCard(isOllamaRunning, models.size)
                }
            }

            items(messages) { entry ->
                ChatBubble(entry)
            }

            // Streaming indicator
            if (streamTokens.isNotEmpty() && isLoading) {
                item {
                    StreamingBubble(streamTokens)
                }
            }

            // Loading indicator
            if (isLoading && streamTokens.isEmpty()) {
                item {
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(com.example.ui.theme.dashColors().surfaceContainer)
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        CircularProgressIndicator(
                            modifier = Modifier.size(14.dp),
                            color = DashCyanPrimary,
                            strokeWidth = 2.dp
                        )
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = "Thinking...",
                            style = MaterialTheme.typography.bodySmall,
                            color = DashCyanPrimary,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }

        // Input bar
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(com.example.ui.theme.dashColors().background)
                .imePadding()
                .padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Model indicator
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(DashCyanPrimary.copy(alpha = 0.08f))
                        .padding(horizontal = 8.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = selectedModel.split(":").first().take(8),
                        fontFamily = FontFamily.Monospace,
                        fontSize = 9.sp,
                        color = DashCyanPrimary,
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis
                    )
                }

                // Text field
                OutlinedTextField(
                    value = textInput,
                    onValueChange = { textInput = it },
                    placeholder = {
                        Text(
                            text = if (isOllamaRunning) "Ask Ollama..." else "Ollama offline",
                            style = MaterialTheme.typography.bodyMedium,
                            color = com.example.ui.theme.dashColors().textMuted
                        )
                    },
                    modifier = Modifier.weight(1f),
                    shape = RoundedCornerShape(20.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashCyanPrimary.copy(alpha = 0.5f),
                        unfocusedBorderColor = com.example.ui.theme.dashColors().borderGlass,
                        focusedContainerColor = com.example.ui.theme.dashColors().surfaceContainerLow,
                        unfocusedContainerColor = com.example.ui.theme.dashColors().surfaceContainerLow,
                        focusedTextColor = com.example.ui.theme.dashColors().textPrimary,
                        unfocusedTextColor = com.example.ui.theme.dashColors().textPrimary
                    ),
                    singleLine = false,
                    maxLines = 4,
                    enabled = !isLoading,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(
                        onSend = {
                            if (textInput.isNotBlank() && !isLoading) {
                                sendMessage(
                                    scope, textInput, selectedModel, messages,
                                    { streamTokens = it },
                                    { fullResponse ->
                                        messages.add(ChatEntry("assistant", fullResponse))
                                        streamTokens = ""
                                        isLoading = false
                                        isStreaming = false
                                    },
                                    { isLoading = it; isStreaming = it }
                                )
                                textInput = ""
                            }
                        }
                    )
                )

                // Send
                IconButton(
                    onClick = {
                        if (textInput.isNotBlank() && !isLoading) {
                            hm.perform(HapticPattern.CONFIRM)
                            sendMessage(
                                scope, textInput, selectedModel, messages,
                                { streamTokens = it },
                                { fullResponse ->
                                    messages.add(ChatEntry("assistant", fullResponse))
                                    streamTokens = ""
                                    isLoading = false
                                    isStreaming = false
                                },
                                { isLoading = it; isStreaming = it }
                            )
                            textInput = ""
                        }
                    },
                    enabled = textInput.isNotBlank() && !isLoading,
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(
                            if (textInput.isNotBlank() && !isLoading) DashCyanPrimary
                            else Color.White.copy(alpha = 0.05f)
                        )
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (textInput.isNotBlank() && !isLoading) DashSurfaceContainerLowest
                        else com.example.ui.theme.dashColors().textMuted,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
        }
    }
}

// ── Helper ──────────────────────────────────────────────────

private fun sendMessage(
    scope: kotlinx.coroutines.CoroutineScope,
    text: String,
    model: String,
    messages: MutableList<ChatEntry>,
    onStreamToken: (String) -> Unit,
    onComplete: (String) -> Unit,
    onLoading: (Boolean) -> Unit
) {
    messages.add(ChatEntry("user", text))
    onLoading(true)

    scope.launch(Dispatchers.IO) {
        val chatHistory = messages.map { OllamaMessage(role = it.role, content = it.content) }
        val buffer = StringBuilder()

        OllamaChatApi.chatStream(
            model = model,
            messages = chatHistory,
            onToken = { token ->
                buffer.append(token)
                onStreamToken(buffer.toString())
            },
            onComplete = { fullResponse ->
                onComplete(fullResponse.ifEmpty { buffer.toString() })
            }
        )
    }
}

// ── Data ────────────────────────────────────────────────────

data class ChatEntry(
    val role: String,
    val content: String
)

// ── UI Components ───────────────────────────────────────────

@Composable
private fun WelcomeCard(isRunning: Boolean, modelCount: Int) {
    Column(
        modifier = Modifier
            .fillMaxWidth()
            .clip(RoundedCornerShape(16.dp))
            .background(com.example.ui.theme.dashColors().surfaceContainer.copy(alpha = 0.6f))
            .border(1.dp, com.example.ui.theme.dashColors().borderGlass, RoundedCornerShape(16.dp))
            .padding(20.dp),
        horizontalAlignment = Alignment.CenterHorizontally
    ) {
        Icon(
            imageVector = Icons.Default.SmartToy,
            contentDescription = null,
            tint = DashCyanPrimary,
            modifier = Modifier.size(40.dp)
        )
        Spacer(modifier = Modifier.height(8.dp))
        Text(
            text = "Ollama AI Chat",
            style = MaterialTheme.typography.titleMedium,
            fontWeight = FontWeight.SemiBold,
            color = com.example.ui.theme.dashColors().textPrimary
        )
        Spacer(modifier = Modifier.height(4.dp))
        Text(
            text = if (isRunning) "$modelCount models available on your PC"
            else "Start Ollama on your PC to chat",
            style = MaterialTheme.typography.bodySmall,
            color = com.example.ui.theme.dashColors().textSecondary
        )
        if (isRunning) {
            Spacer(modifier = Modifier.height(8.dp))
            Text(
                text = "All conversations stay local — nothing leaves your PC",
                style = MaterialTheme.typography.labelSmall,
                color = DashSuccessGreen,
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp
            )
        }
    }
}

@Composable
private fun ModelChip(
    model: OllamaModel,
    isSelected: Boolean,
    onClick: () -> Unit
) {
    val family = model.details?.family ?: ""
    val icon = when {
        family.contains("llama") -> Icons.Default.AutoAwesome
        family.contains("qwen") -> Icons.Default.Code
        family.contains("gemma") -> Icons.Default.SmartToy
        else -> Icons.Default.AutoAwesome
    }

    Row(
        modifier = Modifier
            .clip(RoundedCornerShape(12.dp))
            .background(
                if (isSelected) DashCyanPrimary.copy(alpha = 0.1f)
                else Color.White.copy(alpha = 0.04f)
            )
            .border(
                1.dp,
                if (isSelected) DashCyanPrimary.copy(alpha = 0.4f) else Color.White.copy(alpha = 0.06f),
                RoundedCornerShape(12.dp)
            )
            .clickable { onClick() }
            .padding(horizontal = 10.dp, vertical = 5.dp),
        verticalAlignment = Alignment.CenterVertically
    ) {
        Icon(
            imageVector = icon,
            contentDescription = null,
            tint = if (isSelected) DashCyanPrimary else com.example.ui.theme.dashColors().textMuted,
            modifier = Modifier.size(14.dp)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Column {
            Text(
                text = model.name.split(":").first(),
                fontSize = 11.sp,
                fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal,
                color = if (isSelected) DashCyanPrimary else com.example.ui.theme.dashColors().textSecondary
            )
            if (model.details?.parameter_size?.isNotEmpty() == true) {
                Text(
                    text = model.details.parameter_size,
                    fontSize = 8.sp,
                    color = com.example.ui.theme.dashColors().textMuted
                )
            }
        }
        if (isSelected) {
            Spacer(modifier = Modifier.width(4.dp))
            Icon(
                imageVector = Icons.Default.Check,
                contentDescription = null,
                tint = DashCyanPrimary,
                modifier = Modifier.size(12.dp)
            )
        }
    }
}

@Composable
private fun ChatBubble(entry: ChatEntry) {
    val isUser = entry.role == "user"

    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        // Sender label
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
        ) {
            Text(
                text = if (isUser) "You" else "Ollama",
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium,
                color = if (isUser) com.example.ui.theme.dashColors().textSecondary else DashCyanPrimary
            )
        }

        // Message bubble
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .clip(
                    RoundedCornerShape(
                        topStart = 16.dp, topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp
                    )
                )
                .background(com.example.ui.theme.dashColors().surfaceContainerLow)
                .border(
                    width = 1.dp,
                    color = if (isUser) com.example.ui.theme.dashColors().borderGlass
                    else DashCyanPrimary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(
                        topStart = 16.dp, topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp
                    )
                )
                .padding(12.dp)
        ) {
            Text(
                text = entry.content,
                style = MaterialTheme.typography.bodyMedium,
                color = com.example.ui.theme.dashColors().textPrimary,
                lineHeight = 20.sp
            )
        }
    }
}

@Composable
private fun StreamingBubble(tokens: String) {
    Column(
        modifier = Modifier.fillMaxWidth(),
        horizontalAlignment = Alignment.Start
    ) {
        Text(
            text = "Ollama",
            fontFamily = FontFamily.Monospace,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            color = DashCyanPrimary,
            modifier = Modifier.padding(start = 4.dp, bottom = 2.dp)
        )
        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp))
                .background(com.example.ui.theme.dashColors().surfaceContainerLow)
                .border(
                    1.dp,
                    DashCyanPrimary.copy(alpha = 0.15f),
                    RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp)
                )
                .padding(12.dp)
        ) {
            Text(
                text = tokens,
                style = MaterialTheme.typography.bodyMedium,
                color = com.example.ui.theme.dashColors().textPrimary,
                lineHeight = 20.sp
            )
        }
    }
}
