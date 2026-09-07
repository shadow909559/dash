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

                // Transcript (current state label)
                GlassCard(