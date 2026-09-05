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
import androidx.compose.material.icons.filled.AutoAwesome
import androidx.compose.material.icons.filled.Description
import androidx.compose.material.icons.filled.Search
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
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

/** A single search result returned by the backend research endpoint. */
private data class ResearchResult(
    val title: String = "",
    val url: String = "",
    val snippet: String = ""
)

/** State container for the research panel. */
private data class ResearchState(
    val isLoading: Boolean = false,
    val error: String? = null,
    val query: String = "",
    val summary: String = "",
    val results: List<ResearchResult> = emptyList(),
    val totalResults: Int = 0
)

@Composable
fun KnowledgeResearchSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    onAskDash: (String) -> Unit,
    modifier: Modifier = Modifier
) {
    val scope = rememberCoroutineScope()
    var searchTopic by remember { mutableStateOf("") }
    var state by remember { mutableStateOf(ResearchState()) }

    fun runResearch(query: String) {
        scope.launch {
            state = state.copy(isLoading = true, error = null, query = query, results = emptyList())
            try {
                @Suppress("UNCHECKED_CAST")
                val response = DashApiService.rawResearch(query)
                val ok = response["ok"] as? Boolean ?: false
                if (!ok) {
                    val err = response["error"] as? String ?: "Research failed"
                    state = state.copy(isLoading = false, error = err)
                    return@launch
                }
                val resultsList = (response["results"] as? List<Map<String, Any>>)?.map { r ->
                    ResearchResult(
                        title = r["title"] as? String ?: "",
                        url = r["url"] as? String ?: "",
                        snippet = r["snippet"] as? String ?: ""
                    )
                } ?: emptyList()
                state = state.copy(
                    isLoading = false,
                    summary = response["summary"] as? String ?: "",
                    results = resultsList,
                    totalResults = response["total_results"] as? Int ?: resultsList.size
                )
            } catch (e: Exception) {
                state = state.copy(isLoading = false, error = e.message ?: "Research failed")
            }
        }
    }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("knowledge_research_screen")
    ) {
        SubScreenHeader(
            title = "Knowledge & Research",
            subtitle = "Web Research & Deep Synthesis",
            subtitleColor = DashPurpleSecondary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // Search / Start Research Box
            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.85f)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(16.dp),
                        verticalArrangement = Arrangement.spacedBy(10.dp)
                    ) {
                        Text(
                            text = "START NEW DEEP RESEARCH",
                            style = MaterialTheme.typography.labelSmall,
                            color = dashColors().textMuted,
                            letterSpacing = 1.2.sp
                        )

                        OutlinedTextField(
                            value = searchTopic,
                            onValueChange = { searchTopic = it },
                            placeholder = { Text("e.g. S3 Glacier Instant Retrieval vs Deep Archive pricing") },
                            modifier = Modifier.fillMaxWidth(),
                            shape = RoundedCornerShape(14.dp),
                            colors = OutlinedTextFieldDefaults.colors(
                                focusedBorderColor = DashPurpleSecondary,
                                unfocusedBorderColor = dashColors().borderGlass,
                                focusedTextColor = dashColors().textPrimary,
                                unfocusedTextColor = dashColors().textPrimary
                            )
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.spacedBy(8.dp)
                        ) {
                            Button(
                                onClick = {
                                    if (searchTopic.isNotBlank()) {
                                        runResearch(searchTopic)
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = DashPurpleSecondary),
                                enabled = !state.isLoading && searchTopic.isNotBlank()
                            ) {
                                if (state.isLoading) {
                                    CircularProgressIndicator(
                                        modifier = Modifier.size(14.dp),
                                        color = Color.Black,
                                        strokeWidth = 2.dp
                                    )
                                } else {
                                    Icon(imageVector = Icons.Default.Search, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                                    Spacer(modifier = Modifier.width(6.dp))
                                }
                                Text("Research", color = Color.Black, fontWeight = FontWeight.Bold)
                            }

                            Button(
                                onClick = {
                                    if (searchTopic.isNotBlank()) {
                                        onAskDash("Research topic: $searchTopic and synthesize findings")
                                    }
                                },
                                modifier = Modifier.weight(1f),
                                shape = RoundedCornerShape(12.dp),
                                colors = ButtonDefaults.buttonColors(containerColor = DashCyanPrimary)
                            ) {
                                Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, modifier = Modifier.size(16.dp), tint = Color.Black)
                                Spacer(modifier = Modifier.width(6.dp))
                                Text("Deep Synthesis", color = Color.Black, fontWeight = FontWeight.Bold)
                            }
                        }
                    }
                }
            }

            // Error
            if (state.error != null) {
                item {
                    GlassCard(modifier = Modifier.fillMaxWidth()) {
                        Box(
                            modifier = Modifier.fillMaxWidth().padding(16.dp),
                            contentAlignment = Alignment.Center
                        ) {
                            Text("Error: ${state.error}", color = DashErrorRed, style = MaterialTheme.typography.bodyMedium)
                        }
                    }
                }
            }

            // Loading indicator
            if (state.isLoading) {
                item {
                    Box(
                        modifier = Modifier.fillMaxWidth().padding(32.dp),
                        contentAlignment = Alignment.Center
                    ) {
                        Column(horizontalAlignment = Alignment.CenterHorizontally) {
                            CircularProgressIndicator(color = DashPurpleSecondary, modifier = Modifier.size(40.dp))
                            Spacer(modifier = Modifier.height(8.dp))
                            Text("Researching…", color = dashColors().textSecondary)
                        }
                    }
                }
            }

            // Summary
            if (state.summary.isNotBlank()) {
                item {
                    GlassCard(
                        modifier = Modifier.fillMaxWidth(),
                        backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.7f)
                    ) {
                        Column(modifier = Modifier.fillMaxWidth().padding(16.dp)) {
                            Text(
                                text = "RESEARCH SUMMARY",
                                style = MaterialTheme.typography.labelSmall,
                                color = DashPurpleSecondary,
                                letterSpacing = 1.2.sp
                            )
                            Spacer(modifier = Modifier.height(8.dp))
                            Text(
                                text = state.summary,
                                style = MaterialTheme.typography.bodyMedium,
                                color = dashColors().textPrimary,
                                lineHeight = 20.sp
                            )
                        }
                    }
                }
            }

            // Results header
            if (state.results.isNotEmpty()) {
                item {
                    Text(
                        text = "RESULTS (${state.totalResults} found)",
                        style = MaterialTheme.typography.labelSmall,
                        color = dashColors().textMuted,
                        letterSpacing = 1.2.sp
                    )
                }
            }

            // Skeleton loading during search
            if (state.isLoading && state.results.isEmpty()) {
                item { ShimmerListSkeleton(cardCount = 5) }
            }

            // Result cards
            items(state.results) { result ->
                ResearchResultCard(
                    title = result.title,
                    url = result.url,
                    snippet = result.snippet,
                    onAskDASH = { onAskDash("Explain this research result: ${result.title}") }
                )
            }
        }
    }
}

@Composable
private fun ResearchResultCard(
    title: String,
    url: String,
    snippet: String,
    onAskDASH: () -> Unit
) {
    GlassCard(modifier = Modifier.fillMaxWidth(), cornerRadius = 16.dp) {
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
                    Icon(
                        imageVector = Icons.Default.Description,
                        contentDescription = null,
                        tint = DashPurpleSecondary,
                        modifier = Modifier.size(18.dp)
                    )
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = url.take(60),
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        color = DashCyanPrimary,
                        maxLines = 1
                    )
                }
                Box(
                    modifier = Modifier
                        .clip(CircleShape)
                        .background(DashSuccessGreen.copy(alpha = 0.12f))
                        .padding(horizontal = 8.dp, vertical = 2.dp)
                ) {
                    Text(
                        text = "LIVE",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 9.sp,
                        fontWeight = FontWeight.Bold,
                        color = DashSuccessGreen
                    )
                }
            }

            if (title.isNotBlank()) {
                Text(
                    text = title,
                    style = MaterialTheme.typography.titleMedium,
                    fontWeight = FontWeight.Bold,
                    color = dashColors().textPrimary
                )
            }

            if (snippet.isNotBlank()) {
                Text(
                    text = snippet,
                    style = MaterialTheme.typography.bodyMedium,
                    color = dashColors().textSecondary,
                    lineHeight = 20.sp
                )
            }

            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.End
            ) {
                Button(
                    onClick = onAskDASH,
                    colors = ButtonDefaults.buttonColors(
                        containerColor = DashPurpleSecondary.copy(alpha = 0.15f),
                        contentColor = DashPurpleSecondary
                    ),
                    shape = RoundedCornerShape(12.dp)
                ) {
                    Icon(imageVector = Icons.Default.AutoAwesome, contentDescription = null, modifier = Modifier.size(14.dp))
                    Spacer(modifier = Modifier.width(4.dp))
                    Text("Ask DASH to Explain", fontSize = 11.sp, fontWeight = FontWeight.Bold)
                }
            }
        }
    }
}
