package com.example.ui.screens.subscreens

import androidx.compose.animation.AnimatedVisibility
import androidx.compose.animation.fadeIn
import androidx.compose.animation.fadeOut
import androidx.compose.foundation.background
import androidx.compose.foundation.border
import androidx.compose.foundation.layout.*
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Cancel
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Send
import androidx.compose.material3.*
import androidx.compose.runtime.*
import androidx.compose.runtime.collectAsState
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.data.websocket.WebSocketManager
import com.example.ui.theme.*

data class AgentGoal(
    val id: String,
    val description: String,
    val state: String = "idle",
    val iteration: Int = 0,
    val maxIterations: Int = 10,
    val elapsed: Double = 0.0,
    val result: String? = null,
    val error: String? = null,
    val steps: List<AgentStep> = emptyList()
)

data class AgentStep(
    val iteration: Int,
    val toolName: String?,
    val thought: String?,
    val success: Boolean?,
    val durationMs: Double = 0.0
)

@Composable
fun AgentModeScreen(
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    var goalInput by remember { mutableStateOf("") }
    var goals by remember { mutableStateOf(listOf<AgentGoal>()) }
    var agentStatus by remember { mutableStateOf<Map<String, Any>?>(null) }
    var isSending by remember { mutableStateOf(false) }

    // Collect agent goals from WebSocket
    val rawGoals by WebSocketManager.agentGoals.collectAsState()
    
    // Convert raw goals to AgentGoal objects
    LaunchedEffect(rawGoals) {
        goals = rawGoals.mapNotNull { g ->
            try {
                AgentGoal(
                    id = g["id"] as? String ?: return@mapNotNull null,
                    description = g["description"] as? String ?: "",
                    state = g["state"] as? String ?: "idle",
                    iteration = (g["iteration"] as? Number)?.toInt() ?: 0,
                    maxIterations = (g["max_iterations"] as? Number)?.toInt() ?: 10,
                    elapsed = (g["elapsed"] as? Number)?.toDouble() ?: 0.0,
                    result = g["result"] as? String,
                    error = g["error"] as? String
                )
            } catch (e: Exception) { null }
        }
    }
    
    // Query existing goals on entry
    LaunchedEffect(Unit) {
        WebSocketManager.queryAgentGoals()
        WebSocketManager.queryAgentStatus()
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(DashBackground)
            .padding(16.dp)
    ) {
        // Header
        Row(
            modifier = Modifier.fillMaxWidth(),
            verticalAlignment = Alignment.CenterVertically
        ) {
            IconButton(onClick = onBack) {
                Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back", tint = DashCyanPrimary)
            }
            Spacer(modifier = Modifier.width(8.dp))
            Icon(Icons.Default.AutoAwesome, "Agent", tint = DashCyanPrimary, modifier = Modifier.size(24.dp))
            Spacer(modifier = Modifier.width(8.dp))
            Text(
                "AGENT MODE",
                color = DashCyanPrimary,
                fontSize = 18.sp,
                fontFamily = FontFamily.Monospace,
                fontWeight = FontWeight.Bold
            )
            Spacer(modifier = Modifier.weight(1f))
            // Status indicator
            val runningCount = goals.count { it.state in listOf("thinking", "acting", "reflecting") }
            if (runningCount > 0) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(DashCyanPrimary.copy(alpha = 0.15f))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        "$runningCount running",
                        color = DashCyanPrimary,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Goal input
        GlassCard {
            Column(modifier = Modifier.padding(12.dp)) {
                Text(
                    "NEW GOAL",
                    color = DashCyanPrimary,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Bold,
                    letterSpacing = 1.sp
                )
                Spacer(modifier = Modifier.height(8.dp))
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    OutlinedTextField(
                        value = goalInput,
                        onValueChange = { goalInput = it },
                        modifier = Modifier.weight(1f),
                        placeholder = {
                            Text(
                                "e.g. Find all large files in Downloads",
                                color = DashTextMuted,
                                fontSize = 13.sp
                            )
                        },
                        colors = OutlinedTextFieldDefaults.colors(
                            focusedBorderColor = DashCyanPrimary,
                            unfocusedBorderColor = DashBorderGlass,
                            focusedTextColor = DashTextPrimary,
                            unfocusedTextColor = DashTextPrimary,
                            cursorColor = DashCyanPrimary
                        ),
                        textStyle = LocalTextStyle.current.copy(
                            fontFamily = FontFamily.Monospace,
                            fontSize = 13.sp
                        ),
                        maxLines = 2
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    IconButton(
                        onClick = {
                            if (goalInput.isNotBlank()) {
                                isSending = true
                                WebSocketManager.startAgentGoal(goalInput.trim())
                                goalInput = ""
                                // Refresh goals list
                                WebSocketManager.queryAgentGoals()
                                isSending = false
                            }
                        },
                        enabled = goalInput.isNotBlank() && !isSending
                    ) {
                        Icon(
                            Icons.Default.Send,
                            "Start Goal",
                            tint = if (goalInput.isNotBlank()) DashCyanPrimary else DashTextMuted
                        )
                    }
                }
            }
        }

        Spacer(modifier = Modifier.height(16.dp))

        // Goals list
        Text(
            "GOALS",
            color = DashCyanPrimary,
            fontSize = 11.sp,
            fontFamily = FontFamily.Monospace,
            fontWeight = FontWeight.Bold,
            letterSpacing = 1.sp
        )
        Spacer(modifier = Modifier.height(8.dp))

        if (goals.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .weight(1f),
                contentAlignment = Alignment.Center
            ) {
                Column(horizontalAlignment = Alignment.CenterHorizontally) {
                    Icon(
                        Icons.Default.AutoAwesome,
                        "No goals",
                        tint = DashTextMuted,
                        modifier = Modifier.size(48.dp)
                    )
                    Spacer(modifier = Modifier.height(8.dp))
                    Text(
                        "No autonomous goals yet.\nDescribe a task above to get started.",
                        color = DashTextMuted,
                        fontSize = 13.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier.weight(1f),
                verticalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                items(goals.reversed()) { goal ->
                    GoalCard(
                        goal = goal,
                        onCancel = {
                            WebSocketManager.cancelAgentGoal(goal.id)
                            WebSocketManager.queryAgentGoals()
                        }
                    )
                }
            }
        }
    }
}

@Composable
fun GoalCard(
    goal: AgentGoal,
    onCancel: () -> Unit,
    modifier: Modifier = Modifier
) {
    val stateColor = when (goal.state) {
        "completed" -> DashSuccessGreen
        "failed" -> Color(0xFFEF5350)
        "thinking", "acting", "reflecting" -> DashCyanPrimary
        "paused" -> DashApprovalAmber
        else -> DashTextMuted
    }
    val stateLabel = when (goal.state) {
        "thinking" -> "THINKING"
        "acting" -> "EXECUTING"
        "reflecting" -> "REFLECTING"
        "completed" -> "DONE"
        "failed" -> "FAILED"
        "paused" -> "PAUSED"
        else -> goal.state.uppercase()
    }

    GlassCard(modifier = modifier) {
        Column(modifier = Modifier.padding(12.dp)) {
            // Header row
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                // State indicator dot
                Box(
                    modifier = Modifier
                        .size(8.dp)
                        .clip(CircleShape)
                        .background(stateColor)
                )
                Spacer(modifier = Modifier.width(8.dp))
                Text(
                    goal.description,
                    color = DashTextPrimary,
                    fontSize = 13.sp,
                    fontFamily = FontFamily.Monospace,
                    fontWeight = FontWeight.Medium,
                    modifier = Modifier.weight(1f)
                )
                // Cancel button (only for running goals)
                if (goal.state in listOf("thinking", "acting", "reflecting")) {
                    IconButton(
                        onClick = onCancel,
                        modifier = Modifier.size(32.dp)
                    ) {
                        Icon(
                            Icons.Default.Cancel,
                            "Cancel",
                            tint = Color(0xFFEF5350),
                            modifier = Modifier.size(18.dp)
                        )
                    }
                }
            }

            Spacer(modifier = Modifier.height(6.dp))

            // State and progress
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically
            ) {
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(4.dp))
                        .background(stateColor.copy(alpha = 0.15f))
                        .padding(horizontal = 6.dp, vertical = 2.dp)
                ) {
                    Text(
                        stateLabel,
                        color = stateColor,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        fontWeight = FontWeight.Bold
                    )
                }
                Spacer(modifier = Modifier.width(8.dp))
                if (goal.maxIterations > 0) {
                    Text(
                        "Step ${goal.iteration}/${goal.maxIterations}",
                        color = DashTextSecondary,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
                Spacer(modifier = Modifier.weight(1f))
                if (goal.elapsed > 0) {
                    Text(
                        "${goal.elapsed.toInt()}s",
                        color = DashTextMuted,
                        fontSize = 11.sp,
                        fontFamily = FontFamily.Monospace
                    )
                }
            }

            // Progress bar for running goals
            if (goal.state in listOf("thinking", "acting", "reflecting") && goal.maxIterations > 0) {
                Spacer(modifier = Modifier.height(6.dp))
                LinearProgressIndicator(
                    progress = { (goal.iteration.toFloat() / goal.maxIterations).coerceIn(0f, 1f) },
                    modifier = Modifier
                        .fillMaxWidth()
                        .height(3.dp)
                        .clip(RoundedCornerShape(2.dp)),
                    color = DashCyanPrimary,
                    trackColor = DashSurfaceContainerLow
                )
            }

            // Result or error
            if (goal.result != null) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    goal.result,
                    color = DashSuccessGreen,
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 3
                )
            }
            if (goal.error != null) {
                Spacer(modifier = Modifier.height(6.dp))
                Text(
                    goal.error,
                    color = Color(0xFFEF5350),
                    fontSize = 11.sp,
                    fontFamily = FontFamily.Monospace,
                    maxLines = 3
                )
            }

            // Latest step
            val lastStep = goal.steps.lastOrNull()
            if (lastStep != null && goal.state in listOf("thinking", "acting", "reflecting")) {
                Spacer(modifier = Modifier.height(6.dp))
                Row(verticalAlignment = Alignment.CenterVertically) {
                    if (lastStep.success == true) {
                        Icon(Icons.Default.Check, "OK", tint = DashSuccessGreen, modifier = Modifier.size(12.dp))
                    }
                    Spacer(modifier = Modifier.width(4.dp))
                    Text(
                        "${lastStep.toolName ?: "?"} — ${(lastStep.thought ?: "").take(80)}",
                        color = DashTextSecondary,
                        fontSize = 10.sp,
                        fontFamily = FontFamily.Monospace,
                        maxLines = 2
                    )
                }
            }
        }
    }
}
