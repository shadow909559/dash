import 'package:flutter/foundation.dart';

enum MessageStatus {
  pending,
  sending,
  sent,
  streaming,
  complete,
  error,
}

enum MessageRole {
  user,
  assistant,
}

@immutable
class ChatMessage {
  final String id;
  final MessageRole role;
  final String content;
  final DateTime timestamp;
  final MessageStatus status;

  const ChatMessage({
    required this.id,
    required this.role,
    required this.content,
    required this.timestamp,
    this.status = MessageStatus.sent,
  });

  ChatMessage copyWith({
    String? id,
    MessageRole? role,
    String? content,
    DateTime? timestamp,
    MessageStatus? status,
  }) {
    return ChatMessage(
      id: id ?? this.id,
      role: role ?? this.role,
      content: content ?? this.content,
      timestamp: timestamp ?? this.timestamp,
      status: status ?? this.status,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'role': role.name,
      'content': content,
      'timestamp': timestamp.toIso8601String(),
      'status': status.name,
    };
  }

  factory ChatMessage.fromJson(Map<String, dynamic> json) {
    // Supports both REST API format and locally cached format.
    final roleStr = json['role'] as String? ?? 'user';
    final statusStr = json['status'] as String? ?? 'complete';

    final timestampStr = json['timestamp'] as String? ??
        json['created_at'] as String? ??
        DateTime.now().toIso8601String();

    return ChatMessage(
      id: (json['id'] ?? '').toString(),
      role: MessageRole.values.firstWhere(
        (r) => r.name == roleStr,
        orElse: () => MessageRole.user,
      ),
      content: (json['content'] ?? '').toString(),
      timestamp: DateTime.parse(timestampStr),
      status: MessageStatus.values.firstWhere(
        (s) => s.name == statusStr,
        orElse: () => MessageStatus.complete,
      ),
    );
  }

  bool get isUser => role == MessageRole.user;

  bool get isAssistant => role == MessageRole.assistant;

  bool get isStreaming => status == MessageStatus.streaming;

  bool get hasError => status == MessageStatus.error;

  /// Approximate token count (~4 characters/token)
  int get tokenCount => content.length ~/ 4;

  @override
  String toString() {
    return 'ChatMessage(id: $id, role: $role, status: $status)';
  }

  @override
  bool operator ==(Object other) {
    return identical(this, other) ||
        other is ChatMessage &&
            runtimeType == other.runtimeType &&
            id == other.id &&
            role == other.role &&
            content == other.content &&
            timestamp == other.timestamp &&
            status == other.status;
  }

  @override
  int get hashCode =>
      Object.hash(id, role, content, timestamp, status);
}