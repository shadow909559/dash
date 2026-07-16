import 'package:flutter/foundation.dart';

@immutable
class Conversation {
  final String id;
  final String? title;
  final bool isPinned;
  final bool isFavorited;
  final bool isArchived;
  final int messageCount;
  final String? lastMessageAt;
  final String? model;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Conversation({
    required this.id,
    this.title,
    this.isPinned = false,
    this.isFavorited = false,
    this.isArchived = false,
    this.messageCount = 0,
    this.lastMessageAt,
    this.model,
    required this.createdAt,
    required this.updatedAt,
  });

  Conversation copyWith({
    String? id,
    String? title,
    bool? isPinned,
    bool? isFavorited,
    bool? isArchived,
    int? messageCount,
    String? lastMessageAt,
    String? model,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Conversation(
      id: id ?? this.id,
      title: title ?? this.title,
      isPinned: isPinned ?? this.isPinned,
      isFavorited: isFavorited ?? this.isFavorited,
      isArchived: isArchived ?? this.isArchived,
      messageCount: messageCount ?? this.messageCount,
      lastMessageAt: lastMessageAt ?? this.lastMessageAt,
      model: model ?? this.model,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'title': title,
        'is_pinned': isPinned,
        'is_favorited': isFavorited,
        'is_archived': isArchived,
        'message_count': messageCount,
        'last_message_at': lastMessageAt,
        'model': model,
        'created_at': createdAt.toIso8601String(),
        'updated_at': updatedAt.toIso8601String(),
      };

  factory Conversation.fromJson(Map<String, dynamic> json) => Conversation(
        id: json['id'] as String,
        title: json['title'] as String?,
        isPinned: json['is_pinned'] as bool? ?? false,
        isFavorited: json['is_favorited'] as bool? ?? false,
        isArchived: json['is_archived'] as bool? ?? false,
        messageCount: json['message_count'] as int? ?? 0,
        lastMessageAt: json['last_message_at'] as String?,
        model: json['model'] as String?,
        createdAt: DateTime.parse(json['created_at'] as String),
        updatedAt: DateTime.parse(json['updated_at'] as String),
      );

  String get displayTitle => title ?? 'New Chat';
  String get timeAgo {
    final diff = DateTime.now().difference(createdAt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${createdAt.month}/${createdAt.day}';
  }
}