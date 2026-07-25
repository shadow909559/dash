import 'package:flutter/material.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import '../../chat/models/chat_message.dart';

class MessageBubble extends StatelessWidget {
  final ChatMessage message;
  final bool isUser;
  final VoidCallback? onCopy;
  final VoidCallback? onRegenerate;
  final VoidCallback? onRetry;

  const MessageBubble({
    super.key,
    required this.message,
    required this.isUser,
    this.onCopy,
    this.onRegenerate,
    this.onRetry,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        mainAxisAlignment: isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
        children: [
          if (!isUser) _buildAvatar(theme),
          const SizedBox(width: 8),
          Flexible(
            child: Column(
              crossAxisAlignment: isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
              children: [
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 10),
                  decoration: BoxDecoration(
                    color: isUser
                        ? theme.colorScheme.primaryContainer
                        : theme.colorScheme.surfaceContainerHighest,
                    borderRadius: BorderRadius.only(
                      topLeft: const Radius.circular(18),
                      topRight: const Radius.circular(18),
                      bottomLeft: Radius.circular(isUser ? 18 : 4),
                      bottomRight: Radius.circular(isUser ? 4 : 18),
                    ),
                  ),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      if (message.content.isNotEmpty)
                        isUser
                            ? SelectableText(message.content, style: theme.textTheme.bodyMedium)
                            : MarkdownBody(
                                data: message.content,
                                selectable: true,
                                styleSheet: MarkdownStyleSheet(
                                  p: theme.textTheme.bodyMedium,
                                  code: TextStyle(
                                    backgroundColor: theme.colorScheme.surfaceContainerHighest,
                                    fontFamily: 'monospace',
                                    fontSize: 13,
                                  ),
                                  codeblockDecoration: BoxDecoration(
                                    color: theme.colorScheme.surfaceDim,
                                    borderRadius: BorderRadius.circular(8),
                                  ),
                                ),
                              ),
                      if (message.isStreaming)
                        const SizedBox(
                          height: 20,
                          width: 20,
                          child: Center(child: SizedBox(
                            width: 12, height: 12,
                            child: CircularProgressIndicator(strokeWidth: 2),
                          )),
                        ),
                    ],
                  ),
                ),
                const SizedBox(height: 2),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    Text(
                      _formatTime(message.timestamp),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: theme.colorScheme.onSurfaceVariant,
                      ),
                    ),
                    if (message.tokenCount != null) ...[
                      const SizedBox(width: 8),
                      Text(
                        '${message.tokenCount} tokens',
                        style: theme.textTheme.labelSmall?.copyWith(
                          color: theme.colorScheme.onSurfaceVariant,
                        ),
                      ),
                    ],
                    if (onCopy != null) ...[
                      const SizedBox(width: 8),
                      InkWell(
                        onTap: onCopy,
                        child: Icon(Icons.copy, size: 14, color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                    if (onRegenerate != null && !isUser) ...[
                      const SizedBox(width: 8),
                      InkWell(
                        onTap: onRegenerate,
                        child: Icon(Icons.refresh, size: 14, color: theme.colorScheme.onSurfaceVariant),
                      ),
                    ],
                    if (onRetry != null && isUser && message.hasError) ...[
                      const SizedBox(width: 8),
                      InkWell(
                        onTap: onRetry,
                        child: Icon(Icons.error_outline, size: 14, color: theme.colorScheme.error),
                      ),
                    ],
                  ],
                ),
              ],
            ),
          ),
          if (isUser) const SizedBox(width: 8),
        ],
      ),
    );
  }

  Widget _buildAvatar(ThemeData theme) {
    return CircleAvatar(
      radius: 16,
      backgroundColor: theme.colorScheme.primaryContainer,
      child: Icon(Icons.auto_awesome, size: 16, color: theme.colorScheme.onPrimaryContainer),
    );
  }

  String _formatTime(DateTime? dt) {
    if (dt == null) return '';
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m';
    if (diff.inDays < 1) return '${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
    return '${dt.month}/${dt.day}';
  }
}