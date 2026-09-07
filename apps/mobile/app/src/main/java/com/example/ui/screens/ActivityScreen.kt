package com.example.ui.screens

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
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.Explore
import androidx.compose.material.icons.filled.Pause
import androidx.compose.material.icons.filled.PlayArrow
import androidx.compose.material.icons.filled.Security
import androidx.compose.material.icons.filled.Settings
import androidx.compose.material.icons.filled.Terminal
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Brush
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.data.local.entity.AgentEntity
import com.example.data.local.entity.AuditLogEntity
import com.example.ui.components.GlassCard
import com.example.ui.components.ShimmerListSkeleton
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainer
import com.example.ui.theme.DashSurfaceContainerHigh
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import com.example.ui.theme.dashColors
import androidx.compose.ui.text.style.TextOverflow

@Composable
fun ActivityScreen(
    viewModel: DashViewModel,
    modifier: Modifier = Modifier
) {
    val agents by viewModel.activeAgents.collectAsState()
    val auditLogs by viewModel.auditLogs.collectAsState()

    var selectedTabIndex by remember { mutableIntStateOf(0) }
    var showCreateDialog by remember { mutableStateOf(false) }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("activity_screen")
    ) {
        // Top Header
        Box(
            modifier = Modifier
                .fillMaxWidth()
                .background(dashColors().surface.copy(alpha = 0.9f))
                .border(1.dp, dashColors().borderGlass)
                .padding(horizontal = 20.dp, vertical = 14.dp)
        ) {
            Row(
                modifier = Modifier.fillMaxWidth(),
                verticalAlignment = Alignment.CenterVertically,
                horizontalArrangement = Arrangement.SpaceBetween
            ) {
                Column {
                    Text(
                        text = "Agents & Automation",
                        style = MaterialTheme.typography.titleLarge,
                        fontWeight = FontWeight.Bold,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "${agents.filter { it.status == "RUNNING" }.size} Active daemons on Windows",
                        style = MaterialTheme.typography.bodySmall,
                        color = DashCyanPrimary,
                        fontFamily = FontFamily.Monospace
                    )
                }

                // Deploy Button
                Button(
                    onClick = { showCreateDialog = true },
                    shape = RoundedCornerShape(16.dp),
                    colors = ButtonDefaults.buttonColors(
                        containerColor = DashCyanPrimary,
                        contentColor = dashColors().surface
                    ),
                    contentPadding = PaddingValues(horizontal = 14.dp, vertical = 8.dp),
                    modifier = Modifier.testTag("deploy_agent_button")
                ) {
                    Icon(
                        imageVector = Icons.Default.Add,
                        contentDescription = "New Agent",
                        modifier = Modifier.size(16.dp)
                    )
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Deploy Agent", fontSize = 12.sp, fontWeight = FontWeight.Bold)
                }
            }
        }

        // Sub Tabs: (Active Agents, Security Audit)
        TabRow(
            selectedTabIndex = selectedTabIndex,
            containerColor = dashColors().surfaceContainerLow,
            contentColor = DashCyanPrimary,
            indicator = { tabPositions ->
                TabRowDefaults.SecondaryIndicator(
                    modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTabIndex]),
                    color = DashCyanPrimary,
                    height = 2.dp
                )
            }
        ) {
            Tab(
                selected = selectedTabIndex == 0,
                onClick = { selectedTabIndex = 0 },
                text = {
                    Text(
                        text = "Autonomous Agents (${agents.size})",
                        fontWeight = if (selectedTabIndex == 0) FontWeight.Bold else FontWeight.Normal,
                        color = if (selectedTabIndex == 0) DashCyanPrimary else dashColors().textSecondary
                    )
                }
            )
            Tab(
                selected = selectedTabIndex == 1,
                onClick = { selectedTabIndex = 1 },
                text = {
                    Text(
                        text = "Security Audit Logs",
                        fontWeight = if (selectedTabIndex == 1) FontWeight.Bold else FontWeight.Normal,
                        color = if (selectedTabIndex == 1) DashCyanPrimary else dashColors().textSecondary
                    )
                }
            )
        }

        // Tab Content
        if (selectedTabIndex == 0) {
            // Agents List
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                // Skeleton loading
                if (agents.isEmpty()) {
                    item { ShimmerListSkeleton(cardCount = 4) }
                }
                items(agents, key = { it.id }) { agent ->
                    AgentCard(
                        agent = agent,
                        onToggle = { viewModel.toggleAgent(agent) }
                    )
                }
            }
        } else {
            // Audit Logs List
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
                verticalArrangement = Arrangement.spacedBy(10.dp)
            ) {
                // Skeleton loading
                if (auditLogs.isEmpty()) {
                    item { ShimmerListSkeleton(cardCount = 5) }
                }
                items(auditLogs, key = { it.id }) { log ->
                    AuditLogItem(log = log)
                }
            }
        }
    }

    // Deploy Agent Dialog
    if (showCreateDialog) {
        CreateAgentDialog(
            onDismiss = { showCreateDialog = false },
            onCreate = { name, goal, instructions, tools, model ->
                viewModel.createAgent(name, goal, instructions, tools, model)
                showCreateDialog = false
            }
        )
    }
}

@Composable
private fun AgentCard(
    agent: AgentEntity,
    onToggle: () -> Unit
) {
    val isRunning = agent.status == "RUNNING"
    val accentColor = when (agent.iconType) {
        "TERMINAL" -> DashCyanPrimary
        "EXPLORE" -> DashPurpleSecondary
        "SETTINGS" -> DashCyanPrimary
        else -> DashCyanPrimary
    }

    GlassCard(
        modifier = Modifier
            .fillMaxWidth()
            .testTag("agent_card_${agent.id}")
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Header Row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Row(
                    verticalAlignment = Alignment.CenterVertically,
                    modifier = Modifier.weight(1f)
                ) {
                    Box(
                        modifier = Modifier
                            .size(38.dp)
                            .clip(CircleShape)
                            .background(accentColor.copy(alpha = 0.12f)),
                        contentAlignment = Alignment.Center
                    ) {
                        Icon(
                            imageVector = when (agent.iconType) {
                                "TERMINAL" -> Icons.Default.Terminal
                                "EXPLORE" -> Icons.Default.Explore
                                else -> Icons.Default.Settings
                            },
                            contentDescription = agent.name,
                            tint = accentColor,
                            modifier = Modifier.size(20.dp)
                        )
                    }
                    Spacer(modifier = Modifier.width(12.dp))
                    Column {
                        Text(
                            text = agent.name,
                            style = MaterialTheme.typography.titleMedium,
                            fontWeight = FontWeight.Bold,
                            color = dashColors().textPrimary,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                        Text(
                            text = "Model: ${agent.model} ● Perm L${agent.permissionLevel}",
                            style = MaterialTheme.typography.labelSmall,
                            color = dashColors().textMuted,
                            fontFamily = FontFamily.Monospace,
                            maxLines = 1,
                            overflow = TextOverflow.Ellipsis
                        )
                    }
                }

                // Status & Pause/Resume
                IconButton(
                    onClick = onToggle,
                    modifier = Modifier
                        .size(36.dp)
                        .clip(CircleShape)
                        .background(if (isRunning) DashCyanPrimary.copy(alpha = 0.12f) else Color.White.copy(alpha = 0.05f))
                ) {
                    Icon(
                        imageVector = if (isRunning) Icons.Default.Pause else Icons.Default.PlayArrow,
                        contentDescription = if (isRunning) "Pause" else "Resume",
                        tint = if (isRunning) DashCyanPrimary else dashColors().textMuted,
                        modifier = Modifier.size(18.dp)
                    )
                }
            }

            // Goal & Task
            Text(
                text = agent.goal,
                style = MaterialTheme.typography.bodyMedium,
                color = dashColors().textSecondary,
                maxLines = 2,
                overflow = TextOverflow.Ellipsis
            )

            // Current task live box
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Color.Black.copy(alpha = 0.3f))
                    .border(1.dp, dashColors().borderGlass, RoundedCornerShape(10.dp))
                    .padding(10.dp)
            ) {
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    Text(
                        text = "CURRENT TASK: ${agent.currentTask}",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        color = if (isRunning) DashCyanPrimary else dashColors().textMuted,
                        maxLines = 2,
                        overflow = TextOverflow.Ellipsis
                    )

                    if (agent.progressPercent >= 0) {
                        LinearProgressIndicator(
                            progress = { agent.progressPercent / 100f },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(4.dp)
                                .clip(RoundedCornerShape(2.dp)),
                            color = DashCyanPrimary,
                            trackColor = Color.White.copy(alpha = 0.1f)
                        )
                    }
                }
            }

            // Tools used chip row
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Text(
                    text = "Tools: ${agent.toolsUsed}",
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    color = dashColors().textMuted,
                    maxLines = 1,
                    overflow = TextOverflow.Ellipsis
                )

                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(
                            if (isRunning) DashSuccessGreen.copy(alpha = 0.15f)
                            else Color.White.copy(alpha = 0.05f)
                        )
                        .padding(horizontal = 8.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = agent.status,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        fontWeight = FontWeight.Bold,
                        color = if (isRunning) DashSuccessGreen else dashColors().textMuted
                    )
                }
            }
        }
    }
}

@Composable
private fun AuditLogItem(log: AuditLogEntity) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 14.dp,
        backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.6f)
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically
        ) {
            Box(
                modifier = Modifier
                    .size(32.dp)
                    .clip(CircleShape)
                    .background(DashCyanPrimary.copy(alpha = 0.12f)),
                contentAlignment = Alignment.Center
            ) {
                Icon(
                    imageVector = Icons.Default.Security,
                    contentDescription = null,
                    tint = DashCyanPrimary,
                    modifier = Modifier.size(16.dp)
                )
            }
            Spacer(modifier = Modifier.width(12.dp))
            Column(modifier = Modifier.weight(1f)) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.SpaceBetween
                ) {
                    Text(
                        text = log.event,
                        style = MaterialTheme.typography.titleSmall,
                        fontWeight = FontWeight.SemiBold,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = log.timeFormatted,
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        color = dashColors().textMuted
                    )
                }
                Spacer(modifier = Modifier.height(2.dp))
                Text(
                    text = log.detail,
                    style = MaterialTheme.typography.bodySmall,
                    color = dashColors().textSecondary
                )
            }
        }
    }
}

@Composable
private fun CreateAgentDialog(
    onDismiss: () -> Unit,
    onCreate: (name: String, goal: String, instructions: String, tools: String, model: String) -> Unit
) {
    var name by remember { mutableStateOf("Performance Profiler") }
    var goal by remember { mutableStateOf("Trace memory bottlenecks and render frame drops") }
    var tools by remember { mutableStateOf("Profiler, AST Parser, SysInternals") }
    var selectedModel by remember { mutableStateOf("qwen2.5-coder") }

    Dialog(onDismissRequest = onDismiss) {
        GlassCard(
            modifier = Modifier.fillMaxWidth(),
            backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.95f),
            cornerRadius = 24.dp
        ) {
            Column(
                modifier = Modifier
                    .fillMaxWidth()
                    .padding(20.dp),
                verticalArrangement = Arrangement.spacedBy(14.dp)
            ) {
                Text(
                    text = "Deploy Autonomous Agent",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = DashCyanPrimary
                )

                OutlinedTextField(
                    value = name,
                    onValueChange = { name = it },
                    label = { Text("Agent Name") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashCyanPrimary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                OutlinedTextField(
                    value = goal,
                    onValueChange = { goal = it },
                    label = { Text("Goal & Scope") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashCyanPrimary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                OutlinedTextField(
                    value = tools,
                    onValueChange = { tools = it },
                    label = { Text("Authorized Tools") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashCyanPrimary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Button(
                        onClick = onDismiss,
                        colors = ButtonDefaults.buttonColors(containerColor = Color.Transparent)
                    ) {
                        Text("Cancel", color = dashColors().textSecondary)
                    }

                    Spacer(modifier = Modifier.width(8.dp))

                    Button(
                        onClick = {
                            if (name.isNotBlank()) {
                                onCreate(name, goal, "Execute autonomously", tools, selectedModel)
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = DashCyanPrimary)
                    ) {
                        Text("Deploy to PC", color = dashColors().surface, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
