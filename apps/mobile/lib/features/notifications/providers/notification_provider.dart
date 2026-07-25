import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/notification_item.dart';
import '../services/notification_service.dart';

class NotificationState {
  final List<NotificationItem> notifications;
  final int unreadCount;
  final bool isLoading;

  const NotificationState({
    this.notifications = const [],
    this.unreadCount = 0,
    this.isLoading = false,
  });

  NotificationState copyWith({
    List<NotificationItem>? notifications,
    int? unreadCount,
    bool? isLoading,
    bool clearError = false,
  }) {
    return NotificationState(
      notifications: notifications ?? this.notifications,
      unreadCount: unreadCount ?? this.unreadCount,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  List<NotificationItem> get unread => notifications.where((n) => !n.isRead).toList();
}

class NotificationNotifier extends StateNotifier<NotificationState> {
  final NotificationService _service;
  Timer? _pollTimer;

  NotificationNotifier(this._service) : super(const NotificationState()) {
    loadNotifications();
    _startPolling();
  }

  Future<void> loadNotifications() async {
    state = state.copyWith(isLoading: true);
    try {
      final items = await _service.getNotifications();
      final count = await _service.getUnreadCount();
      state = state.copyWith(
        notifications: items,
        unreadCount: count,
        isLoading: false,
      );
    } catch (e, st) {
      debugPrint('Failed to load notifications: $e\n$st');
      state = state.copyWith(isLoading: false);
    }
  }

  Future<void> markAsRead(String id) async {
    try {
      await _service.markAsRead(id);
      final updated = state.notifications.map((n) {
        return n.id == id ? n.copyWith(isRead: true) : n;
      }).toList();
      state = state.copyWith(
        notifications: updated,
        unreadCount: updated.where((n) => !n.isRead).length,
      );
    } catch (e) {
      debugPrint('Failed to mark notification as read: $e');
    }
  }

  Future<void> markAllAsRead() async {
    try {
      await _service.markAllAsRead();
      final updated = state.notifications.map((n) => n.copyWith(isRead: true)).toList();
      state = state.copyWith(notifications: updated, unreadCount: 0);
    } catch (e) {
      debugPrint('Failed to mark all as read: $e');
    }
  }

  Future<void> removeNotification(String id) async {
    try {
      await _service.removeNotification(id);
      final updated = state.notifications.where((n) => n.id != id).toList();
      state = state.copyWith(
        notifications: updated,
        unreadCount: updated.where((n) => !n.isRead).length,
      );
    } catch (e) {
      debugPrint('Failed to remove notification: $e');
    }
  }

  @override
  void dispose() {
    _pollTimer?.cancel();
    super.dispose();
  }

  void _startPolling() {
    _pollTimer = Timer.periodic(const Duration(seconds: 30), (_) => loadNotifications());
  }
}

final notificationProvider =
    StateNotifierProvider<NotificationNotifier, NotificationState>((ref) {
  final service = ref.watch(notificationServiceProvider);
  return NotificationNotifier(service);
});
