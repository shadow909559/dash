import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';
import 'package:shimmer/shimmer.dart';

import 'models/chat_message.dart';
import 'models/conversation.dart';
import 'providers/conversation_provider.dart';
import 'services/conversation_repository.dart';

class ConversationDetailsPage extends ConsumerStatefulWidget {
  const ConversationDetailsPage({super.key, required this.conversationId});

  final String conversationId;

  @override
  ConsumerState<ConversationDetailsPage> createState() => _ConversationDetailsPageState();
}

class _ConversationDetailsPageState extends ConsumerState<ConversationDetailsPage> {
  @override
  Widget build(BuildContext context) {
    final repo = ref.read(conversationRepositoryProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Conversation Details'),
      ),
      body: FutureBuilder<Conversation>(
        future: repo.get(widget.conversationId),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return _buildSkeleton(theme, colorScheme);
          }
          if (snapshot.hasError) {
            return _buildError(context, theme, colorScheme, snapshot.error.toString());
          }
          final conv = snapshot.data!;
          return _buildDetails(context, ref, conv, theme, colorScheme, repo);
        },
      ),
    );
  }

  Widget _buildSkeleton(ThemeData theme, ColorScheme colorScheme) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Shimmer.fromColors(
          baseColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          highlightColor: colorScheme.surfaceContainerHighest,
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(width: double.infinity, height: 32, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(8))),
              const SizedBox(height: 16),
              Container(width: 200, height: 14, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
              const SizedBox(height: 24),
              Container(width: double.infinity, height: 180, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12))),
              const SizedBox(height: 24),
              Container(width: double.infinity, height: 180, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12))),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildError(BuildContext context, ThemeData theme, ColorScheme colorScheme, String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.error_outline, size: 40, color: colorScheme.error),
            ),
            const SizedBox(height: 16),
            Text('Something went wrong', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text(error, textAlign: TextAlign.center, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
            const SizedBox(height: 16),
            FilledButton.tonal(onPressed: () => setState(() {}), child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _buildDetails(BuildContext context, WidgetRef ref, Conversation conv, ThemeData theme, ColorScheme colorScheme, ConversationRepository repo) {
    final dateFormat = DateFormat('MMM d, y · h:mm a');
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Icon(Icons.chat_bubble_outline, color: colorScheme.primary, size: 28),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        conv.displayTitle,
                        style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                _buildMetaRow(Icons.public, conv.model ?? 'Default model'),
                const SizedBox(height: 8),
                _buildMetaRow(Icons.message_outlined, '${conv.messageCount} messages'),
                const SizedBox(height: 8),
                _buildMetaRow(Icons.timeline, 'Created ${dateFormat.format(conv.createdAt)}'),
                const SizedBox(height: 8),
                _buildMetaRow(Icons.update, 'Updated ${dateFormat.format(conv.updatedAt)}'),
                if (conv.tokenCount > 0) ...[
                  const SizedBox(height: 8),
                  _buildMetaRow(Icons.token, '${conv.tokenCount} tokens'),
                ],
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        Text('Actions', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        _buildActionTile(context, ref, conv, Icons.edit_outlined, 'Rename', () async {
          final newTitle = await _showRenameDialog(context, theme, conv.displayTitle);
          if (newTitle != null && newTitle.isNotEmpty) {
            await ref.read(conversationListProvider.notifier).rename(conv.id, newTitle);
            if (mounted) setState(() {});
          }
        }),
        _buildActionTile(context, ref, conv, Icons.push_pin_outlined,
            conv.isPinned ? 'Unpin' : 'Pin', () async {
          await ref.read(conversationListProvider.notifier).togglePin(conv.id);
          if (mounted) setState(() {});
        }),
        _buildActionTile(context, ref, conv, Icons.archive_outlined, 'Archive', () async {
          final confirm = await _showConfirmDialog(context, theme, 'Archive conversation?', 'This will move it to archived.');
          if (confirm == true) {
            await ref.read(conversationListProvider.notifier).archive(conv.id);
            if (mounted) {
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Conversation archived')));
              Navigator.pop(context);
            }
          }
        }),
        _buildActionTile(context, ref, conv, Icons.delete_outline, 'Delete', () async {
          final confirm = await _showConfirmDialog(context, theme, 'Delete conversation?', 'This will permanently delete "${conv.displayTitle}" and all its messages.');
          if (confirm == true) {
            final success = await ref.read(conversationListProvider.notifier).delete(conv.id);
            if (success && mounted) {
              ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Conversation deleted')));
              Navigator.pop(context);
            }
          }
        }),
        const SizedBox(height: 16),
        Text('Messages', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        FutureBuilder<MessageListResponse>(
          future: repo.getMessages(widget.conversationId, limit: 50),
          builder: (context, snapshot) {
            if (snapshot.connectionState == ConnectionState.waiting) {
              return const Center(child: Padding(padding: EdgeInsets.all(16), child: CircularProgressIndicator()));
            }
            if (snapshot.hasError || (snapshot.data?.items.isEmpty ?? true)) {
              return Center(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Column(
                    children: [
                      Icon(Icons.inbox_outlined, size: 48, color: colorScheme.onSurface.withValues(alpha: 0.3)),
                      const SizedBox(height: 12),
                      Text('No messages yet', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                    ],
                  ),
                ),
              );
            }
            final messages = snapshot.data!.items;
            return Column(
              crossAxisAlignment: CrossAxisAlignment.stretch,
              children: messages.map((m) {
                return Padding(
                  padding: const EdgeInsets.symmetric(vertical: 4),
                  child: _MessagePreview(
                    message: m,
                    onCopy: () {
                      Clipboard.setData(ClipboardData(text: m.content));
                      ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Message copied'), duration: Duration(seconds: 1)));
                    },
                  ),
                );
              }).toList(),
            );
          },
        ),
      ],
    );
  }

  Widget _buildMetaRow(IconData icon, String text) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Row(
      children: [
        Icon(icon, size: 16, color: colorScheme.onSurfaceVariant),
        const SizedBox(width: 8),
        Expanded(child: Text(text, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurfaceVariant))),
      ],
    );
  }

  Widget _buildActionTile(BuildContext context, WidgetRef ref, Conversation conv, IconData icon, String label, VoidCallback onTap) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return ListTile(
      leading: Icon(icon, color: colorScheme.onSurfaceVariant),
      title: Text(label),
      trailing: Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
      onTap: onTap,
    );
  }

  Future<String?> _showRenameDialog(BuildContext context, ThemeData theme, String current) {
    final controller = TextEditingController(text: current);
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Rename conversation'),
        content: TextField(controller: controller, autofocus: true, decoration: const InputDecoration(hintText: 'Enter new name')),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, controller.text.trim()), child: const Text('Rename')),
        ],
      ),
    ).then((value) { controller.dispose(); return value; });
  }

  Future<bool?> _showConfirmDialog(BuildContext context, ThemeData theme, String title, String body) {
    return showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text(title),
        content: Text(body),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: theme.colorScheme.error),
            onPressed: () => Navigator.pop(ctx, true),
            child: const Text('Confirm'),
          ),
        ],
      ),
    );
  }
}

class _MessagePreview extends StatelessWidget {
  const _MessagePreview({
    required this.message,
    required this.onCopy,
  });

  final ChatMessage message;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isUser = message.isUser;

    return Container(
      padding: const EdgeInsets.all(12),
      decoration: BoxDecoration(
        color: isUser
            ? theme.colorScheme.primaryContainer.withValues(alpha: 0.5)
            : theme.colorScheme.surfaceContainerHighest,
        borderRadius: BorderRadius.circular(8),
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Row(
            children: [
              Icon(
                isUser ? Icons.person : Icons.auto_awesome,
                size: 14,
                color: theme.colorScheme.onSurfaceVariant,
              ),
              const SizedBox(width: 4),
              Text(
                isUser ? 'You' : 'Assistant',
                style: theme.textTheme.labelSmall?.copyWith(
                  color: theme.colorScheme.onSurfaceVariant,
                  fontWeight: FontWeight.w600,
                ),
              ),
              const Spacer(),
              InkWell(
                onTap: onCopy,
                borderRadius: BorderRadius.circular(4),
                child: Padding(
                  padding: const EdgeInsets.all(2),
                  child: Icon(Icons.content_copy, size: 12, color: theme.colorScheme.onSurface.withValues(alpha: 0.4)),
                ),
              ),
            ],
          ),
          const SizedBox(height: 4),
          Text(
            message.content,
            maxLines: 3,
            overflow: TextOverflow.ellipsis,
            style: theme.textTheme.bodySmall?.copyWith(height: 1.4),
          ),
        ],
      ),
    );
  }
}
