import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../automation/models/automation.dart';
import '../automation/providers/automation_provider.dart';

class AutomationHistoryPage extends ConsumerWidget {
  const AutomationHistoryPage({super.key, required this.automationId});

  final String automationId;

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final historyState = ref.watch(automationHistoryProvider(automationId));
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(automationHistoryProvider(automationId).notifier).loadHistory();
    });

    return Scaffold(
      appBar: AppBar(
        title: const Text('Execution History'),
      ),
      body: historyState.isLoading && historyState.items.isEmpty
          ? const Center(child: CircularProgressIndicator())
          : historyState.errorMessage != null && historyState.items.isEmpty
              ? Center(
                  child: Column(
                    children: [
                      Icon(Icons.error_outline,
                          size: 48, color: colorScheme.error),
                      const SizedBox(height: 16),
                      Text('Failed to load history',
                          style: theme.textTheme.bodyLarge),
                      const SizedBox(height: 8),
                      Text(historyState.errorMessage!,
                          style: theme.textTheme.bodySmall?.copyWith(
                            color: colorScheme.onSurface.withValues(alpha: 0.6),
                          )),
                      const SizedBox(height: 16),
                      FilledButton.icon(
                        onPressed: () => ref
                            .read(automationHistoryProvider(automationId).notifier)
                            .loadHistory(),
                        icon: const Icon(Icons.refresh),
                        label: const Text('Retry'),
                      ),
                    ],
                  ),
                )
              : historyState.items.isEmpty
                  ? Center(
                      child: Column(
                        children: [
                          Icon(Icons.history,
                              size: 48,
                              color: colorScheme.onSurface.withValues(alpha: 0.3)),
                          const SizedBox(height: 16),
                          Text('No executions yet',
                              style: theme.textTheme.bodyLarge?.copyWith(
                                color: colorScheme.onSurface.withValues(alpha: 0.6),
                              )),
                        ],
                      ),
                    )
                  : ListView.builder(
                      padding: const EdgeInsets.symmetric(vertical: 8),
                      itemCount: historyState.items.length,
                      itemBuilder: (context, index) {
                        final item = historyState.items[index];
                        return _HistoryTile(history: item);
                      },
                    ),
    );
  }
}

class _HistoryTile extends StatelessWidget {
  const _HistoryTile({required this.history});

  final AutomationHistory history;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    final statusColor = switch (history.status.toLowerCase()) {
      'completed' || 'success' => Colors.green,
      'failed' || 'error' => Colors.red,
      'running' || 'in_progress' => Colors.orange,
      _ => colorScheme.primary,
    };

    return Card(
      margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: ExpansionTile(
        leading: Icon(
          history.status.toLowerCase() == 'failed' || history.status.toLowerCase() == 'error'
              ? Icons.error_outline
              : Icons.check_circle_outline,
          color: statusColor,
        ),
        title: Text(
          history.summary ?? history.status,
          style: theme.textTheme.titleSmall,
        ),
        subtitle: Text(
          _formatDateTime(history.startedAt),
          style: theme.textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
        children: [
          Padding(
            padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                _InfoRow(label: 'Status', value: history.status),
                if (history.output != null)
                  _InfoRow(label: 'Output', value: history.output!),
                if (history.error != null)
                  _InfoRow(
                    label: 'Error',
                    value: history.error!,
                    valueColor: colorScheme.error,
                  ),
                _InfoRow(
                  label: 'Started',
                  value: _formatDateTime(history.startedAt),
                ),
                if (history.finishedAt != null)
                  _InfoRow(
                    label: 'Finished',
                    value: _formatDateTime(history.finishedAt!),
                  ),
                if (history.durationMs != null)
                  _InfoRow(
                    label: 'Duration',
                    value: '${history.durationMs} ms',
                  ),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({
    required this.label,
    required this.value,
    this.valueColor,
  });

  final String label;
  final String value;
  final Color? valueColor;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 80,
            child: Text(
              label,
              style: theme.textTheme.bodySmall?.copyWith(
                fontWeight: FontWeight.w600,
                color: theme.colorScheme.onSurface.withValues(alpha: 0.7),
              ),
            ),
          ),
          Expanded(
            child: Text(
              value,
              style: theme.textTheme.bodySmall?.copyWith(color: valueColor),
            ),
          ),
        ],
      ),
    );
  }
}

String _formatDateTime(DateTime dt) {
  final now = DateTime.now();
  final diff = now.difference(dt);
  if (diff.inMinutes < 1) return 'Just now';
  if (diff.inMinutes < 60) return '${diff.inMinutes}m ago';
  if (diff.inHours < 24) return '${diff.inHours}h ago';
  return '${dt.day}/${dt.month}/${dt.year} ${dt.hour}:${dt.minute.toString().padLeft(2, '0')}';
}
