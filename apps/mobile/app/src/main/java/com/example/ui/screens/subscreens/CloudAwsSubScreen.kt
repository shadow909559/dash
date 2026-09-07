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
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.Cloud
import androidx.compose.material.icons.filled.CloudDone
import androidx.compose.material.icons.filled.Hub
import androidx.compose.material.icons.filled.Lock
import androidx.compose.material.icons.filled.Storage
import androidx.compose.material3.Button
import androidx.compose.material3.ButtonDefaults
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
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
fun CloudAwsSubScreen(
    viewModel: DashViewModel,
    onBack: () -> Unit,
    modifier: Modifier = Modifier
) {
    val systemMetrics by viewModel.systemMetrics.collectAsState()

    Column(
        modifier = modifier
            .fillMaxSize()
            .background(dashColors().background)
            .testTag("cloud_aws_screen")
    ) {
        SubScreenHeader(
            title = "AWS & Cloud Infrastructure",
            subtitle = "${systemMetrics.awsRegion} - Operational",
            subtitleColor = DashCyanPrimary,
            onBack = onBack
        )

        LazyColumn(
            modifier = Modifier
                .fillMaxSize()
                .padding(horizontal = 16.dp),
            contentPadding = PaddingValues(top = 16.dp, bottom = 100.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp)
        ) {
            // S3 Storage Allocation Meter Card
            item {
                GlassCard(
                    modifier = Modifier.fillMaxWidth(),
                    backgroundColor = dashColors().surfaceContainerLow.copy(alpha = 0.85f)
                ) {
                    Column(
                        modifier = Modifier
                            .fillMaxWidth()
                            .padding(18.dp),
                        verticalArrangement = Arrangement.spacedBy(12.dp)
                    ) {
                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween,
                            verticalAlignment = Alignment.CenterVertically
                        ) {
                            Row(verticalAlignment = Alignment.CenterVertically) {
                                Box(
                                    modifier = Modifier
                                        .size(36.dp)
                                        .clip(CircleShape)
                                        .background(DashApprovalAmber.copy(alpha = 0.15f)),
                                    contentAlignment = Alignment.Center
                                ) {
                                    Icon(
                                        imageVector = Icons.Default.Storage,
                                        contentDescription = null,
                                        tint = DashApprovalAmber,
                                        modifier = Modifier.size(20.dp)
                                    )
                                }
                                Spacer(modifier = Modifier.width(10.dp))
                                Column {
                                    Text(
                                        text = "S3 Encrypted Vault Sync",
                                        style = MaterialTheme.typography.titleMedium,
                                        fontWeight = FontWeight.Bold,
                                        color = dashColors().textPrimary
                                    )
                                    Text(
                                        text = "Bucket: s3://dash-vault-us-east-1",
                                        style = MaterialTheme.typography.labelSmall,
                                        color = dashColors().textMuted,
                                        fontFamily = FontFamily.Monospace
                                    )
                                }
                            }

                            Text(
                                text = "${systemMetrics.cloudStorageAllocatedTb}/${systemMetrics.cloudStorageTotalLimitTb} TB",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 12.sp,
                                fontWeight = FontWeight.Bold,
                                color = DashCyanPrimary
                            )
                        }

                        // Progress Bar (64%)
                        val usedPercent = systemMetrics.cloudStorageAllocatedTb / systemMetrics.cloudStorageTotalLimitTb
                        LinearProgressIndicator(
                            progress = { usedPercent },
                            modifier = Modifier
                                .fillMaxWidth()
                                .height(8.dp)
                                .clip(RoundedCornerShape(4.dp)),
                            color = DashApprovalAmber,
                            trackColor = Color.White.copy(alpha = 0.1f)
                        )

                        Row(
                            modifier = Modifier.fillMaxWidth(),
                            horizontalArrangement = Arrangement.SpaceBetween
                        ) {
                            Text(
                                text = "AES-256 GCM Client-Side Encrypted",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp,
                                color = DashSuccessGreen
                            )
                            Text(
                                text = "Synced ${systemMetrics.lastSyncTime}",
                                fontFamily = FontFamily.Monospace,
                                fontSize = 10.sp,
                                color = dashColors().textMuted
                            )
                        }
                    }
                }
            }

            // AWS Active Services Grid
            item {
                Text(
                    text = "DEPLOYED CLOUD SERVICES",
                    style = MaterialTheme.typography.labelSmall,
                    color = dashColors().textMuted,
                    letterSpacing = 1.2.sp
                )
                Spacer(modifier = Modifier.height(6.dp))

                Column(verticalArrangement = Arrangement.spacedBy(10.dp)) {
                    CloudServiceRow(
                        name = "Amazon Bedrock (Claude 3.5 Sonnet)",
                        category = "Generative AI Foundation Model",
                        status = "Connected ● 320ms",
                        statusColor = DashCyanPrimary
                    )
                    CloudServiceRow(
                        name = "AWS Lambda (Remote Webhook Daemon)",
                        category = "Serverless Task Dispatcher",
                        status = "Active ● 12 Executions today",
                        statusColor = DashSuccessGreen
                    )
                    CloudServiceRow(
                        name = "Amazon CloudWatch Logs",
                        category = "System & Security Audit Log Stream",
                        status = "Streaming ● Normal",
                        statusColor = DashSuccessGreen
                    )
                    CloudServiceRow(
                        name = "AWS Secrets Manager",
                        category = "Encrypted Token Vault",
                        status = "Locked ● Zero Trust",
                        statusColor = DashPurpleSecondary
                    )
                }
            }
        }
    }
}

@Composable
private fun CloudServiceRow(
    name: String,
    category: String,
    status: String,
    statusColor: Color
) {
    GlassCard(
        modifier = Modifier.fillMaxWidth(),
        cornerRadius = 14.dp
    ) {
        Row(
            modifier = Modifier
                .fillMaxWidth()
                .padding(14.dp),
            verticalAlignment = Alignment.CenterVertically,
            horizontalArrangement = Arrangement.SpaceBetween
        ) {
            Column(modifier = Modifier.weight(1f)) {
                Text(
                    text = name,
                    style = MaterialTheme.typography.titleSmall,
                    fontWeight = FontWeight.SemiBold,
                    color = dashColors().textPrimary
                )
                Text(
                    text = category,
                    style = MaterialTheme.typography.labelSmall,
                    color = dashColors().textMuted
                )
            }

            Box(
                modifier = Modifier
                    .clip(CircleShape)
                    .background(statusColor.copy(alpha = 0.12f))
                    .padding(horizontal = 8.dp, vertical = 4.dp)
            ) {
                Text(
                    text = status,
                    fontFamily = FontFamily.Monospace,
                    fontSize = 10.sp,
                    fontWeight = FontWeight.Bold,
                    color = statusColor
                )
            }
        }
    }
}
