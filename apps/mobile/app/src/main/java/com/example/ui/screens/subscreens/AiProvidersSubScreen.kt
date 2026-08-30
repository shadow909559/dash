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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material.icons.filled.Tune
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.platform.testTag
import androidx.compose.ui.text.font.FontFamily
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import com.example.ui.components.GlassCard
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.viewmodel.DashViewModel
import com.example.ui.theme.dashColors

@Composable
fun AiProvidersSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val activeModel by viewModel.selectedProvider.collectAsState()

    val providers = listOf(
        ProviderOption(
            id = "gemini-3.5-flash",
            name = "Gemini 3.5 Flash",
            type = "Cloud AI (Google AI Studio)",
            description = "Ultra-low latency, multimodal search grounding, live vision, and responsive tool calling.",
            badge = "RECOMMENDED",
            badgeColor = DashCyanPrimary
        ),
        ProviderOption(
            id = "gemini-3.1-pro-preview",
            name = "Gemini 3.1 Pro (Thinking Mode)",
            type = "Deep Reasoning Cloud AI",
            description = "High-depth reasoning, complex architectural analysis, multi-agent task planning.",
            badge = "REASONING",
            badgeColor = DashPurpleSecondary
        ),
        ProviderOption(
            id = "qwen2.5-coder",
            name = "Qwen 2.5 Coder (Ollama)",
            type = "Local GPU Engine",
            description = "Zero internet dependency, local code generation, runs directly on Windows host RTX 4090.",
            badge = "LOCAL OFFLINE",
            badgeColor = DashSuccessGreen
        ),
        ProviderOption(
            id = "llama3.2:3b",
            name = "Llama 3.2 3B (Ollama)",
            type = "Local Ultra-Light",
            description = "Minimal VRAM footprint, instant local conversational responses and summarization.",
            badge = "LOCAL LIGHT",
            badgeColor = DashCyanPrimary
        ),
        ProviderOption(
            id = "bedrock-claude-3.5-sonnet",
            name = "Claude 3.5 Sonnet (AWS Bedrock)",
            type = "Enterprise Cloud AI",
            description = "High-tier code generation and complex tool orchestration via AWS IAM credentials.",
            badge = "AWS CLOUD",
            badgeColor = DashApprovalAmber
        )
    )

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("ai_providers_screen")
    ) {
        SubScreenHeader(
            title = "AI Providers & Protocol",
            subtitle = "Active: $activeModel - Protocol: OPENAI_NATIVE",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            items(providers.size) { index ->
                val provider = providers[index]
                val isSelected = activeModel == provider.id

                GlassCard(
                    modifier = Modifier
                        .fillMaxWidth()
                        .testTag("provider_option_${provider.id}"),
                    borderColor = if (isSelected) DashCyanPrimary else dashColors().borderGlass,
                    backgroundColor = if (isSelected) DashCyanPrimary.copy(alpha = 0.08f) else dashColors().surfaceContainerLow.copy(alpha = 0.7f),
                    onClick = { viewModel.setProvider(provider.id) }
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(8.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(24.dp)
                                        .clip(CircleShape)
                                        .background(if (isSelected) DashCyanPrimary else Color.White.copy(alpha = 0.08f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    if (isSelected) {
                                        Icon(
                                            imageVector = Icons.Default.Check,
                                            contentDescription = "Selected",
                                            tint = dashColors().surface,
                                            modifier = Modifier.size(14.dp)
                                        )
                                    }
                                }
                                Spacer(modifier = Modifier.width(10.dp))
                                Column {
                                    Text(
                                        text = provider.name,
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = if (isSelected) DashCyanPrimary else dashColors().textPrimary
                                    )
                                    Text(
                                        text = provider.type,
                                        style = MaterialTheme.typography.labelSmall,
                                        color = dashColors().textMuted
                                    )
                                }
                            }

                            Box(
                                modifier = Modifier
                                    .clip(RoundedCornerShape(6.dp))
                                    .background(provider.badgeColor.copy(alpha = 0.15f))
                                    .padding(horizontal = 8.dp, vertical = 4.dp)
                            ) {
                                Text(
                                    text = provider.badge,
                                    fontFamily = FontFamily.Monospace,
                                    fontSize = 9.sp,
                                    fontWeight = FontWeight.Bold,
                                    color = provider.badgeColor
                                )
                            }
                        }

                        Text(
                            text = provider.description,
                            style = MaterialTheme.typography.bodyMedium,
                            color = dashColors().textSecondary,
                            lineHeight = 18.sp
                        )
                    }
                }
            }
        }
    }
}

private data class ProviderOption(
    val id: String,
    val name: String,
    val type: String,
    val description: String,
    val badge: String,
    val badgeColor: Color
)
