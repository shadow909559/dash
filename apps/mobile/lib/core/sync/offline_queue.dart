import 'dart:collection';
import 'dart:convert';

import 'package:shared_preferences/shared_preferences.dart';

/// An offline message to be sent when connectivity is restored.
class QueuedMessage {
  final String id;
  final String type;
  final Map<String, dynamic> payload;
  final DateTime timestamp;
  final int retryCount;
  final String? conversationId;

  const QueuedMessage({
    required this.id,
    required this.type,
    required this.payload,
    required this.timestamp,
    this.retryCount = 0,
    this.conversationId,
  });

  QueuedMessage copyWith({int? retryCount}) {
    return QueuedMessage(
      id: id,
      type: type,
      payload: payload,
      timestamp: timestamp,
      retryCount: retryCount ?? this.retryCount,
      conversationId: conversationId,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'type': type,
        'payload': payload,
        'timestamp': timestamp.toIso8601String(),
        'retry_count': retryCount,
        'conversation_id': conversationId,
      };

  factory QueuedMessage.fromJson(Map<String, dynamic> json) {
    return QueuedMessage(
      id: json['id'] as String? ?? '',
      type: json['type'] as String? ?? '',
      payload: json['payload'] as Map<String, dynamic>? ?? {},
      timestamp: DateTime.tryParse(json['timestamp'] as String? ?? '') ??
          DateTime.now(),
      retryCount: json['retry_count'] as int? ?? 0,
      conversationId: json['conversation_id'] as String?,
    );
  }
}

/// Persistent offline message queue backed by SharedPreferences.
///
/// Messages are stored locally when the WebSocket is disconnected
/// and flushed when the connection is restored.
class OfflineMessageQueue {
  static const String _storageKey = 'offline_message_queue';

  final Queue<QueuedMessage> _queue = Queue<QueuedMessage>();
  bool _loaded = false;

  /// Load the queue from persistent storage.
  Future<void> load() async {
    if (_loaded) return;
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = prefs.getStringList(_storageKey) ?? [];
      for (final item in raw) {
        try {
          final decoded = jsonDecode(item) as Map<String, dynamic>;
          _queue.add(QueuedMessage.fromJson(decoded));
        } catch (_) {
          // Skip malformed entries
        }
      }
      _loaded = true;
    } catch (_) {
      _loaded = true;
    }
  }

  /// Save the queue to persistent storage.
  Future<void> _save() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final raw = _queue.map((m) => jsonEncode(m.toJson())).toList();
      await prefs.setStringList(_storageKey, raw);
    } catch (_) {
      // Storage write failures are non-fatal
    }
  }

  /// Enqueue a message for later delivery.
  Future<void> enqueue(QueuedMessage message) async {
    await load();
    _queue.add(message);
    await _save();
  }

  /// Dequeue the next message.
  QueuedMessage? dequeue() {
    if (_queue.isEmpty) return null;
    final message = _queue.removeFirst();
    // Don't persist every dequeue - caller should call flush
    return message;
  }

  /// Peek at the next message without removing it.
  QueuedMessage? peek() {
    if (_queue.isEmpty) return null;
    return _queue.first;
  }

  /// Get all queued messages (does not remove them).
  List<QueuedMessage> getAll() {
    return _queue.toList();
  }

  /// Remove all messages from the queue.
  Future<void> clear() async {
    _queue.clear();
    await _save();
  }

  /// Get the number of queued messages.
  int get length => _queue.length;

  /// Whether the queue has any messages.
  bool get isEmpty => _queue.isEmpty;

  /// Whether the queue has messages.
  bool get isNotEmpty => _queue.isNotEmpty;

  /// Remove successfully sent messages from the queue.
  Future<void> removeSent(List<String> messageIds) async {
    final toRemove = <String>{...messageIds};
    _queue.removeWhere((m) => toRemove.contains(m.id));
    await _save();
  }

  /// Increment retry count for all messages and save.
  Future<void> incrementRetries() async {
    final updated = _queue.map((m) => m.copyWith(retryCount: m.retryCount + 1)).toList();
    _queue.clear();
    _queue.addAll(updated);
    await _save();
  }

  /// Save current queue state.
  Future<void> flush() async {
    await _save();
  }
}