package com.example.ui.screens

import android.util.Log
import androidx.compose.animation.core.FastOutSlowInEasing
import androidx.compose.animation.core.LinearEasing
import androidx.compose.animation.core.RepeatMode
import androidx.compose.animation.core.animateFloat
import androidx.compose.animation.core.animateFloatAsState
import androidx.compose.animation.core.infiniteRepeatable
import androidx.compose.animation.core.rememberInfiniteTransition
import androidx.compose.animation.core.tween
import androidx.compose.foundation.Canvas
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.systemBarsPadding
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.ui.text.style.TextOverflow
import androidx.compose.foundation.layout.widthIn
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyRow
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Mic
import androidx.compose.material.icons.filled.MicOff
import androidx.compose.material.icons.filled.Stop
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableLongStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.mutableStateListOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.drawscope.Stroke
import androidx.compose.ui.hapticfeedback.HapticFeedbackType
import com.example.ui.components.HapticPattern
import com.example.ui.components.LocalHapticManager
import com.example.ui.components.ConversationMode
import androidx.compose.ui.platform.LocalHapticFeedback
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontStyle
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.text.style.TextAlign
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import kotlin.math.sin
import com.example.data.model.OrbState
import com.example.ui.components.DashOrb
import com.example.ui.components.GlassCard
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashPrimaryContainer
import com.example.ui.theme.DashPurpleContainer
import com.example.ui.viewmodel.DashViewModel
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.rememberCoroutineScope
import com.example.data.audio.SttRecorder
import com.example.data.audio.TtsPlayer
import com.example.data.websocket.WebSocketManager
import kotlinx.coroutines.launch
import com.example.ui.theme.dashColors
import androidx.compose.ui.platform.LocalClipboardManager
import androidx.compose.ui.text.AnnotatedString
import kotlinx.coroutines.delay

@Composable
fun VoiceScreen(
    viewModel: DashViewModel,
    onClose: () -> Unit,
    modifier: Modifier = Modifier
) {
    val hm = LocalHapticManager.current
    val orbState by viewModel.orbState.collectAsState()
    val isListening by viewModel.isVoiceListening.collectAsState()
    val voiceTranscript by viewModel.voiceTranscript.collectAsState()
    val chatMessages by viewModel.chatMessages.collectAsState()
    val recentMessages = remember(chatMessages) { chatMessages.takeLast(6) }

    var handsFreeEnabled by remember { mutableStateOf(true) }

    // Collect TTS audio chunks from backend and play sequentially (streaming)
    val ttsAudioQueue by WebSocketManager.ttsAudioQueue.collectAsState()
    val ttsAmplitude by TtsPlayer.currentAmplitude.collectAsState()
    val scope = rememberCoroutineScope()
    val conversationEnabled by ConversationMode.enabled.collectAsState()
    var conversationTurns by remember { mutableIntStateOf(0) }
    var isPlayingChunks by remember { mutableStateOf(false) }
    val liveAmplitude by SttRecorder.currentAmplitude.collectAsState()
    // Rolling buffer of amplitude samples for the waveform bars
    val amplitudeHistory = remember { mutableStateListOf<Int>() }
    LaunchedEffect(liveAmplitude) {
        amplitudeHistory.add(liveAmplitude)
        if (amplitudeHistory.size > 20) amplitudeHistory.removeAt(0)
    }
    var lastOrbTapTime by remember { mutableStateOf(0L) }

    // ── Session summary tracking ──
    var sessionStartTime by remember { mutableLongStateOf(System.currentTimeMillis()) }
    val sessionUserMessages = remember { mutableStateListOf<String>() }
    val sessionDashMessages = remember { mutableStateListOf<String>() }
    var showSessionSummary by remember { mutableStateOf(false) }

    // Track new messages as they arrive for the summary
    LaunchedEffect(chatMessages.size) {
        if (chatMessages.isNotEmpty()) {
            val last = chatMessages.last()
            if (last.sender == "USER" && !sessionUserMessages.contains(last.content)) {
                sessionUserMessages.add(last.content)
            } else if (last.sender == "DASH" && !sessionDashMessages.contains(last.content)) {
                sessionDashMessages.add(last.content)
            }
        }
    }

    // ── Audio latency tracking ──
    var sttSendTime by remember { mutableLongStateOf(0L) }
    var audioLatencyMs by remember { mutableLongStateOf(0L) }
    var avgLatencyMs by remember { mutableLongStateOf(0L) }
    var latencyCount by remember { mutableIntStateOf(0) }
    var latencySum by remember { mutableLongStateOf(0L) }

    // ── Sentence-by-sentence DASH response display ──
    val chatTokens by WebSocketManager.chatTokens.collectAsState()
    val chatDone by WebSocketManager.chatDone.collectAsState()
    var dashResponseSentences by remember { mutableStateOf<List<String>>(emptyList()) }
    var currentSentenceIndex by remember { mutableIntStateOf(-1) }

    // Capture tokens as they stream in during voice mode
    LaunchedEffect(chatTokens) {
        if (chatTokens.isNotBlank()) {
            dashResponseSentences = splitIntoSentences(chatTokens)
            if (currentSentenceIndex < 0) currentSentenceIndex = 0
        }
    }

    // When chat finishes, finalize the sentence list
    LaunchedEffect(chatDone) {
        if (chatDone && chatTokens.isNotBlank()) {
            dashResponseSentences = splitIntoSentences(chatTokens)
            if (currentSentenceIndex < 0) currentSentenceIndex = 0
        }
    }

    // Advance through sentences while TTS plays (word-count based timing)
    LaunchedEffect(isPlayingChunks, dashResponseSentences.size) {
        if (isPlayingChunks && dashResponseSentences.isNotEmpty()) {
            currentSentenceIndex = 0
            for (i in dashResponseSentences.indices) {
                currentSentenceIndex = i
                val sentence = dashResponseSentences[i]
                val wordCount = sentence.split(Regex("\\s+")).size.coerceAtLeast(1)
                val speakTimeMs = (wordCount * 400L).coerceIn(800, 5000)
                kotlinx.coroutines.delay(speakTimeMs)
            }
        }
    }

    // Reset sentences when entering voice mode (new question)
    LaunchedEffect(orbState) {
        if (orbState == OrbState.LISTENING) {
            dashResponseSentences = emptyList()
            currentSentenceIndex = -1
        }
    }

    // Build summary text from session data
    val sessionSummary = remember(sessionUserMessages.size, sessionDashMessages.size, showSessionSummary, avgLatencyMs) {
        if (!showSessionSummary) null else buildSessionSummary(
            startTime = sessionStartTime,
            userMessages = sessionUserMessages,
            dashMessages = sessionDashMessages,
            avgLatencyMs = avgLatencyMs
        )
    }

    // Goodbye detection patterns
    val goodbyePatterns = remember {
        setOf(
            "bye", "goodbye", "good bye", "see you", "see ya",
            "talk to you later", "talk later", "catch you later",
            "i'm done", "im done", "that's all", "thats all",
            "end conversation", "end chat", "stop listening",
            "stop talking", "exit voice", "exit", "quit",
            "close voice", "close", "shut up", "be quiet",
            "enough", "that'll be all", "that will be all",
            "you can stop", "we're done", "were done",
            "over and out", "out", "peace", "later"
        )
    }
    var isExitingConversation by remember { mutableStateOf(false) }
    var farewellText by remember { mutableStateOf<String?>(null) }

    // Streaming TTS: consume chunks from queue and play sequentially
    LaunchedEffect(ttsAudioQueue.size) {
        if (ttsAudioQueue.isNotEmpty() && !isPlayingChunks) {
            isPlayingChunks = true
            viewModel.setOrbState(OrbState.SPEAKING)
            try {
                hm.perform(HapticPattern.CONFIRM)

                // Calculate audio latency: time from STT send to first TTS chunk
                if (sttSendTime > 0) {
                    val latency = System.currentTimeMillis() - sttSendTime
                    audioLatencyMs = latency
                    latencyCount++
                    latencySum += latency
                    avgLatencyMs = latencySum / latencyCount
                    sttSendTime = 0L
                }

                // Play all queued chunks sequentially
                while (true) {
                    val chunk = WebSocketManager.popTtsAudio() ?: break
                    if (chunk.audioBase64.isNotBlank()) {
                        TtsPlayer.play(chunk.audioBase64)
                    }
                }

                // Auto-start listening for conversation mode
                if (conversationEnabled && conversationTurns < ConversationMode.MAX_TURNS) {
                    scope.launch {
                        kotlinx.coroutines.delay(300)
                        conversationTurns++
                        SttRecorder.start()
                        viewModel.startVoiceInteraction()
                        hm.perform(HapticPattern.TAP)
                    }
                }
            } finally {
                // Always clean up state, even if coroutine is cancelled by a new chunk
                viewModel.setOrbState(OrbState.IDLE)
                isPlayingChunks = false
            }
        }
    }

    // Reset conversation turns when entering conversation mode
    LaunchedEffect(conversationEnabled) {
        if (!conversationEnabled) {
            conversationTurns = 0
        }
    }

    // Collect STT result — detect goodbye before sending to backend
    val sttResult by WebSocketManager.sttResult.collectAsState()
    LaunchedEffect(sttResult) {
        val result = sttResult
        if (result != null && result.text.isNotBlank()) {
            val spoken = result.text.trim().lowercase()
                .replace(Regex("[.!?,;:'\"\\-]"), "")
            val isGoodbye = goodbyePatterns.any { pattern ->
                spoken == pattern || spoken.startsWith(pattern) || spoken.endsWith(pattern)
            }
            if (isGoodbye && !isExitingConversation) {
                // Goodbye detected — show session summary then exit
                isExitingConversation = true
                conversationTurns = 0
                SttRecorder.cancel()
                TtsPlayer.stop()
                WebSocketManager.clearTtsQueue()
                viewModel.setOrbState(OrbState.IDLE)
                hm.perform(HapticPattern.DESTROY)
                WebSocketManager.clearSttResult()
                // Show session summary
                showSessionSummary = true
            } else if (!isGoodbye) {
                // Normal message — send to backend
                isExitingConversation = false
                viewModel.sendMessage(result.text, voiceMode = true)
                WebSocketManager.clearSttResult()
            } else {
                // Already exiting, just clear
                WebSocketManager.clearSttResult()
            }
        }
    }

    // Cleanup: stop TTS and STT when leaving screen
    DisposableEffect(Unit) {
        onDispose {
            TtsPlayer.stop()
            TtsPlayer.onComplete = null
            SttRecorder.cancel()
            viewModel.setOrbState(OrbState.IDLE)
            conversationTurns = 0
            isPlayingChunks = false
            WebSocketManager.clearTtsQueue()
        }
    }

    val infiniteTransition = rememberInfiniteTransition(label = "voice")
    val waveOffset by infiniteTransition.animateFloat(
        initialValue = 0.2f, targetValue = 1.0f,
        animationSpec = infiniteRepeatable(
            tween(600, easing = FastOutSlowInEasing), RepeatMode.Reverse
        ), label = "wave"
    )

    // Ambient glow intensity based on state
    val ambientIntensity by animateFloatAsState(
        targetValue = when {
            isListening -> 0.20f
            orbState == OrbState.SPEAKING -> 0.15f
            orbState == OrbState.THINKING -> 0.12f
            else -> 0.06f
        },
        animationSpec = tween(800, easing = FastOutSlowInEasing),
        label = "ambient"
    )

    // Pulsing ring animation
    val pulseRing by infiniteTransition.animateFloat(
        initialValue = 0.8f, targetValue = 1.6f,
        animationSpec = infiniteRepeatable(
            tween(3000, easing = FastOutSlowInEasing), RepeatMode.Restart
        ), label = "pulse_ring"
    )

    val voiceHaptic = LocalHapticFeedback.current

    // Subtle haptic pulse synced with orb animation when listening/speaking
    LaunchedEffect(isListening, orbState) {
        val isActive = isListening || orbState == OrbState.SPEAKING
        while (isActive) {
            kotlinx.coroutines.delay(3000) // matches pulseRing animation period
            if (isListening || orbState == OrbState.SPEAKING) {
                hm.perform(HapticPattern.TAP)
            }
        }
    }

    // TAP haptic when transitioning into listening state
    LaunchedEffect(isListening) {
        if (isListening) {
            hm.perform(HapticPattern.CONFIRM)
        }
    }

    Box(modifier = modifier.fillMaxSize()) {
        // ── Ambient background layers ──
        Box(
            modifier = Modifier
                .fillMaxSize()
                .background(dashColors().background)
        ) {
            // Radial glow — top center
            Canvas(modifier = Modifier.fillMaxSize()) {
                val w = size.width
                val h = size.height

                // Top radial glow
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            DashCyanPrimary.copy(alpha = ambientIntensity),
                            DashPurpleSecondary.copy(alpha = ambientIntensity * 0.4f),
                            Color.Transparent
                        ),
                        center = Offset(w / 2f, h * 0.25f),
                        radius = w * 0.7f
                    ),
                    radius = w * 0.7f,
                    center = Offset(w / 2f, h * 0.25f)
                )

                // Bottom ambient glow
                drawCircle(
                    brush = Brush.radialGradient(
                        colors = listOf(
                            DashPurpleSecondary.copy(alpha = ambientIntensity * 0.5f),
                            Color.Transparent
                        ),
                        center = Offset(w / 2f, h * 0.85f),
                        radius = w * 0.5f
                    ),
                    radius = w * 0.5f,
                    center = Offset(w / 2f, h * 0.85f)
                )

                // Pulse rings (when listening)
                if (isListening || orbState == OrbState.SPEAKING) {
                    for (i in 0 until 3) {
                        val ringRadius = w * 0.25f * (pulseRing + i * 0.15f)
                        val ringAlpha = (1f - (pulseRing - 0.8f + i * 0.15f) / 0.9f).coerceIn(0f, 1f) * 0.15f
                        drawCircle(
                            color = DashCyanPrimary.copy(alpha = ringAlpha),
                            radius = ringRadius,
                            center = Offset(w / 2f, h * 0.38f),
                            style = Stroke(width = 1.dp.toPx())
                        )
                    }
                }
            }
        }

        // ── Content ──
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 24.dp),
            horizontalAlignment = Alignment.CenterHorizontally,
            verticalArrangement = Arrangement.SpaceBetween
        ) {
            // Top bar
            Row(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(top = 16.dp),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                IconButton(
                    onClick = {
                        hm.perform(HapticPattern.TAP)
                        if (conversationTurns > 0 || sessionUserMessages.isNotEmpty()) {
                            showSessionSummary = true
                        } else {
                            onClose()
                        }
                    },
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(Color.White.copy(alpha = 0.06f))
                        .testTag("voice_close_button")
                ) {
                    Icon(
                        imageVector = Icons.Default.Close,
                        contentDescription = "Close",
                        tint = dashColors().textPrimary,
                        modifier = Modifier.size(18.dp)
                    )
                }

                // Hands-free toggle
                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(
                            if (handsFreeEnabled) DashCyanPrimary.copy(alpha = 0.1f) else Color.Transparent
                        )
                        .border(
                            1.dp,
                            if (handsFreeEnabled) DashCyanPrimary.copy(alpha = 0.4f) else Color.White.copy(alpha = 0.08f),
                            CircleShape
                        )
                        .clickable {
                            hm.perform(HapticPattern.TAP)
                            handsFreeEnabled = !handsFreeEnabled
                        }
                        .padding(horizontal = 10.dp, vertical = 5.dp)
                ) {
                    Text(
                        text = if (handsFreeEnabled) "Wake: ON" else "Wake: OFF",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        color = if (handsFreeEnabled) DashCyanPrimary else dashColors().textMuted
                    )
                }
            }

            // Center: Orb + status
            Column(
                modifier = Modifier.fillMaxWidth(),
                horizontalAlignment = Alignment.CenterHorizontally
            ) {
                DashOrb(
                    state = if (isListening) OrbState.LISTENING else orbState,
                    size = 220.dp,
                    interactive = true,
                    audioAmplitude = ttsAmplitude / 1000f,
                    onClick = {
                        val now = System.currentTimeMillis()
                        if (now - lastOrbTapTime < 500) return@DashOrb  // 500ms debounce
                        lastOrbTapTime = now
                        hm.perform(HapticPattern.CONFIRM)
                        if (isListening) {
                            // Stop recording and send audio to backend
                            scope.launch {
                                try {
                                    val audio = SttRecorder.stop()
                                    viewModel.stopVoiceInteraction()
                                    if (audio != null) {
                                        sttSendTime = System.currentTimeMillis()
                                        WebSocketManager.sendVoiceStt(audio)
                                    }
                                } catch (e: Exception) {
                                    Log.e("VoiceScreen", "Error stopping voice", e)
                                    viewModel.stopVoiceInteraction()
                                }
                            }
                        } else {
                            // Start recording
                            hm.perform(HapticPattern.TAP)
                            try {
                                SttRecorder.start()
                                viewModel.startVoiceInteraction()
                            } catch (e: Exception) {
                                Log.e("VoiceScreen", "Error starting voice", e)
                            }
                        }
                    }
                )

                Spacer(modifier = Modifier.height(16.dp))

                // State badge
                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(
                            if (isListening) DashCyanPrimary.copy(alpha = 0.1f)
                            else orbState.primaryColor.copy(alpha = 0.1f)
                        )
                        .padding(horizontal = 14.dp, vertical = 5.dp)
                ) {
                    Text(
                        text = if (isListening) "LISTENING" else orbState.label.uppercase(),
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Medium,
                        fontSize = 11.sp,
                        color = if (isListening) DashCyanPrimary else orbState.primaryColor,
                        letterSpacing = 0.5.sp
                    )
                }

                // Audio latency indicator
                if (audioLatencyMs > 0) {
                    Spacer(modifier = Modifier.height(4.dp))
                    Row(
                        verticalAlignment = Alignment.CenterVertically,
                        horizontalArrangement = Arrangement.Center
                    ) {
                        Box(
                            modifier = Modifier
                                .size(5.dp)
                                .clip(CircleShape)
                                .background(
                                    when {
                                        audioLatencyMs < 1500 -> DashCyanPrimary
                                        audioLatencyMs < 3000 -> Color(0xFFFFC107)
                                        else -> DashErrorRed
                                    }
                                )
                        )
                        Spacer(modifier = Modifier.width(5.dp))
                        Text(
                            text = "${audioLatencyMs / 1000f}s response",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 9.sp,
                            color = dashColors().textMuted,
                            letterSpacing = 0.5.sp
                        )
                        if (avgLatencyMs > 0 && latencyCount > 1) {
                            Text(
                                text = "  avg ${(avgLatencyMs / 1000f)}s",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 9.sp,
                                color = DashPurpleSecondary.copy(alpha = 0.6f),
                                letterSpacing = 0.5.sp
                            )
                        }
                    }
                }

                // Conversation mode indicator
                if (conversationEnabled) {
                    Spacer(modifier = Modifier.height(6.dp))
                    Text(
                        text = "CONVERSATION MODE  Turn ${conversationTurns + 1}/${ConversationMode.MAX_TURNS}",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 9.sp,
                        color = DashPurpleSecondary.copy(alpha = 0.7f),
                        letterSpacing = 1.sp
                    )
                }

                Spacer(modifier = Modifier.height(12.dp))

                // Waveform
                if (isListening || orbState == OrbState.SPEAKING) {
                    Canvas(
                        modifier = Modifier
                            .fillMaxWidth(0.5f)
                            .height(32.dp)
                    ) {
                        val barCount = 20
                        val barWidth = 3.dp.toPx()
                        val spacing = (size.width - (barCount * barWidth)) / (barCount - 1)
                        val centerY = size.height / 2f
                        val historySize = amplitudeHistory.size

                        for (i in 0 until barCount) {
                            // Map bar index to amplitude history (newest = rightmost)
                            val histIndex = historySize - barCount + i
                            val rawAmp = if (histIndex in 0 until historySize) {
                                amplitudeHistory[histIndex].toFloat() / 1000f
                            } else {
                                // Idle: subtle ambient wave
                                ((sin(Math.toRadians(i * 22.0 + waveOffset * 180.0)) + 1.0) / 2.0).toFloat() * 0.1f
                            }
                            // Smooth with a minimum idle floor and apply easing
                            val factor = (rawAmp * 1.2f).coerceIn(0.04f, 1.0f)
                            val barHeight = (4.dp.toPx() + factor * 24.dp.toPx()).coerceAtMost(size.height)
                            val x = i * (barWidth + spacing)

                            // Bar glow
                            val glowRadius = barHeight / 2f + 4.dp.toPx()
                            drawCircle(
                                brush = Brush.radialGradient(
                                    colors = listOf(
                                        DashCyanPrimary.copy(alpha = factor * 0.25f),
                                        Color.Transparent
                                    ),
                                    center = Offset(x + barWidth / 2, centerY),
                                    radius = glowRadius
                                ),
                                radius = glowRadius,
                                center = Offset(x + barWidth / 2, centerY)
                            )

                            // Bar — brighter when louder
                            drawRoundRect(
                                color = DashCyanPrimary.copy(alpha = 0.2f + factor * 0.7f),
                                topLeft = Offset(x, centerY - barHeight / 2f),
                                size = androidx.compose.ui.geometry.Size(barWidth, barHeight),
                                cornerRadius = androidx.compose.ui.geometry.CornerRadius(3f, 3f)
                            )
                        }
                    }
                } else {
                    Spacer(modifier = Modifier.height(32.dp))
                }

Spacer(modifier = Modifier.height(8.dp))

                // Conversation flow with avatars
                if (recentMessages.isNotEmpty() || voiceTranscript.isNotBlank()) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(horizontal = 12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        recentMessages.forEach { msg ->
                            val isUser = msg.sender == "USER"
                            Row(
                                modifier = Modifier.fillMaxWidth(),
                                horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start,
                                verticalAlignment = Alignment.Top
                            ) {
                                if (!isUser) {
                                    Box(
                                        modifier = Modifier
                                            .size(28.dp)
                                            .clip(CircleShape)
                                            .background(DashCyanPrimary.copy(alpha = 0.15f)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("D", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = DashCyanPrimary)
                                    }
                                    Spacer(modifier = Modifier.width(8.dp))
                                }
                                Box(
                                    modifier = Modifier
                                        .widthIn(max = 240.dp)
                                        .clip(RoundedCornerShape(
                                            topStart = if (isUser) 14.dp else 4.dp,
                                            topEnd = if (isUser) 4.dp else 14.dp,
                                            bottomStart = 14.dp, bottomEnd = 14.dp
                                        ))
                                        .background(if (isUser) DashCyanPrimary.copy(alpha = 0.12f) else dashColors().surfaceContainerLow)
                                        .padding(horizontal = 12.dp, vertical = 8.dp)
                                ) {
                                    Text(
                                        text = msg.content,
                                        fontSize = 12.sp,
                                        color = if (isUser) dashColors().textPrimary else dashColors().textSecondary,
                                        lineHeight = 16.sp, maxLines = 3, overflow = TextOverflow.Ellipsis
                                    )
                                }
                                if (isUser) {
                                    Spacer(modifier = Modifier.width(8.dp))
                                    Box(
                                        modifier = Modifier.size(28.dp).clip(CircleShape)
                                            .background(DashPurpleSecondary.copy(alpha = 0.15f)),
                                        contentAlignment = Alignment.Center
                                    ) {
                                        Text("U", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = DashPurpleSecondary)
                                    }
                                }
                            }
                        }
                        // Live transcript bubble
                        if (voiceTranscript.isNotBlank() && (recentMessages.isEmpty() || recentMessages.last().sender != "USER" || recentMessages.last().content != voiceTranscript)) {
                            Row(modifier = Modifier.fillMaxWidth(), horizontalArrangement = Arrangement.End, verticalAlignment = Alignment.Top) {
                                Box(
                                    modifier = Modifier.widthIn(max = 240.dp)
                                        .clip(RoundedCornerShape(14.dp, 4.dp, 14.dp, 14.dp))
                                        .background(DashCyanPrimary.copy(alpha = 0.08f))
                                        .padding(horizontal = 12.dp, vertical = 8.dp)
                                ) {
                                    Text(voiceTranscript, fontSize = 12.sp, color = dashColors().textMuted,
                                        fontStyle = FontStyle.Italic, lineHeight = 16.sp, maxLines = 2, overflow = TextOverflow.Ellipsis)
                                }
                                Spacer(modifier = Modifier.width(8.dp))
                                Box(modifier = Modifier.size(28.dp).clip(CircleShape)
                                    .background(DashPurpleSecondary.copy(alpha = 0.15f)), contentAlignment = Alignment.Center) {
                                    Text("U", fontSize = 12.sp, fontWeight = FontWeight.Bold, color = DashPurpleSecondary)
                                }
                            }
                        }
                    }
                }

                Spacer(modifier = Modifier.height(8.dp))

                // Transcript / Sentence-by-sentence DASH response
                GlassCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .padding(horizontal = 8.dp),
                    backgroundColor = if (farewellText != null)
                        DashCyanPrimary.copy(alpha = 0.08f)
                    else dashColors().surfaceContainerLow.copy(alpha = 0.9f)
                ) {
                    if (farewellText != null) {
                        Text(
                            text = farewellText ?: "",
                            style = MaterialTheme.typography.bodyLarge,
                            color = DashCyanPrimary,
                            textAlign = TextAlign.Center,
                            lineHeight = 22.sp,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(14.dp)
                        )
                    } else if (dashResponseSentences.isNotEmpty() && currentSentenceIndex >= 0) {
                        // Sentence-by-sentence display
                        Column(
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(14.dp),
                            verticalArrangement = Arrangement.spacedBy(6.dp)
                        ) {
                            val displaySentences = dashResponseSentences.take(currentSentenceIndex + 1)
                            displaySentences.forEachIndexed { idx, sentence ->
                                val isCurrent = idx == currentSentenceIndex
                                val isPast = idx < currentSentenceIndex
                                val animatedAlpha by animateFloatAsState(
                                    targetValue = if (isCurrent) 1f else if (isPast) 0.5f else 0f,
                                    animationSpec = tween(300),
                                    label = "sentence_alpha_$idx"
                                )
                                Text(
                                    text = sentence,
                                    fontSize = if (isCurrent) 15.sp else 12.sp,
                                    fontWeight = if (isCurrent) FontWeight.Medium else FontWeight.Normal,
                                    color = when {
                                        isCurrent -> DashCyanPrimary
                                        isPast -> dashColors().textMuted
                                        else -> Color.Transparent
                                    },
                                    fontStyle = if (isPast) FontStyle.Italic else FontStyle.Normal,
                                    lineHeight = 20.sp,
                                    modifier = Modifier.graphicsLayer { alpha = animatedAlpha }
                                )
                                // Animated cursor on current sentence
                                if (isCurrent) {
                                    Box(
                                        modifier = Modifier
                                            .padding(top = 2.dp)
                                            .width(20.dp)
                                            .height(2.dp)
                                            .clip(RoundedCornerShape(1.dp))
                                            .background(DashCyanPrimary)
                                    )
                                }
                            }
                        }
                    } else {
                        // Fallback: show raw transcript
                        Text(
                            text = "\"$voiceTranscript\"",
                            style = MaterialTheme.typography.bodyLarge,
                            color = dashColors().textPrimary,
                            textAlign = TextAlign.Center,
                            lineHeight = 22.sp,
                            modifier = Modifier
                                .fillMaxWidth()
                                .padding(14.dp)
                        )
                    }
                }
            }

            // Bottom: prompts + mic
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(bottom = 80.dp),
                horizontalAlignment = Alignment.CenterHorizontally,
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Quick prompts
                LazyRow(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(6.dp)
                ) {
                    items(listOf(
                        "Check system health" to "Check system health and PC hardware",
                        "Review PR #402" to "Review PR #402 test suite and diffs",
                        "Lock PC" to "Lock my Windows workstation",
                        "Daily tasks" to "Summarize my daily tasks and priorities"
                    )) { (label, command) ->
                        Box(
                            modifier = Modifier
                                .clip(RoundedCornerShape(12.dp))
                                .background(Color.White.copy(alpha = 0.04f))
                                .border(1.dp, dashColors().borderGlass, RoundedCornerShape(12.dp))
                                .clickable {
                                    hm.perform(HapticPattern.TAP)
                                    viewModel.stopVoiceInteraction(command, voiceMode = true)
                                }
                                .padding(horizontal = 12.dp, vertical = 6.dp)
                        ) {
                            Text(
                                text = label,
                                fontSize = 11.sp,
                                color = DashCyanPrimary
                            )
                        }
                    }
                }

                // Mic button
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.Center,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    if (isListening || orbState == OrbState.SPEAKING) {
                        IconButton(
                            onClick = {
                                hm.perform(HapticPattern.CONFIRM)
                                TtsPlayer.stop()
                                SttRecorder.cancel()
                                viewModel.setOrbState(OrbState.IDLE)
                            },
                            modifier = Modifier
                                .size(44.dp)
                                .clip(CircleShape)
                                .background(DashErrorRed.copy(alpha = 0.1f))
                                .border(1.dp, DashErrorRed.copy(alpha = 0.3f), CircleShape)
                        ) {
                            Icon(
                                imageVector = Icons.Default.Stop,
                                contentDescription = "Stop",
                                tint = DashErrorRed,
                                modifier = Modifier.size(22.dp)
                            )
                        }

                        Spacer(modifier = Modifier.width(20.dp))
                    }

                    Box(
                        modifier = Modifier
                            .size(68.dp)
                            .clip(CircleShape)
                            .background(
                                Brush.radialGradient(
                                    if (isListening) listOf(DashPurpleSecondary, DashPurpleContainer)
                                    else listOf(DashCyanPrimary, DashPrimaryContainer)
                                )
                            )
                            .border(
                                2.dp,
                                if (isListening) DashPurpleSecondary else DashCyanPrimary,
                                CircleShape
                            )
                            .clickable {
                                hm.perform(HapticPattern.CONFIRM)
                                if (isListening) {
                                    scope.launch {
                                        val audio = SttRecorder.stop()
                                        viewModel.stopVoiceInteraction()
                                        if (audio != null) {
                                            sttSendTime = System.currentTimeMillis()
                                            WebSocketManager.sendVoiceStt(audio)
                                        }
                                    }
                                } else {
                                    SttRecorder.start()
                                    viewModel.startVoiceInteraction()
                                }
                            }
                            .testTag("voice_ptt_button"),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = if (isListening) Icons.Default.MicOff else Icons.Default.Mic,
                            contentDescription = "Push to talk",
                            tint = dashColors().surface,
                            modifier = Modifier.size(32.dp)
                        )
                    }
                }

                Text(
                    text = if (isListening) "Tap to stop" else "Tap to speak",
                    style = MaterialTheme.typography.bodySmall,
                    color = dashColors().textMuted
                )
            }
        }

        // ── Session Summary Overlay ──
        if (showSessionSummary && sessionSummary != null) {
            SessionSummaryOverlay(
                summary = sessionSummary,
                onDismiss = {
                    showSessionSummary = false
                    isExitingConversation = false
                    sessionUserMessages.clear()
                    sessionDashMessages.clear()
                    sessionStartTime = System.currentTimeMillis()
                    onClose()
                },
                onCopy = { /* clipboard copy handled inside overlay */ }
            )
        }
    }
}

// ── Sentence splitting helper ──
private fun splitIntoSentences(text: String): List<String> {
    if (text.isBlank()) return emptyList()
    // Split on sentence-ending punctuation followed by space or end of string
    val raw = text.split(Regex("(?<=[.!?])\\s+"))
        .map { it.trim() }
        .filter { it.isNotEmpty() }
    // If no sentence boundaries found, split by comma or just return the whole thing
    if (raw.size <= 1 && text.length > 60) {
        return text.chunked(60).map { it.trim() }.filter { it.isNotEmpty() }
    }
    return raw
}

// ── Session Summary Data ──
data class SessionSummary(
    val durationMs: Long,
    val turnCount: Int,
    val userQuestions: List<String>,
    val dashReplies: List<String>,
    val topics: List<String>,
    val timestamp: String,
    val avgLatencyMs: Long = 0L
)

private fun buildSessionSummary(
    startTime: Long,
    userMessages: List<String>,
    dashMessages: List<String>,
    avgLatencyMs: Long = 0L
): SessionSummary {
    val duration = System.currentTimeMillis() - startTime
    val turnCount = maxOf(userMessages.size, dashMessages.size)

    // Extract topics: first 3 user messages, truncated
    val topics = userMessages.take(3).map { msg ->
        val clean = msg.replace(Regex("[^a-zA-Z0-9 ]"), "").trim()
        if (clean.length > 40) clean.take(40) + "…" else clean
    }.ifEmpty { listOf("General conversation") }

    // Format timestamp
    val cal = java.util.Calendar.getInstance()
    val hour = cal.get(java.util.Calendar.HOUR_OF_DAY)
    val min = cal.get(java.util.Calendar.MINUTE)
    val amPm = if (hour < 12) "AM" else "PM"
    val displayHour = if (hour == 0) 12 else if (hour > 12) hour - 12 else hour
    val timestamp = "$displayHour:${"%02d".format(min)} $amPm"

    return SessionSummary(
        durationMs = duration,
        turnCount = turnCount,
        userQuestions = userMessages,
        dashReplies = dashMessages,
        topics = topics,
        timestamp = timestamp,
        avgLatencyMs = avgLatencyMs
    )
}

@Composable
private fun SessionSummaryOverlay(
    summary: SessionSummary,
    onDismiss: () -> Unit,
    onCopy: (String) -> Unit
) {
    val hm = LocalHapticManager.current
    val clipboardManager = LocalClipboardManager.current
    val scope = rememberCoroutineScope()
    var isAnimating by remember { mutableStateOf(false) }
    var copied by remember { mutableStateOf(false) }

    // Animate in
    LaunchedEffect(Unit) {
        isAnimating = true
    }

    val animatedAlpha by animateFloatAsState(
        targetValue = if (isAnimating) 1f else 0f,
        animationSpec = tween(400, easing = FastOutSlowInEasing),
        label = "summary_alpha"
    )
    val animatedScale by animateFloatAsState(
        targetValue = if (isAnimating) 1f else 0.9f,
        animationSpec = tween(400, easing = FastOutSlowInEasing),
        label = "summary_scale"
    )

    // Format duration
    val totalSec = summary.durationMs / 1000
    val min = totalSec / 60
    val sec = totalSec % 60
    val durationText = if (min > 0) "${min}m ${sec}s" else "${sec}s"

    // Build full summary text for copy
    val fullText = remember(summary) {
        buildString {
            appendLine("DASH Session Summary")
            appendLine("Time: ${summary.timestamp}  Duration: $durationText")
            appendLine("Turns: ${summary.turnCount}")
            if (summary.avgLatencyMs > 0) appendLine("Avg latency: ${summary.avgLatencyMs / 1000f}s")
            appendLine()
            appendLine("Topics:")
            summary.topics.forEachIndexed { i, t -> appendLine("  ${i + 1}. $t") }
            appendLine()
            if (summary.userQuestions.isNotEmpty()) {
                appendLine("You said:")
                summary.userQuestions.forEach { appendLine("  → $it") }
            }
            if (summary.dashReplies.isNotEmpty()) {
                appendLine()
                appendLine("DASH replied:")
                summary.dashReplies.takeLast(3).forEach { reply ->
                    val short = if (reply.length > 120) reply.take(120) + "…" else reply
                    appendLine("  ← $short")
                }
            }
        }
    }

    Box(
        modifier = Modifier
            .fillMaxSize()
            .graphicsLayer { alpha = animatedAlpha; scaleX = animatedScale; scaleY = animatedScale }
            .background(Color.Black.copy(alpha = 0.85f))
            .clickable(enabled = false) { }
            .systemBarsPadding(),
        contentAlignment = Alignment.Center
    ) {
        GlassCard(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 28.dp, vertical = 16.dp),
            backgroundColor = dashColors().surface.copy(alpha = 0.95f)
        ) {
            Column(
                modifier = Modifier.padding(24.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Header
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Text(
                        text = "SESSION SUMMARY",
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold,
                        fontSize = 13.sp,
                        color = DashCyanPrimary,
                        letterSpacing = 2.sp
                    )
                    Text(
                        text = summary.timestamp,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        color = dashColors().textMuted
                    )
                }

                // Divider
                Box(modifier = Modifier.fillMaxWidth().height(1.dp).background(DashCyanPrimary.copy(alpha = 0.2f)))

                // Stats row
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceEvenly
                ) {
                    SummaryStat("DURATION", durationText)
                    SummaryStat("TURNS", "${summary.turnCount}")
                    SummaryStat("AVG LATENCY", if (summary.avgLatencyMs > 0) "${summary.avgLatencyMs / 1000f}s" else "—")
                }

                // Topics discussed
                if (summary.topics.isNotEmpty()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "TOPICS DISCUSSED",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            color = DashPurpleSecondary,
                            letterSpacing = 1.sp
                        )
                        summary.topics.forEach { topic ->
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(5.dp)
                                        .clip(CircleShape)
                                        .background(DashCyanPrimary)
                                )
                                Spacer(modifier = Modifier.width(8.dp))
                                Text(
                                    text = topic,
                                    fontSize = 13.sp,
                                    color = dashColors().textPrimary,
                                    maxLines = 1,
                                    overflow = TextOverflow.Ellipsis
                                )
                            }
                        }
                    }
                }

                // Last few exchanges preview
                if (summary.dashReplies.isNotEmpty()) {
                    Column(verticalArrangement = Arrangement.spacedBy(4.dp)) {
                        Text(
                            text = "LAST EXCHANGE",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            color = DashPurpleSecondary,
                            letterSpacing = 1.sp
                        )
                        val lastUser = summary.userQuestions.lastOrNull()
                        val lastDash = summary.dashReplies.lastOrNull()
                        if (lastUser != null) {
                            Text(
                                text = "You: ${if (lastUser.length > 80) lastUser.take(80) + "…" else lastUser}",
                                fontSize = 12.sp,
                                color = dashColors().textSecondary,
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                        if (lastDash != null) {
                            Text(
                                text = "DASH: ${if (lastDash.length > 80) lastDash.take(80) + "…" else lastDash}",
                                fontSize = 12.sp,
                                color = DashCyanPrimary.copy(alpha = 0.8f),
                                maxLines = 2,
                                overflow = TextOverflow.Ellipsis
                            )
                        }
                    }
                }

                Spacer(modifier = Modifier.height(4.dp))

                // Action buttons
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.spacedBy(10.dp)
                ) {
                    // Copy button
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(if (copied) DashCyanPrimary.copy(alpha = 0.2f) else DashCyanPrimary.copy(alpha = 0.1f))
                            .border(1.dp, DashCyanPrimary.copy(alpha = 0.3f), RoundedCornerShape(12.dp))
                            .clickable {
                                hm.perform(HapticPattern.TAP)
                                clipboardManager.setText(AnnotatedString(fullText))
                                copied = true
                                scope.launch {
                                    kotlinx.coroutines.delay(2000)
                                    copied = false
                                }
                            }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = if (copied) "✅ Copied!" else "📋 Copy Summary",
                            fontFamily = FontFamily.Monospace,
                            fontSize = 12.sp,
                            color = if (copied) DashCyanPrimary else DashCyanPrimary
                        )
                    }

                    // Done button
                    Box(
                        modifier = Modifier
                            .weight(1f)
                            .clip(RoundedCornerShape(12.dp))
                            .background(DashCyanPrimary)
                            .clickable {
                                hm.perform(HapticPattern.CONFIRM)
                                onDismiss()
                            }
                            .padding(vertical = 10.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Text(
                            text = "Done",
                            fontFamily = FontFamily.Monospace,
                            fontWeight = FontWeight.Bold,
                            fontSize = 12.sp,
                            color = Color.Black
                        )
                    }
                }
            }
        }
    }
}

@Composable
private fun SummaryStat(label: String, value: String) {
    Column(horizontalAlignment = Alignment.CenterHorizontally) {
        Text(
            text = value,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            fontSize = 20.sp,
            color = DashCyanPrimary
        )
        Text(
            text = label,
            fontFamily = FontFamily.Monospace,
            fontSize = 9.sp,
            color = dashColors().textMuted,
            letterSpacing = 1.sp
        )
    }
}
