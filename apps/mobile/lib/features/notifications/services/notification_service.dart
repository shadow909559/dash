import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/notification_item.dart';

class NotificationService {
  NotificationService();

  static const _kNotificationsKey = 'dash_notifications';
  static const _kUnreadKey = 'dash_unread_count';

  Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

  Future<List<NotificationItem>> getNotifications() async {
    final prefs = await _prefs();
    final raw = prefs.getStringList(_kNotificationsKey) ?? [];
    return raw.map((j) {
      final map = jsonDecode(j) as Map<String, dynamic>;
      return _fromMap(map);
    }).toList();
  }

  Future<int> getUnreadCount() async {
    final prefs = await _prefs();
    final stored = prefs.getInt(_kUnreadKey);
    if (stored != null) return stored;
    final notifications = await getNotifications();
    return notifications.where((n) => !n.isRead).length;
  }

  Future<void> addNotification(NotificationItem notification) async {
    final prefs = await _prefs();
    final existing = await getNotifications();
    existing.insert(0, notification);
    await _saveList(prefs, existing);
    if (!notification.isRead) {
      await prefs.setInt(_kUnreadKey, await getUnreadCount() + 1);
    }
  }

  Future<void> markAsRead(String id) async {
    final prefs = await _prefs();
    final existing = await getNotifications();
    final updated = existing.map((n) {
      return n.id == id ? n.copyWith(isRead: true) : n;
    }).toList();
    await _saveList(prefs, updated);
    await prefs.setInt(_kUnreadKey, updated.where((n) => !n.isRead).length);
  }

  Future<void> markAllAsRead() async {
    final prefs = await _prefs();
    final existing = await getNotifications();
    final updated = existing.map((n) => n.copyWith(isRead: true)).toList();
    await _saveList(prefs, updated);
    await prefs.setInt(_kUnreadKey, 0);
  }

  Future<void> removeNotification(String id) async {
    final prefs = await _prefs();
    final existing = await getNotifications();
    final updated = existing.where((n) => n.id != id).toList();
    await _saveList(prefs, updated);
    await prefs.setInt(_kUnreadKey, updated.where((n) => !n.isRead).length);
  }

  Future<void> clearAll() async {
    final prefs = await _prefs();
    await prefs.setStringList(_kNotificationsKey, []);
    await prefs.setInt(_kUnreadKey, 0);
  }

  Future<void> _saveList(SharedPreferences prefs, List<NotificationItem> list) async {
    final serialized = list.map((n) => jsonEncode(_toMap(n))).toList();
    await prefs.setStringList(_kNotificationsKey, serialized);
  }

  Map<String, dynamic> _toMap(NotificationItem n) {
    return {
      'id': n.id,
      'title': n.title,
      'body': n.body,
      'type': n.type.name,
      'timestamp': n.timestamp.toIso8601String(),
      'isRead': n.isRead,
      if (n.payload != null) 'payload': jsonEncode(n.payload),
    };
  }

  NotificationItem _fromMap(Map<String, dynamic> map) {
    NotificationType parseType(String value) {
      return NotificationType.values.firstWhere(
        (t) => t.name == value,
        orElse: () => NotificationType.system,
      );
    }

    return NotificationItem(
      id: map['id'] as String,
      title: map['title'] as String,
      body: map['body'] as String,
      type: parseType(map['type'] as String? ?? 'system'),
      timestamp: DateTime.tryParse(map['timestamp'] as String? ?? '') ?? DateTime.now(),
      isRead: map['isRead'] as bool? ?? false,
      payload: map['payload'] != null
          ? jsonDecode(map['payload'] as String) as Map<String, dynamic>?
          : null,
    );
  }
}

final notificationServiceProvider = Provider<NotificationService>((ref) {
  return NotificationService();
});
