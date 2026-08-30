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
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Check
import androidx.compose.material.icons.filled.Close
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Shield
import androidx.compose.material.icons.filled.Warning
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Tab
import androidx.compose.material3.TabRow
import androidx.compose.material3.TabRowDefaults
import androidx.compose.material3.TabRowDefaults.tabIndicatorOffset
import androidx.compose.material3.Text
import androidx.compose.runtime.Composable
import androidx.compose.runtime.collectAsState
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableIntStateOf
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
import com.example.data.local.entity.ApprovalEntity
import com.example.ui.components.GlassCard
import com.example.ui.components.ShimmerListSkeleton
import com.example.ui.components.SubScreenHeader
import com.example.ui.theme.DashApprovalAmber
import com.example.ui.theme.DashBackground
import com.example.ui.theme.DashBorderGlass
import com.example.ui.theme.DashCyanPrimary
import com.example.ui.theme.DashErrorRed
import com.example.ui.theme.DashSuccessGreen
import com.example.ui.theme.DashSurface
import com.example.ui.theme.DashSurfaceContainerHigh
import com.example.ui.theme.DashSurfaceContainerLow
import com.example.ui.theme.DashTextMuted
import com.example.ui.theme.DashTextPrimary
import com.example.ui.theme.DashTextSecondary
import com.example.ui.viewmodel.DashViewModel
import com.example.ui.theme.dashColors
import androidx.compose.ui.text.style.TextOverflow

@Composable
fun ApprovalsSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val approvals by viewModel.approvals.collectAsState()
    var selectedTab by remember { mutableIntStateOf(0) }

    val pendingList = approvals.filter { it.status == "PENDING" }
    val resolvedList = approvals.filter { it.status != "PENDING" }

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("approvals_screen")
    ) {
        SubScreenHeader(
            title = "Security Approvals",
            subtitle = "Privileged Action Gateway ● Zero Trust",
            subtitleColor = DashApprovalAmber,
            onBack = onBack
        )

        // Tabs
        TabRow(
            selectedTabIndex = selectedTab,
            containerColor = dashColors().surfaceContainerLow,
            contentColor = DashApprovalAmber,
            indicator = { tabPositions ->
                TabRowDefaults.SecondaryIndicator(
                    modifier = Modifier.tabIndicatorOffset(tabPositions[selectedTab]),
                    color = DashApprovalAmber,
                    height = 2.dp
                )
            }
        ) {
            Tab(
                selected = selectedTab == 0,
                onClick = { selectedTab = 0 },
                text = {
                    Text(
                        text = "Pending (${pendingList.size})",
                        fontWeight = if (selectedTab == 0) FontWeight.Bold else FontWeight.Normal,
                        color = if (selectedTab == 0) DashApprovalAmber else dashColors().textSecondary
                    )
                }
            )
            Tab(
                selected = selectedTab == 1,
                onClick = { selectedTab = 1 },
                text = {
                    Text(
                        text = "Audit History (${resolvedList.size})",
                        fontWeight = if (selectedTab == 1) FontWeight.Bold else FontWeight.Normal,
                        color = if (selectedTab == 1) DashApprovalAmber else dashColors().textSecondary
                    )
                }
            )
        }

        val displayList = if (selectedTab == 0) pendingList else resolvedList

        if (displayList.isEmpty()) {
            Box(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(32.dp),
                contentAlignment = Alignment.Center
            ) {
                Column(
                    horizontalAlignment = Alignment.CenterHorizontally,
                    verticalArrangement = Arrangement.spacedBy(8.dp)
                ) {
                    Icon(
                        imageVector = Icons.Default.Shield,
                        contentDescription = null,
                        tint = DashSuccessGreen,
                        modifier = Modifier.size(48.dp)
                    )
                    Text(
                        text = if (selectedTab == 0) "No Pending Authorizations" else "No Authorization History",
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "All systems nominal.",
                        style = MaterialTheme.typography.bodySmall,
                        color = dashColors().textMuted
                    )
                }
            }
        } else {
            LazyColumn(
                modifier = Modifier
                    .fillMaxSize()
                    .padding(horizontal = 16.dp),
                contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
                verticalArrangement = Arrangement.spacedBy(16.dp)
            ) {
                // Skeleton loading
                if (displayList.isEmpty()) {
                    item { ShimmerListSkeleton(cardCount = 4) }
                }
                items(displayList, key = { it.id }) { item ->
                    ApprovalCard(
                        item = item,
                        onApprove = { viewModel.approveRequest(item.id, item.title) },
                        onReject = { viewModel.rejectRequest(item.id, item.title) }
                    )
                }
            }
        }
    }
}

@Composable
private fun ApprovalCard(
    item: ApprovalEntity,
    onApprove: () -> Unit,
    onReject: () -> Unit
) {
    val isPending = item.status == "PENDING"
    val isApproved = item.status == "APPROVED"

    GlassCard(
        modifier = Modifier.fillMaxWidth().testTag("approval_card_${item.id}"),
        backgroundColor = if (isPending) dashColors().surfaceContainerLow.copy(alpha = 0.9f) else dashColors().surfaceContainerLow.copy(alpha = 0.5f),
        borderColor = if (isPending) DashApprovalAmber.copy(alpha = 0.35f) else dashColors().borderGlass
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(18.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp)
        ) {
            // Title & Level Pill
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = Arrangement.SpaceBetween,
                verticalAlignment = Alignment.CenterVertically
            ) {
                Column(modifier = Modifier.weight(1f)) {
                    Text(
                        text = item.title,
                        style = MaterialTheme.typography.titleMedium,
                        fontWeight = FontWeight.Bold,
                        color = dashColors().textPrimary
                    )
                    Text(
                        text = "${item.category} ● ${item.timeAgo}",
                        maxLines = 1,
                        overflow = TextOverflow.Ellipsis,
                        style = MaterialTheme.typography.labelSmall,
                        color = DashApprovalAmber,
                        fontFamily = FontFamily.Monospace
                    )
                }

                Box(
                    modifier = Modifier
                        .clip(RoundedCornerShape(8.dp))
                        .background(DashApprovalAmber.copy(alpha = 0.15f))
                        .border(1.dp, DashApprovalAmber.copy(alpha = 0.3f), RoundedCornerShape(8.dp))
                        .padding(horizontal = 8.dp, vertical = 4.dp)
                ) {
                    Text(
                        text = "LEVEL ${item.permissionLevel}",
                        fontFamily = FontFamily.Monospace,
                        fontSize = 11.sp,
                        fontWeight = FontWeight.Bold,
                        color = DashApprovalAmber
                    )
                }
            }

            // Reason
            Text(
                text = item.reason,
                style = MaterialTheme.typography.bodyMedium,
                color = dashColors().textSecondary
            )

            // Code Diff or Command Box
            Box(
                modifier = Modifier
                    .fillMaxWidth()
                    .clip(RoundedCornerShape(10.dp))
                    .background(Color.Black.copy(alpha = 0.6f))
                    .border(1.dp, dashColors().borderGlass, RoundedCornerShape(10.dp))
                    .padding(12.dp)
            ) {
                Text(
                    text = item.diffOrCommand,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 11.sp,
                    color = DashCyanPrimary,
                    lineHeight = 16.sp
                )
            }

            // Actions or Status
            if (isPending) {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End,
                    verticalAlignment = Alignment.CenterVertically
                ) {
                    Button(
                        onClick = onReject,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DashErrorRed.copy(alpha = 0.15f),
                            contentColor = DashErrorRed
                        ),
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.testTag("reject_button_${item.id}")
                    ) {
                        Icon(imageVector = Icons.Default.Close, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Reject", fontWeight = FontWeight.Bold)
                    }

                    Spacer(modifier = Modifier.width(10.dp))

                    Button(
                        onClick = onApprove,
                        colors = ButtonDefaults.buttonColors(
                            containerColor = DashApprovalAmber,
                            contentColor = dashColors().surface
                        ),
                        shape = RoundedCornerShape(14.dp),
                        modifier = Modifier.testTag("approve_button_${item.id}")
                    ) {
                        Icon(imageVector = Icons.Default.Check, contentDescription = null, modifier = Modifier.size(16.dp))
                        Spacer(modifier = Modifier.width(4.dp))
                        Text("Authorize (L${item.permissionLevel})", fontWeight = FontWeight.Bold)
                    }
                }
            } else {
                Row(
                    modifier = Modifier.fillMaxWidth(),
                    horizontalArrangement = Arrangement.End
                ) {
                    Box(
                        modifier = Modifier
                            .clip(CircleShape)
                            .background(
                                if (isApproved) DashSuccessGreen.copy(alpha = 0.15f)
                                else DashErrorRed.copy(alpha = 0.15f)
                            )
                            .padding(horizontal = 12.dp, vertical = 4.dp)
                    ) {
                        Text(
                            text = item.status,
                            fontFamily = FontFamily.Monospace,
                            fontSize = 11.sp,
                            fontWeight = FontWeight.Bold,
                            color = if (isApproved) DashSuccessGreen else DashErrorRed
                        )
                    }
                }
            }
        }
    }
}
