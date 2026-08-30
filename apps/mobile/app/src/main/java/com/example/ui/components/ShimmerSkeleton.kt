package com.example.ui.components

import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.Spacer
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.height
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.layout.width
import androidx.compose.foundation.shape.CircleShape
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.unit.dp
import com.valentinilk.shimmer.shimmer

/** Base shimmer placeholder box. */
@Composable
private fun ShimmerBox(
    modifier: Modifier = Modifier,
    width: androidx.compose.ui.unit.Dp = 48.dp,
    height: androidx.compose.ui.unit.Dp = 16.dp,
    cornerRadius: androidx.compose.ui.unit.Dp = 6.dp
) {
    Box(
        modifier = modifier
            .width(width)
            .height(height)
            .clip(RoundedCornerShape(cornerRadius))
            .background(Color.White.copy(alpha = 0.08f))
    )
}

/** Shimmer circle placeholder. */
@Composable
private fun ShimmerCircle(
    modifier: Modifier = Modifier,
    size: androidx.compose.ui.unit.Dp = 40.dp
) {
    Box(
        modifier = modifier
            .size(size)
            .clip(CircleShape)
            .background(Color.White.copy(alpha = 0.08f))
    )
}

/** Full-page shimmer skeleton for list-based screens. */
@Composable
fun ShimmerListSkeleton(
    modifier: Modifier = Modifier,
    cardCount: Int = 6,
    showMetrics: Boolean = false,
    showHeader: Boolean = true
) {
    Column(
        modifier = modifier
            .fillMaxWidth()
            .shimmer()
    ) {
        if (showMetrics) {
            // Orb placeholder
            Box(
                modifier = Modifier.fillMaxWidth().height(200.dp),
                contentAlignment = Alignment.Center
            ) { ShimmerCircle(size = 120.dp) }

            // Metric cards row
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp),
                horizontalArrangement = Arrangement.spacedBy(8.dp)
            ) {
                repeat(3) {
                    Column(
                        modifier = Modifier.weight(1f).padding(12.dp),
                        verticalArrangement = Arrangement.spacedBy(6.dp)
                    ) {
                        ShimmerBox(width = 32.dp, height = 10.dp, cornerRadius = 4.dp)
                        ShimmerBox(width = 48.dp, height = 24.dp, cornerRadius = 6.dp)
                    }
                }
            }
            Spacer(modifier = Modifier.height(16.dp))
        }

        // Repeated card skeletons
        repeat(cardCount) {
            Row(
                modifier = Modifier.fillMaxWidth().padding(horizontal = 16.dp, vertical = 4.dp),
                verticalAlignment = Alignment.CenterVertically
            ) {
                ShimmerCircle(size = 40.dp)
                Spacer(modifier = Modifier.width(12.dp))
                Column(verticalArrangement = Arrangement.spacedBy(6.dp)) {
                    ShimmerBox(width = 140.dp, height = 14.dp, cornerRadius = 4.dp)
                    ShimmerBox(width = 90.dp, height = 10.dp, cornerRadius = 4.dp)
                }
            }
        }
    }
}

/** Chat message skeleton — alternating user/DASH bubbles. */
@Composable
fun ShimmerChatSkeleton(
    modifier: Modifier = Modifier,
    messageCount: Int = 5
) {
    Column(
        modifier = modifier.fillMaxWidth().shimmer().padding(horizontal = 16.dp, vertical = 8.dp),
        verticalArrangement = Arrangement.spacedBy(12.dp)
    ) {
        repeat(messageCount) { index ->
            val isUser = index % 2 == 0
            Row(
                modifier = Modifier.fillMaxWidth(),
                horizontalArrangement = if (isUser) Arrangement.End else Arrangement.Start
            ) {
                if (!isUser) {
                    ShimmerCircle(size = 28.dp)
                    Spacer(modifier = Modifier.width(8.dp))
                }
                Column {
                    ShimmerBox(width = if (isUser) 160.dp else 200.dp, height = 14.dp, cornerRadius = 4.dp)
                    Spacer(modifier = Modifier.height(4.dp))
                    ShimmerBox(width = if (isUser) 100.dp else 140.dp, height = 14.dp, cornerRadius = 4.dp)
                }
                if (isUser) {
                    Spacer(modifier = Modifier.width(8.dp))
                    ShimmerCircle(size = 28.dp)
                }
            }
        }
    }
}
