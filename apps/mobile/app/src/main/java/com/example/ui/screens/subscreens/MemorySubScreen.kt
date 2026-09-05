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
import androidx.compose.material.icons.filled.Add
import androidx.compose.material.icons.filled.Delete
import androidx.compose.material.icons.filled.Psychology
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedTextField
import androidx.compose.material3.OutlinedTextFieldDefaults
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
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
import androidx.compose.ui.unit.dp
import androidx.compose.ui.unit.sp
import androidx.compose.ui.window.Dialog
import com.example.data.local.entity.MemoryEntity
import com.example.ui.components.GlassCard
import com.example.ui.components.ShimmerListSkeleton
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashPurpleSecondary
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerHigh
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import com.example.ui.theme.dashColors

@Composable
fun MemorySubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val memories by viewModel.memories.collectAsState()
    var selectedCategory by remember { mutableStateOf("ALL") }
    var showAddDialog by remember { mutableStateOf(false) }

    val categories = listOf("ALL", "Technical", "Projects", "Preferences", "Personal", "Tasks")
    val filteredMemories = if (selectedCategory == "ALL") memories else memories.filter { it.category == selectedCategory }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("memory_screen")
    ) {
        SubScreenHeader(
            title = "Neural Memory",
            subtitle = "${memories.size} Active Memory Entries",
            subtitleColor = DashPurpleSecondary,
            onBack = onBack
        )

        // Category Chips
        LazyRow(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 16.dp, vertical = 10.dp),
            horizontalArrangement = Arrangement.spacedBy(8.dp)
        ) {
            items(categories) { cat ->
                val isSelected = selectedCategory == cat
                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(14.dp))
                        .background(if (isSelected) DashPurpleSecondary.copy(alpha = 0.2f) else Color.White.copy(alpha = 0.04f))
                        .border(1.dp, if (isSelected) DashPurpleSecondary else Color.White.copy(alpha = 0.08f), RoundedCornerShape(14.dp))
                        .clickable { selectedCategory = cat }
                        .padding(horizontal = 12.dp, vertical = 6.dp)
                ) {
                    Text(
                        text = cat,
                        fontSize = 12.sp,
                        fontWeight = if (isSelected) FontWeight.Bold else FontWeight.Normal,
                        color = if (isSelected) DashPurpleSecondary else dashColors().textSecondary
                    )
                }
            }
        }

        // Memories List
        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 8.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Skeleton loading
            if (memories.isEmpty()) {
                item { ShimmerListSkeleton(cardCount = 5) }
            }
            items(filteredMemories, key = { it.id }) { memory ->
                MemoryItemCard(
                    memory = memory,
                    onDelete = { viewModel.deleteMemory(memory.id) }
                )
            }
        }
    }

    if (showAddDialog) {
        AddMemoryDialog(
            onDismiss = { showAddDialog = false },
            onAdd = { category, title, details ->
                viewModel.addMemory(category, title, details)
                showAddDialog = false
            }
        )
    }
}

@Composable
private fun MemoryItemCard(
    memory: MemoryEntity,
    onDelete: () -> Unit
) {
    GlassCard(
        modifier = Modifier.fillMaxWidth().testTag("memory_card_${memory.id}"),
        cornerRadius = 16.dp
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
                            .clip(RoundedCornerShape(8.dp))
                            .background(DashPurpleSecondary.copy(alpha = 0.15f))
                            .padding(horizontal = 8.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = memory.category.uppercase(),
                            fontFamily = FontFamily.Monospace,
                            fontSize = 10.sp,
                            fontWeight = FontWeight.Bold,
                            color = DashPurpleSecondary
                        )
                    }
                    Spacer(modifier = Modifier.width(8.dp))
                    Text(
                        text = "Fidelity ${(memory.confidenceScore * 100).toInt()}%",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 10.sp,
                        color = DashCyanPrimary
                    )
                }

                IconButton(
                    onClick = onDelete,
                    modifier = Modifier.size(28.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Delete,
                        contentDescription = "Forget",
                        tint = dashColors().textMuted,
                        modifier = Modifier.size(16.dp)
                    )
                }
            }

            Text(
                text = memory.title,
                style = MaterialTheme.typography.titleMedium,
                fontWeight = FontWeight.Bold,
                color = dashColors().textPrimary
            )

            Text(
                text = memory.details,
                style = MaterialTheme.typography.bodyMedium,
                color = dashColors().textSecondary,
                lineHeight = 20.sp
            )
        }
    }
}

@Composable
private fun AddMemoryDialog(
    onDismiss: () -> Unit,
    onAdd: (category: String, title: String, details: String) -> Unit
) {
    var category by remember { mutableStateOf("Preferences") }
    var title by remember { mutableStateOf("") }
    var details by remember { mutableStateOf("") }

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
                verticalArrangement = Arrangement.spacedBy(12.dp)
            ) {
                Text(
                    text = "Store Persistent Memory",
                    style = MaterialTheme.typography.titleLarge,
                    fontWeight = FontWeight.Bold,
                    color = DashPurpleSecondary
                )

                OutlinedTextField(
                    value = category,
                    onValueChange = { category = it },
                    label = { Text("Category (Preferences, Technical, Projects)") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashPurpleSecondary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                OutlinedTextField(
                    value = title,
                    onValueChange = { title = it },
                    label = { Text("Title") },
                    modifier = Modifier.fillMaxWidth(),
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashPurpleSecondary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                OutlinedTextField(
                    value = details,
                    onValueChange = { details = it },
                    label = { Text("Details & Context") },
                    modifier = Modifier.fillMaxWidth(),
                    minLines = 3,
                    colors = OutlinedTextFieldDefaults.colors(
                        focusedBorderColor = DashPurpleSecondary,
                        unfocusedBorderColor = dashColors().borderGlass,
                        focusedTextColor = dashColors().textPrimary,
                        unfocusedTextColor = dashColors().textPrimary
                    )
                )

                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
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
                            if (title.isNotBlank() && details.isNotBlank()) {
                                onAdd(category, title, details)
                            }
                        },
                        colors = ButtonDefaults.buttonColors(containerColor = DashPurpleSecondary)
                    ) {
                        Text("Save to Memory", color = Color.White, fontWeight = FontWeight.Bold)
                    }
                }
            }
        }
    }
}
