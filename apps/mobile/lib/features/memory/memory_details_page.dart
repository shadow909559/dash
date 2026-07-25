import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shimmer/shimmer.dart';
import 'package:intl/intl.dart';

import 'models/memory_item.dart';
import 'services/memory_service.dart';
import 'memory_provider.dart';

class MemoryDetailsPage extends ConsumerStatefulWidget {
  const MemoryDetailsPage({super.key, required this.memoryId});

  final String memoryId;

  @override
  ConsumerState<MemoryDetailsPage> createState() => _MemoryDetailsPageState();
}

class _MemoryDetailsPageState extends ConsumerState<MemoryDetailsPage> {
  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Memory Details'),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) async {
              switch (value) {
                case 'delete':
                  _showDeleteDialog(context);
                  break;
              }
            },
            itemBuilder: (context) => [
              const PopupMenuItem(value: 'delete', child: Text('Delete')),
            ],
          ),
        ],
      ),
      body: FutureBuilder<dynamic>(
        future: ref.read(memoryServiceProvider).getMemory(widget.memoryId),
        builder: (context, snapshot) {
          if (snapshot.connectionState == ConnectionState.waiting) {
            return _buildSkeleton(theme, colorScheme);
          }
          if (snapshot.hasError) {
            return _buildErrorState(context, theme, colorScheme, snapshot.error.toString());
          }
          if (snapshot.data == null) {
            return _buildErrorState(context, theme, colorScheme, 'Memory not found');
          }
          final memory = MemoryItem.fromJson(snapshot.data as Map<String, dynamic>);
          return _buildDetails(context, memory, theme, colorScheme);
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
              Container(width: double.infinity, height: 120, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12))),
              const SizedBox(height: 24),
              Container(width: double.infinity, height: 80, decoration: BoxDecoration(color: colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(12))),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildErrorState(BuildContext context, ThemeData theme, ColorScheme colorScheme, String error) {
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

  Widget _buildDetails(BuildContext context, MemoryItem memory, ThemeData theme, ColorScheme colorScheme) {
    final dateFormat = DateFormat('MMM d, y · h:mm a');

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Category and metadata card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    _buildCategoryIcon(memory.category, colorScheme),
                    const SizedBox(width: 12),
                    Expanded(
                      child: Text(
                        memory.category.toUpperCase(),
                        style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
                      ),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                if (memory.importance != null)
                  _buildImportanceBar(memory.importance!, colorScheme),
                const SizedBox(height: 8),
                _buildMetaRow(Icons.category_outlined, memory.category),
                const SizedBox(height: 8),
                _buildMetaRow(Icons.timeline_outlined, dateFormat.format(memory.createdAt)),
                if (memory.source != null) ...[
                  const SizedBox(height: 8),
                  _buildMetaRow(Icons.link_outlined, memory.source!),
                ],
              ],
            ),
          ),
        ),

        const SizedBox(height: 16),

        // Content card
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Text('Content', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
                const SizedBox(height: 8),
                Text(
                  memory.content,
                  style: theme.textTheme.bodyMedium?.copyWith(height: 1.6),
                ),
              ],
            ),
          ),
        ),

        const SizedBox(height: 24),

        // Actions
        Text('Actions', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
        const SizedBox(height: 8),
        _buildActionTile(Icons.delete_outline, 'Delete', () => _showDeleteDialog(context), colorScheme),
      ],
    );
  }

  Widget _buildCategoryIcon(String category, ColorScheme colorScheme) {
    IconData icon;
    switch (category.toLowerCase()) {
      case 'conversation':
        icon = Icons.chat_bubble_outline;
        break;
      case 'fact':
        icon = Icons.fact_check_outlined;
        break;
      case 'preference':
        icon = Icons.favorite_outline;
        break;
      case 'task':
        icon = Icons.task_alt;
        break;
      case 'note':
        icon = Icons.note_outlined;
        break;
      default:
        icon = Icons.memory_outlined;
    }
    return CircleAvatar(
      backgroundColor: colorScheme.primaryContainer,
      child: Icon(icon, color: colorScheme.onPrimaryContainer),
    );
  }

  Widget _buildImportanceBar(int importance, ColorScheme colorScheme) {
    final clamped = (importance / 10.0).clamp(0.0, 1.0);
    Color barColor;
    if (clamped >= 0.7) {
      barColor = Colors.red;
    } else if (clamped >= 0.4) {
      barColor = Colors.orange;
    } else {
      barColor = Colors.green;
    }

    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Row(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Text('Importance', style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
            Text('$importance/10', style: TextStyle(fontSize: 12, color: colorScheme.onSurfaceVariant)),
          ],
        ),
        const SizedBox(height: 4),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: clamped,
            backgroundColor: colorScheme.surfaceContainerHighest,
            valueColor: AlwaysStoppedAnimation<Color>(barColor),
            minHeight: 6,
          ),
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

  Widget _buildActionTile(IconData icon, String label, VoidCallback onTap, ColorScheme colorScheme) {
    return ListTile(
      leading: Icon(icon, color: colorScheme.onSurfaceVariant),
      title: Text(label),
      trailing: Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
      onTap: onTap,
    );
  }

  void _showDeleteDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete memory?'),
        content: const Text('This will permanently delete this memory.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            style: FilledButton.styleFrom(backgroundColor: Theme.of(context).colorScheme.error),
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(memoryProvider.notifier).deleteMemory(widget.memoryId);
              if (mounted) Navigator.pop(context);
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}