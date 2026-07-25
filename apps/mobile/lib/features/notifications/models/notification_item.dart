library;

import 'package:flutter/material.dart';

enum NotificationType {
  planner('Planner Reminder', Icons.event_available, Colors.purple),
  automation('Automation Completed', Icons.auto_fix_high, Colors.teal),
  desktopAlert('Desktop Alert', Icons.desktop_windows, Colors.blue),
  memoryReminder('Memory Reminder', Icons.lightbulb_outline, Colors.amber),
  system('System', Icons.settings_suggest, Colors.grey);

  final String label;
  final IconData icon;
  final Color accentColor;
  const NotificationType(this.label, this.icon, this.accentColor);
}

class NotificationItem {
  final String id;
  final String title;
  final String body;
  final NotificationType type;
  final DateTime timestamp;
  final bool isRead;
  final Map<String, dynamic>? payload;

  const NotificationItem({
    required this.id,
    required this.title,
    required this.body,
    required this.type,
    required this.timestamp,
    this.isRead = false,
    this.payload,
  });

  NotificationItem copyWith({bool? isRead}) {
    return NotificationItem(
      id: id,
      title: title,
      body: body,
      type: type,
      timestamp: timestamp,
      isRead: isRead ?? this.isRead,
      payload: payload,
    );
  }
}
