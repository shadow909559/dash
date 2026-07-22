import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Represents a notification in the notification center.
class AppNotification {
  final String id;
  final String title;
  final String body;
  final String type; // 'info', 'success', 'warning', 'error'
  final DateTime createdAt;
  final bool isRead;

  const AppNotification({
    required this.id,
    required this.title,
    required this.body,
    this.type = 'info',
    required this.createdAt,
    this.isRead = false,
  });

  AppNotification copyWith({bool? isRead}) {
    return AppNotification(
      id: id,
      title: title,
      body: body,
      type: type,
      createdAt: createdAt,
      isRead: isRead ?? this.isRead,
    );
  }

  IconData get icon {
    switch (type) {
      case 'success':
        return Icons.check_circle;
      case 'warning':
        return Icons.warning;
      case 'error':
        return Icons.error;
      default:
        return Icons.info_outline;
    }
  }

  Color color(ColorScheme scheme) {
    switch (type) {
      case 'success':
        return Colors.green;
      case 'warning':
        return Colors.orange;
      case 'error':
        return scheme.error;
      default:
        return scheme.primary;
    }
  }
}

/// State for the notification center.
class NotificationState {
  final List<AppNotification> notifications;
  final int unreadCount;

  const NotificationState({
    this.notifications = const [],
    this.unreadCount = 0,
  });

  int get totalCount => notifications.length;
}

/// Notifier managing application notifications.
class NotificationNotifier extends StateNotifier<NotificationState> {
  NotificationNotifier() : super(const NotificationState());

  void addNotification(AppNotification notification) {
    state = NotificationState(
      notifications: [notification, ...state.notifications],
      unreadCount: state.unreadCount + 1,
    );
  }

  void markAsRead(String id) {
    final updated = state.notifications.map((n) {
      return n.id == id ? n.copyWith(isRead: true) : n;
    }).toList();
    state = NotificationState(
      notifications: updated,
      unreadCount: updated.where((n) => !n.isRead).length,
    );
  }

  void markAllAsRead() {
    final updated = state.notifications
        .map((n) => n.copyWith(isRead: true))
        .toList();
    state = NotificationState(
      notifications: updated,
      unreadCount: 0,
    );
  }

  void removeNotification(String id) {
    final updated =
        state.notifications.where((n) => n.id != id).toList();
    state = NotificationState(
      notifications: updated,
      unreadCount: updated.where((n) => !n.isRead).length,
    );
  }

  void clearAll() {
    state = const NotificationState();
  }

  /// Add an info notification.
  void info(String title, String body) {
    addNotification(AppNotification(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: title,
      body: body,
      type: 'info',
      createdAt: DateTime.now(),
    ));
  }

  /// Add a success notification.
  void success(String title, String body) {
    addNotification(AppNotification(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: title,
      body: body,
      type: 'success',
      createdAt: DateTime.now(),
    ));
  }

  /// Add a warning notification.
  void warning(String title, String body) {
    addNotification(AppNotification(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: title,
      body: body,
      type: 'warning',
      createdAt: DateTime.now(),
    ));
  }

  /// Add an error notification.
  void error(String title, String body) {
    addNotification(AppNotification(
      id: DateTime.now().millisecondsSinceEpoch.toString(),
      title: title,
      body: body,
      type: 'error',
      createdAt: DateTime.now(),
    ));
  }
}

/// Riverpod provider for the notification center.
final notificationProvider =
    StateNotifierProvider<NotificationNotifier, NotificationState>(
  (ref) => NotificationNotifier(),
);

