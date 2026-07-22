import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/websocket_service.dart';
import 'sync_state.dart';
import 'offline_queue.dart';

/// Maximum number of retry attempts for failed sync operations.
const int _maxRetries = 10;

/// Heartbeat interval (in seconds).
const int _heartbeatInterval = 15;

/// Background sync interval (in seconds).
const int _backgroundSyncInterval = 60;

/// Provider for the sync service.
final syncServiceProvider =
    StateNotifierProvider<SyncServiceNotifier, SyncState>(
  (ref) => SyncServiceNotifier(ref),
);

/// Provider for the offline message queue.
final offlineQueueProvider = Provider<OfflineMessageQueue>((ref) {
  return OfflineMessageQueue();
});

class SyncServiceNotifier extends StateNotifier<SyncState> {
  SyncServiceNotifier(this._ref) : super(const SyncState()) {
    _ws = _ref.read(webSocketServiceProvider.notifier);
    _queue = OfflineMessageQueue();

    // Listen to WebSocket status changes
    _statusSub = _ws.statusStream.listen(_onWebSocketStatusChanged);

    // Listen for session info from the server
    _rawSub = _ws.rawMessageStream.listen(_onRawMessage);

    // Start heartbeat timer
    _heartbeatTimer = Timer.periodic(
      const Duration(seconds: _heartbeatInterval),
      (_) => _sendHeartbeat(),
    );

    // Start background sync timer
    _backgroundSyncTimer = Timer.periodic(
      const Duration(seconds: _backgroundSyncInterval),
      (_) => _performBackgroundSync(),
    );

    // Load offline queue
    _queue.load();

    // Flush offline queue when we connect
    _flushOfflineQueue();
  }

  final Ref _ref;
  late final WebSocketService _ws;
  late final OfflineMessageQueue _queue;
  StreamSubscription<WebSocketStatus>? _statusSub;
  StreamSubscription<String>? _rawSub;
  Timer? _heartbeatTimer;
  Timer? _backgroundSyncTimer;
  Timer? _retryTimer;
  bool _isFlushing = false;

  /// Register a sync session with the server.
  Future<void> registerSession({String? clientId}) async {
    if (!_ws.state.canSend) return;

    state = state.copyWith(
      status: SyncStatus.connecting,
      serviceStatus: SyncServiceStatus.syncing,
    );

    final payload = {
      'type': 'sync.register',
      if (clientId != null) 'client_id': clientId,
      'client_type': 'mobile',
    };

    _ws.send(jsonEncode(payload));
  }

  /// Send a heartbeat to the server.
  Future<void> _sendHeartbeat() async {
    if (!_ws.state.canSend) return;

    final payload = {
      'type': 'sync.heartbeat',
    };

    _ws.send(jsonEncode(payload));
  }

  /// Mark messages as seen by the server (for dedup).
  Future<void> markMessagesSeen(List<String> messageIds) async {
    if (!_ws.state.canSend || messageIds.isEmpty) return;

    final payload = {
      'type': 'sync.mark_seen',
      'message_ids': messageIds,
    };

    _ws.send(jsonEncode(payload));
  }

  /// Request a full sync from the server.
  Future<void> requestSync({
    List<Map<String, dynamic>> conversations = const [],
    List<Map<String, dynamic>> memories = const [],
    List<String> messageIdsSeen = const [],
  }) async {
    if (!_ws.state.canSend) return;

    state = state.copyWith(
      status: SyncStatus.syncing,
      serviceStatus: SyncServiceStatus.syncing,
    );

    final payload = {
      'type': 'sync.request',
      'client_id': state.session?.clientId ?? 'mobile',
      'client_type': 'mobile',
      'last_sync_timestamp': state.lastSyncTimestamp,
      'conversations': conversations,
      'memories': memories,
      'message_ids_seen': messageIdsSeen,
    };

    _ws.send(jsonEncode(payload));
  }

  /// Handle WebSocket status changes.
  void _onWebSocketStatusChanged(WebSocketStatus status) {
    switch (status) {
      case WebSocketStatus.connected:
        state = state.copyWith(
          status: SyncStatus.connected,
          retryCount: 0,
          clearError: true,
        );

        // Register sync session
        registerSession();

        // Flush offline queue
        _flushOfflineQueue();
        break;

      case WebSocketStatus.connecting:
        state = state.copyWith(
          status: SyncStatus.connecting,
          serviceStatus: SyncServiceStatus.syncing,
        );
        break;

      case WebSocketStatus.disconnected:
        state = state.copyWith(
          status: SyncStatus.disconnected,
          serviceStatus: SyncServiceStatus.offline,
        );
        break;

      case WebSocketStatus.reconnecting:
        state = state.copyWith(
          status: SyncStatus.connecting,
          serviceStatus: SyncServiceStatus.syncing,
        );
        break;

      case WebSocketStatus.error:
        state = state.copyWith(
          status: SyncStatus.error,
          serviceStatus: SyncServiceStatus.error,
          errorMessage: _ws.state.errorMessage,
        );
        break;
    }
  }

  /// Handle raw messages from the WebSocket.
  void _onRawMessage(String raw) {
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final type = json['type'] as String? ?? '';

      switch (type) {
        case 'session.info':
          _handleSessionInfo(json);
          break;

        case 'sync.registered':
          _handleSyncRegistered(json);
          break;

        case 'sync.response':
          _handleSyncResponse(json);
          break;

        case 'sync.heartbeat_ack':
          // Heartbeat acknowledged - connection is healthy
          break;

        case 'pong':
          // Server responded to our ping
          break;
      }
    } catch (_) {
      // Ignore malformed messages
    }
  }

  /// Handle session info from the server.
  void _handleSessionInfo(Map<String, dynamic> json) {
    final session = SyncSession(
      sessionId: json['session_id'] as String? ?? '',
      clientId: json['client_id'] as String? ?? '',
      recoveryCount: json['recovery_count'] as int? ?? 0,
      requiresFullSync: json['requires_full_sync'] as bool? ?? false,
    );

    state = state.copyWith(
      session: session,
      status: SyncStatus.connected,
      serviceStatus: SyncServiceStatus.idle,
    );

    // If recovery count is high, request full sync
    if (session.requiresFullSync) {
      requestSync();
    }
  }

  /// Handle sync registration response.
  void _handleSyncRegistered(Map<String, dynamic> json) {
    final session = SyncSession(
      sessionId: json['session_id'] as String? ?? '',
      clientId: json['client_id'] as String? ?? '',
      recoveryCount: json['recovery_count'] as int? ?? 0,
      requiresFullSync: json['requires_full_sync'] as bool? ?? false,
    );

    state = state.copyWith(
      session: session,
      status: SyncStatus.connected,
      serviceStatus: SyncServiceStatus.idle,
    );

    // Deliver any queued messages from the server
    final queuedMessages = json['queued_messages'] as List? ?? [];
    if (queuedMessages.isNotEmpty) {
      for (final msg in queuedMessages) {
        if (msg is Map<String, dynamic>) {
          _ws.chatMessageController.add(msg);
        }
      }
    }

    // If recovery count is high, request full sync
    if (session.requiresFullSync) {
      requestSync();
    }
  }

  /// Handle sync response from the server.
  void _handleSyncResponse(Map<String, dynamic> json) {
    final conversations = json['conversations'] as List? ?? [];
    final memories = json['memories'] as List? ?? [];
    final conflicts = json['conflicts'] as List? ?? [];
    final serverTimestamp = json['server_timestamp'] as String? ?? '';
    final requiresFullSync = json['requires_full_sync'] as bool? ?? false;

    state = state.copyWith(
      status: SyncStatus.connected,
      serviceStatus: SyncServiceStatus.idle,
      lastSyncTimestamp: serverTimestamp,
      totalSyncedConversations: state.totalSyncedConversations + conversations.length,
      totalSyncedMemories: state.totalSyncedMemories + memories.length,
      totalConflicts: state.totalConflicts + conflicts.length,
    );

    // If there are conflicts, log them
    if (conflicts.isNotEmpty) {
      // Conflicts are resolved server-side with last-write-wins
    }

    // If full sync is required, request it
    if (requiresFullSync) {
      requestSync();
    }
  }

  /// Flush the offline message queue.
  Future<void> _flushOfflineQueue() async {
    if (_isFlushing) return;
    _isFlushing = true;

    try {
      await _queue.load();

      while (_queue.isNotEmpty && _ws.state.canSend) {
        final message = _queue.dequeue();
        if (message == null) break;

        // Check retry count
        if (message.retryCount >= _maxRetries) {
          // Drop message after max retries
          continue;
        }

        // Send the message
        _ws.send(jsonEncode(message.payload));

        // Mark as sent
        await _queue.removeSent([message.id]);
      }

      state = state.copyWith(pendingMessages: _queue.length);
    } finally {
      _isFlushing = false;
    }
  }

  /// Queue a message for sending (goes to offline queue if disconnected).
  Future<void> queueMessage({
    required String id,
    required String type,
    required Map<String, dynamic> payload,
    String? conversationId,
  }) async {
    if (_ws.state.canSend) {
      // Send immediately
      _ws.send(jsonEncode(payload));
    } else {
      // Queue for later
      await _queue.enqueue(QueuedMessage(
        id: id,
        type: type,
        payload: payload,
        timestamp: DateTime.now(),
        conversationId: conversationId,
      ));
      state = state.copyWith(pendingMessages: _queue.length);
    }
  }

  /// Perform background sync.
  Future<void> _performBackgroundSync() async {
    if (!_ws.state.canSend) return;

    // Only sync if we have a session
    if (state.session == null) return;

    // Request incremental sync
    await requestSync();
  }


  /// Force a full sync now.
  Future<void> forceSync() async {
    await requestSync();
  }

  /// Clear the sync state.
  void clearSyncState() {
    state = const SyncState();
  }

  @override
  void dispose() {
    _statusSub?.cancel();
    _rawSub?.cancel();
    _heartbeatTimer?.cancel();
    _backgroundSyncTimer?.cancel();
    _retryTimer?.cancel();
    super.dispose();
  }
}