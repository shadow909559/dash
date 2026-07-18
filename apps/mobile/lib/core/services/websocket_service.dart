import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../constants.dart';

import '../../features/auth/services/auth_service.dart';

enum WebSocketStatus {
  disconnected,
  connecting,
  connected,
  error,
}

class WebSocketState {
  const WebSocketState({
    required this.status,
    this.url = defaultWebSocketUrl,
    this.lastMessage,
    this.errorMessage,
  });

  final WebSocketStatus status;
  final String url;
  final String? lastMessage;
  final String? errorMessage;

  bool get canSend => status == WebSocketStatus.connected;

  WebSocketState copyWith({
    WebSocketStatus? status,
    String? url,
    String? lastMessage,
    String? errorMessage,
    bool clearError = false,
  }) {
    return WebSocketState(
      status: status ?? this.status,
      url: url ?? this.url,
      lastMessage: lastMessage ?? this.lastMessage,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

final webSocketServiceProvider =
    StateNotifierProvider<WebSocketService, WebSocketState>(
  (ref) => WebSocketService(ref),
);

/// Chat message types that should become visible messages.
const Set<String> _chatTypes = {
  'chat.token',
  'chat.message',
  'assistant',
  'user',
};

class WebSocketService extends StateNotifier<WebSocketState> {
  WebSocketService(this._ref)
      : super(const WebSocketState(status: WebSocketStatus.disconnected));

  final Ref _ref;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;

  /// Raw message stream — ALL messages from the server (for internal use).
  final StreamController<String> _rawMessageController =
      StreamController<String>.broadcast();

  /// Filtered stream — only chat-relevant messages (chat.token, chat.message, etc.)
  final StreamController<Map<String, dynamic>> _chatMessageController =
      StreamController<Map<String, dynamic>>.broadcast();

  /// Stream of connection status changes.
  final StreamController<WebSocketStatus> _statusController =
      StreamController<WebSocketStatus>.broadcast();

  /// Stream of typing indicators from the server.
  final StreamController<bool> _typingController =
      StreamController<bool>.broadcast();

  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 50;
  Timer? _reconnectTimer;
  Timer? _heartbeatTimer;

  /// Stream of raw message strings received from the WebSocket.
  Stream<String> get rawMessageStream => _rawMessageController.stream;

  /// Stream of parsed chat messages (only chat.token, chat.message, etc.)
  Stream<Map<String, dynamic>> get chatMessageStream =>
      _chatMessageController.stream;

  /// Stream of connection status changes.
  Stream<WebSocketStatus> get statusStream => _statusController.stream;

  /// Stream of typing indicators.
  Stream<bool> get typingStream => _typingController.stream;

  /// Whether auto-reconnect is currently active.
  bool get isReconnecting => _reconnectTimer != null;

  Future<void> connect({String url = defaultWebSocketUrl}) async {
    if (state.status == WebSocketStatus.connecting ||
        state.status == WebSocketStatus.connected) {
      return;
    }

    state = state.copyWith(
      status: WebSocketStatus.connecting,
      url: url,
      clearError: true,
    );
    _statusController.add(WebSocketStatus.connecting);

    try {
      final channel = WebSocketChannel.connect(Uri.parse(url));
      _channel = channel;
      state = state.copyWith(status: WebSocketStatus.connected);
      _statusController.add(WebSocketStatus.connected);

      _subscription = channel.stream.listen(
        (message) {
          final msg = message?.toString() ?? '';
          _rawMessageController.add(msg);

          state = state.copyWith(
            status: WebSocketStatus.connected,
            lastMessage: msg,
            clearError: true,
          );
          _reconnectAttempts = 0;

          // Parse and route the message
          _routeMessage(msg);
        },
        onError: (Object error) {
          state = state.copyWith(
            status: WebSocketStatus.error,
            errorMessage: error.toString(),
          );
          _statusController.add(WebSocketStatus.error);
          _scheduleReconnect();
        },
        onDone: () {
          state = state.copyWith(status: WebSocketStatus.disconnected);
          _statusController.add(WebSocketStatus.disconnected);
          _scheduleReconnect();
        },
      );

      // Start heartbeat: send ping every 20 seconds
      _heartbeatTimer = Timer.periodic(const Duration(seconds: 20), (_) {
        if (_channel != null && state.status == WebSocketStatus.connected) {
          try {
            _channel!.sink.add(jsonEncode({'type': 'ping'}));
          } catch (_) {}
        }
      });

      // Backend protocol:
      // 1) hello
      // 2) auth (if we have JWT)
      _channel!.sink.add(jsonEncode({
        'type': 'hello',
      }));

      final auth = _ref.read(authServiceProvider);

      await auth.tryRestoreSession();

      final jwt = await auth.getValidAccessToken();

      if (jwt != null && jwt.isNotEmpty) {
        _channel!.sink.add(
          jsonEncode({
            'type': 'auth',
            'access_token': jwt,
          }),
        );
      } else {
        print('[WebSocketService] No JWT found; skipping auth.');
      }
    } catch (error) {
      state = state.copyWith(
        status: WebSocketStatus.error,
        errorMessage: error.toString(),
      );
      _statusController.add(WebSocketStatus.error);
      _scheduleReconnect();
    }
  }

  /// Route an incoming message based on its type.
  /// Protocol messages are handled internally.
  /// Chat messages are forwarded to the chat stream.
  void _routeMessage(String raw) {
    Map<String, dynamic> json;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) {
        return; // Ignore non-JSON messages
      }
      json = decoded;
    } catch (_) {
      return; // Ignore malformed JSON
    }

    final type = json['type']?.toString() ?? '';

    // Handle ping/pong automatically — never forward to chat
    if (type == 'ping') {
      _handlePing(json);
      return;
    }
    if (type == 'pong') {
      // Server responded to our ping — just ignore
      return;
    }

    // Handle typing indicators
    if (type == 'typing.start') {
      _typingController.add(true);
      return;
    }
    if (type == 'typing.stop') {
      _typingController.add(false);
      return;
    }

    // Handle connection status
    if (type == 'connected') {
      _statusController.add(WebSocketStatus.connected);
      return;
    }
    if (type == 'disconnected') {
      _statusController.add(WebSocketStatus.disconnected);
      return;
    }

    // Handle auth/hello — just acknowledge, never create bubbles
    if (type == 'hello' || type == 'auth') {
      return;
    }

    // Forward chat messages to the chat stream
    if (_chatTypes.contains(type)) {
      _chatMessageController.add(json);
      return;
    }

    // For chat.done and chat.error, also forward to chat stream
    // so the provider can finalize streaming
    if (type == 'chat.done' || type == 'chat.error') {
      _chatMessageController.add(json);
      return;
    }

    // Unknown type — log but don't create bubbles
    print('[WebSocketService] Unknown message type: $type');
  }

  /// Automatically reply to server pings.
  void _handlePing(Map<String, dynamic> json) {
    if (_channel != null && state.status == WebSocketStatus.connected) {
      try {
        _channel!.sink.add(jsonEncode({'type': 'pong'}));
      } catch (_) {}
    }
  }

  void send(String payload) {
    if (!state.canSend) return;
    _channel?.sink.add(payload);
  }

  Future<void> disconnect() async {
    _cancelReconnect();
    _heartbeatTimer?.cancel();
    _heartbeatTimer = null;
    _reconnectAttempts = 0;

    await _subscription?.cancel();
    await _channel?.sink.close();

    _subscription = null;
    _channel = null;
    state = const WebSocketState(status: WebSocketStatus.disconnected);
    _statusController.add(WebSocketStatus.disconnected);
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;

    _cancelReconnect();

    _reconnectAttempts++;
    final delay = Duration(
      seconds: (_reconnectAttempts * 2).clamp(1, 60),
    );

    _reconnectTimer = Timer(delay, () {
      _reconnectTimer = null;
      if (state.status != WebSocketStatus.connected) {
        connect(url: state.url);
      }
    });
  }

  void _cancelReconnect() {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
  }

  @override
  void dispose() {
    _cancelReconnect();
    _heartbeatTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    _rawMessageController.close();
    _chatMessageController.close();
    _statusController.close();
    _typingController.close();
    super.dispose();
  }
}