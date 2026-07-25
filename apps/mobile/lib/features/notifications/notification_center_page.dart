import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../notifications/providers/notification_provider.dart';
import '../notifications/models/notification_item.dart';

class NotificationCenterPage extends ConsumerWidget {
  const NotificationCenterPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final state = ref.watch(notificationProvider);
    final notifier = ref.read(notificationProvider.notifier);

    final grouped = _groupByDate(state.notifications);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Notifications'),
        actions: [
          if (state.unreadCount > 0)
            TextButton(
              onPressed: notifier.markAllAsRead,
              child: Text('Mark all read', style: TextStyle(color: colorScheme.primary)),
            ),
        ],
      ),
      body: _buildBody(state, grouped, theme, colorScheme, notifier),
    );
  }

  Widget _buildBody(
    NotificationState state,
    Map<String, List<NotificationItem>> grouped,
    ThemeData theme,
    ColorScheme colorScheme,
    NotificationNotifier notifier,
  ) {
    if (state.isLoading && state.notifications.isEmpty) {
      return _buildLoadingSkeleton(theme, colorScheme);
    }

    if (state.notifications.isEmpty) {
      return _buildEmptyState(theme, colorScheme);
    }

    return RefreshIndicator(
      onRefresh: notifier.loadNotifications,
      child: ListView.builder(
        padding: const EdgeInsets.symmetric(vertical: 12),
        itemCount: grouped.keys.length,
        itemBuilder: (context, index) {
          final dateKey = grouped.keys.elementAt(index);
          final items = grouped[dateKey]!;
          return _DateGroup(dateLabel: dateKey, items: items, theme: theme, colorScheme: colorScheme, notifier: notifier);
        },
      ),
    );
  }

  Widget _buildLoadingSkeleton(ThemeData theme, ColorScheme colorScheme) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: 6,
      itemBuilder: (_, __) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(width: 36, height: 36, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(8))),
                const SizedBox(width: 12),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(height: 12, width: 140, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                  const SizedBox(height: 8),
                  Container(height: 10, width: 200, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                ])),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme, ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.notifications_off_rounded, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text('No notifications', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('You are all caught up', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      ),
    );
  }

  Map<String, List<NotificationItem>> _groupByDate(List<NotificationItem> notifications) {
    final now = DateTime.now();
    final today = DateTime(now.year, now.month, now.day);
    final yesterday = today.subtract(const Duration(days: 1));
    final weekStart = today.subtract(Duration(days: today.weekday - 1));

    final groups = <String, List<NotificationItem>>{};

    for (final n in notifications) {
      final date = DateTime(n.timestamp.year, n.timestamp.month, n.timestamp.day);
      String label;
      if (date == today) {
        label = 'Today';
      } else if (date == yesterday) {
        label = 'Yesterday';
      } else if (date.isAfter(weekStart)) {
        label = 'This Week';
      } else {
        label = DateFormat('MMM d, y').format(n.timestamp);
      }

      groups[label] = [...(groups[label] ?? []), n];
    }

    final ordered = <String, List<NotificationItem>>{};
    for (final key in ['Today', 'Yesterday', 'This Week'] as Iterable<String>) {
      if (groups.containsKey(key)) {
        ordered[key] = groups[key]!;
      }
    }
    for (final entry in groups.entries) {
      if (!['Today', 'Yesterday', 'This Week'].contains(entry.key)) {
        ordered[entry.key] = entry.value;
      }
    }

    return ordered;
  }
}

class _DateGroup extends StatelessWidget {
  final String dateLabel;
  final List<NotificationItem> items;
  final ThemeData theme;
  final ColorScheme colorScheme;
  final NotificationNotifier notifier;

  const _DateGroup({
    required this.dateLabel,
    required this.items,
    required this.theme,
    required this.colorScheme,
    required this.notifier,
  });

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 16),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Padding(
            padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
            child: Text(
              dateLabel,
              style: theme.textTheme.labelLarge?.copyWith(
                fontWeight: FontWeight.w600,
                color: colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ),
          ListView.separated(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            padding: const EdgeInsets.symmetric(horizontal: 12),
            itemCount: items.length,
            separatorBuilder: (_, __) => const SizedBox(height: 6),
            itemBuilder: (context, index) {
              final notification = items[index];
              return _NotificationTile(notification: notification, notifier: notifier);
            },
          ),
        ],
      ),
    );
  }
}

class _NotificationTile extends StatelessWidget {
  final NotificationItem notification;
  final NotificationNotifier notifier;

  const _NotificationTile({
    required this.notification,
    required this.notifier,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Dismissible(
      key: Key(notification.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.only(right: 20),
        decoration: BoxDecoration(color: colorScheme.errorContainer, borderRadius: BorderRadius.circular(10)),
        child: Icon(Icons.delete_outlined, color: colorScheme.error),
      ),
      confirmDismiss: (direction) async {
        return await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Dismiss notification?'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
              TextButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Dismiss')),
            ],
          ),
        );
      },
      onDismissed: (_) => notifier.removeNotification(notification.id),
      child: Card(
        color: !notification.isRead ? colorScheme.primaryContainer.withValues(alpha: 0.1) : null,
        child: InkWell(
          borderRadius: BorderRadius.circular(10),
          onTap: () => notifier.markAsRead(notification.id),
          child: Padding(
            padding: const EdgeInsets.all(14),
            child: Row(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(
                  width: 36,
                  height: 36,
                  decoration: BoxDecoration(
                    color: notification.type.accentColor.withValues(alpha: 0.12),
                    borderRadius: BorderRadius.circular(8),
                  ),
                  child: Icon(notification.type.icon, size: 18, color: notification.type.accentColor),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      Row(
                        children: [
                          Expanded(
                            child: Text(
                              notification.title,
                              style: theme.textTheme.bodyMedium?.copyWith(
                                fontWeight: notification.isRead ? FontWeight.w400 : FontWeight.w600,
                              ),
                              maxLines: 1,
                              overflow: TextOverflow.ellipsis,
                            ),
                          ),
                          if (!notification.isRead)
                            Container(
                              width: 7,
                              height: 7,
                              margin: const EdgeInsets.only(left: 8),
                              decoration: BoxDecoration(color: colorScheme.primary, shape: BoxShape.circle),
                            ),
                        ],
                      ),
                      const SizedBox(height: 2),
                      Text(notification.body, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)), maxLines: 2, overflow: TextOverflow.ellipsis),
                      const SizedBox(height: 4),
                      Text(
                        DateFormat('hh:mm a').format(notification.timestamp),
                        style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.4)),
                      ),
                    ],
                  ),
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}
