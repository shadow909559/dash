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
import androidx.compose.material.icons.filled.Code
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Search
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
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
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.text.input.ImeAction
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.local.entity.ChatMessageEntity
import com.example.data.model.OrbState
import com.example.ui.components.DashOrb
import com.example.ui.components.ShimmerChatSkeleton
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainer
import com.example.ui.theme.DashSurfaceContainerHigh
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.theme.DashSurfaceContainerLowest
import com.example.ui.viewmodel.DashViewModel
import com.example.ui.theme.dashColors

@Composable
fun ChatScreen(
    viewModel: DashViewModel,
    onOpenVoice: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val messages by viewModel.chatMessages.collectAsState()
    val orbState by viewModel.orbState.collectAsState()
    val selectedProvider by viewModel.selectedProvider.collectAsState()
    val chatTokens by viewModel.chatTokens.collectAsState()
    val chatDone by viewModel.chatDone.collectAsState()
    val connectionState by viewModel.connectionState.collectAsState()

    var textInput by remember { mutableStateOf("") }
    var selectedMode by remember { mutableStateOf("GENERAL") }
    val listState = rememberLazyListState()

    LaunchedEffect(messages.size, chatTokens.length) {
        if (messages.isNotEmpty() || chatTokens.isNotEmpty()) {
            listState.animateScrollToItem(
                messages.size + if (chatTokens.isNotEmpty() && !chatDone) 1 else 0
            )
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("chat_screen")
    ) {
        // Header
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(dashColors().background)
                .padding(horizontal = 20.dp, vertical = 12.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Row(verticalAlignment = Alignment.CenterVertically) {
                    DashOrb(
                        state = orbState,
                        size = 32.dp,
                        interactive = false
                    )
                    Spacer(modifier = Modifier.width(10.dp))
                    Column {
                        Text(
                            text = "DASH",
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.SemiBold,
                            color = dashColors().textPrimary
                        )
                        Text(
                            text = when (connectionState) {
                                com.example.data.websocket.WebSocketManager.ConnectionState.Authenticated -> "Connected"
                                com.example.data.websocket.WebSocketManager.ConnectionState.Connected -> "Connecting..."
                                else -> "Offline"
                            },
                            style = MaterialTheme.typography.labelSmall,
                            color = when (connectionState) {
                                com.example.data.websocket.WebSocketManager.ConnectionState.Authenticated -> DashCyanPrimary
                                com.example.data.websocket.WebSocketManager.ConnectionState.Connected -> DashPurpleSecondary
                                else -> dashColors().textSecondary
                            },
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp
                        )
                    }
                }

                // Provider badge
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(DashCyanPrimary.copy(alpha = 0.08f))
                        .padding(horizontal = 8.dp, vertical = 3.dp)
                ) {
                    Text(
                        text = if (selectedProvider.contains("qwen")) "Qwen 2.5" else "Llama 3.2",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        color = DashCyanPrimary
                    )
                }
            }
        }

        // Mode chips
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 6.dp),
            horizontalArrangement = Arrangement.spacedBy(6.dp)
        ) {
            item { ChatModeChip("General", Icons.Default.AutoAwesome, selectedMode == "GENERAL") { selectedMode = "GENERAL" } }
            item { ChatModeChip("Code Review", Icons.Default.Code, selectedMode == "CODE") { selectedMode = "CODE" } }
            item { ChatModeChip("Research", Icons.Default.Search, selectedMode == "RESEARCH") { selectedMode = "RESEARCH" } }
            item { ChatModeChip("Thinking", Icons.Default.Psychology, selectedMode == "THINKING") { selectedMode = "THINKING" } }
            item { ChatModeChip("Terminal", Icons.Default.Terminal, selectedMode == "TERMINAL") { selectedMode = "TERMINAL" } }
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
            // Skeleton loading when no messages yet
            if (messages.isEmpty() && chatTokens.isEmpty()) {
                item {
                    ShimmerChatSkeleton(messageCount = 4)
                }
            }

            items(messages, key = { it.id }) { message ->
                MessageBubble(message = message)
            }

            if (chatTokens.isNotEmpty() && !chatDone) {
                item {
                    StreamingBubble(tokens = chatTokens)
                }
            }

            if ((orbState == OrbState.THINKING || orbState == OrbState.EXECUTING) && chatTokens.isEmpty()) {
                item {
                    Row(
                        modifier = Modifier
                            .clip(RoundedCornerShape(12.dp))
                            .background(dashColors().surfaceContainer)
                            .padding(horizontal = 12.dp, vertical = 8.dp),
                        verticalAlignment = Alignment.CenterVertically
                    ) {
                        DashOrb(state = orbState, size = 16.dp, interactive = false)
                        Spacer(modifier = Modifier.width(6.dp))
                        Text(
                            text = if (orbState == OrbState.EXECUTING) "Executing..." else "Thinking...",
                            style = MaterialTheme.typography.bodySmall,
                            color = DashCyanPrimary,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp
                        )
                    }
                }
            }
        }

        // Suggested prompts
        if (messages.size <= 2) {
            LazyRow(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(horizontal = 16.dp, vertical = 4.dp),
                horizontalArrangement = Arrangement.spacedBy(6.dp)
            ) {
                item { SuggestionPill("PC status") { viewModel.sendMessage("What is the status of my PC?") } }
                item { SuggestionPill("Review PR #402") { viewModel.sendMessage("Review PR #402 test suite") } }
                item { SuggestionPill("Active agents") { viewModel.sendMessage("What are the active agents?") } }
                item { SuggestionPill("Today's plan") { viewModel.sendMessage("Show my plan for today") } }
            }
        }

        // Input bar
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(dashColors().background)
                .imePadding()
                .padding(horizontal = 16.dp, vertical = 8.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                // Voice button
                val chatHaptic = LocalHapticFeedback.current
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        onOpenVoice()
                    },
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.06f))
                        .testTag("chat_voice_button")
                ) {
                    Icon(
                        imageVector = Icons.Default.Mic,
                        contentDescription = "Voice",
                        tint = DashCyanPrimary,
                        modifier = Modifier.size(20.dp)
                    )
                }

                // Text field
                OutlinedTextField(
                    value = textInput,
                    onValueChange = { textInput = it },
                    placeholder = {
                        Text(
                            text = "Ask DASH...",
                            style = MaterialTheme.typography.bodyMedium,
                            color = dashColors().textMuted
                        )
                    },
                    modifier = Modifier
                        .weight(1f)
                        .testTag("chat_input_field"),
                    shape = RoundedCornerShape(20.dp),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashCyanPrimary.copy(alpha = 0.5f),
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedContainerColor = dashColors().surfaceContainerLow,
                        unfocusedContainerColor = dashColors().surfaceContainerLow,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    ),
                    singleLine = false,
                    maxLines = 4,
                    keyboardOptions = KeyboardOptions(imeAction = ImeAction.Send),
                    keyboardActions = KeyboardActions(
                        onSend = {
                            if (textInput.isNotBlank()) {
                                viewModel.sendMessage(textInput)
                                textInput = ""
                            }
                        }
                    )
                )

                // Send
                IconButton(
                    onClick = {
                        if (textInput.isNotBlank()) {
                            hm.perform(HapticPattern.CONFIRM)
                            viewModel.sendMessage(textInput)
                            textInput = ""
                        }
                    },
                    enabled = textInput.isNotBlank(),
                    modifier = Modifier
                        .size(40.dp)
                        .clip(CircleShape)
                        .background(
                            if (textInput.isNotBlank()) DashCyanPrimary else Color.White.copy(alpha = 0.05f)
                        )
                        .testTag("chat_send_button")
                ) {
                    Icon(
                        imageVector = Icons.AutoMirrored.Filled.Send,
                        contentDescription = "Send",
                        tint = if (textInput.isNotBlank()) DashSurfaceContainerLowest else dashColors().textMuted,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }
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
            text = "DASH",
            fontFamily = FontFamily.Monospace,
            fontSize = 10.sp,
            fontWeight = FontWeight.Medium,
            color = DashCyanPrimary,
            modifier = Modifier.padding(start = 4.dp, bottom = 2.dp)
        )

        Box(
            modifier = Modifier
                .clip(RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp))
                .background(dashColors().surfaceContainerLow)
                .border(1.dp, DashCyanPrimary.copy(alpha = 0.15f), RoundedCornerShape(topStart = 16.dp, topEnd = 16.dp, bottomStart = 4.dp, bottomEnd = 16.dp))
                .padding(12.dp)
        ) {
            Text(
                text = tokens,
                style = MaterialTheme.typography.bodyMedium,
                color = dashColors().textPrimary,
                lineHeight = 20.sp
            )
        }
    }
}

@Composable
private fun MessageBubble(message: ChatMessageEntity) {
    val isUser = message.sender == "USER"

    Column(
        modifier = Modifier
            .fillMaxWidth()
            .testTag(if (isUser) "chat_bubble_user" else "chat_bubble_dash"),
        horizontalAlignment = if (isUser) Alignment.End else Alignment.Start
    ) {
        // Sender
        Row(
            verticalAlignment = Alignment.CenterVertically,
            modifier = Modifier.padding(horizontal = 4.dp, vertical = 2.dp)
        ) {
            Text(
                text = if (isUser) "You" else "DASH",
                fontFamily = FontFamily.Monospace,
                fontSize = 10.sp,
                fontWeight = FontWeight.Medium,
                color = if (isUser) dashColors().textSecondary else DashCyanPrimary
            )
            Spacer(modifier = Modifier.width(6.dp))
            Text(
                text = message.timeFormatted,
                fontSize = 10.sp,
                color = dashColors().textMuted
            )
        }

        // Bubble
        Box(
            modifier = Modifier
                .clip(
                    RoundedCornerShape(
                        topStart = 16.dp,
                        topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp
                    )
                )
                .background(
                    if (isUser) dashColors().surfaceContainerLow else dashColors().surfaceContainerLow
                )
                .border(
                    width = 1.dp,
                    color = if (isUser) dashColors().borderGlass else DashCyanPrimary.copy(alpha = 0.12f),
                    shape = RoundedCornerShape(
                        topStart = 16.dp,
                        topEnd = 16.dp,
                        bottomStart = if (isUser) 16.dp else 4.dp,
                        bottomEnd = if (isUser) 4.dp else 16.dp
                    )
                )
                .padding(12.dp)
        ) {
            Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                Text(
                    text = message.content,
                    style = MaterialTheme.typography.bodyMedium,
                    color = dashColors().textPrimary,
                    lineHeight = 20.sp
                )

                if (!message.toolExecutionInfo.isNullOrBlank()) {
                    Box(
                        modifier = Modifier
                            .fillMaxWidth()
                            .clip(RoundedCornerShape(8.dp))
                            .background(Color.Black.copy(alpha = 0.3f))
                            .padding(8.dp)
                    ) {
                        Text(
                            text = message.toolExecutionInfo,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            color = DashCyanPrimary,
                            lineHeight = 14.sp
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun ChatModeChip(
    title: String,
    icon: androidx.compose.ui.graphics.vector.ImageVector,
    isSelected: Boolean,
    onClick: () -> Unit
) {
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
            contentDescription = title,
            tint = if (isSelected) DashCyanPrimary else dashColors().textMuted,
            modifier = Modifier.size(14.dp)
        )
        Spacer(modifier = Modifier.width(4.dp))
        Text(
            text = title,
            fontSize = 11.sp,
            fontWeight = if (isSelected) FontWeight.Medium else FontWeight.Normal,
            color = if (isSelected) DashCyanPrimary else dashColors().textSecondary
        )
    }
}

@Composable
private fun SuggestionPill(
    text: String,
    onClick: () -> Unit
) {
    Box(
        modifier = Modifier
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.04f))
            .border(1.dp, Color.White.copy(alpha = 0.08f), CircleShape)
            .clickable { onClick() }
            .padding(horizontal = 12.dp, vertical = 5.dp)
    ) {
        Text(
            text = text,
            fontSize = 11.sp,
            color = DashCyanPrimary
        )
    }
}
