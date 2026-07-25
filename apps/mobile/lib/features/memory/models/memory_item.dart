import 'package:flutter/foundation.dart';

@immutable
class MemoryItem {
  final String id;
  final String userId;
  final String content;
  final String? source;
  final String category;
  final int? importance;
  final DateTime createdAt;
  final DateTime updatedAt;

  const MemoryItem({
    required this.id,
    required this.userId,
    required this.content,
    this.source,
    this.category = 'general',
    this.importance,
    required this.createdAt,
    required this.updatedAt,
  });

  MemoryItem copyWith({
    String? id,
    String? userId,
    String? content,
    String? source,
    String? category,
    int? importance,
    DateTime? createdAt,
    DateTime? updatedAt,
    bool clearSource = false,
  }) {
    return MemoryItem(
      id: id ?? this.id,
      userId: userId ?? this.userId,
      content: content ?? this.content,
      source: clearSource ? null : (source ?? this.source),
      category: category ?? this.category,
      importance: importance ?? this.importance,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }

  factory MemoryItem.fromJson(Map<String, dynamic> json) {
    return MemoryItem(
      id: json['id'] as String,
      userId: (json['user_id'] as String?) ?? '',
      content: (json['content'] as String?) ?? '',
      source: json['source'] as String?,
      category: (json['category'] as String?)?.toLowerCase() ?? 'general',
      importance: json['importance'] as int?,
      createdAt: DateTime.parse(
        json['created_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
      updatedAt: DateTime.parse(
        json['updated_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
    );
  }
}
