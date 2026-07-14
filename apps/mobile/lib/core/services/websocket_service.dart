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

class WebSocketService extends StateNotifier<WebSocketState> {
  WebSocketService(this._ref)
      : super(const WebSocketState(status: WebSocketStatus.disconnected));

  final Ref _ref;

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  final StreamController<String> _messageController =
      StreamController<String>.broadcast();

  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 5;
  Timer? _reconnectTimer;

  /// Stream of raw message strings received from the WebSocket.
  Stream<String> get messageStream => _messageController.stream;

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

    try {
      final channel = WebSocketChannel.connect(Uri.parse(url));
      _channel = channel;
      state = state.copyWith(status: WebSocketStatus.connected);

      _subscription = channel.stream.listen(
        (message) {
          
          print("WS RAW: $message");
          
          final msg = message?.toString() ?? '';
          _messageController.add(msg);

          state = state.copyWith(
            status: WebSocketStatus.connected,
            lastMessage: msg,
            clearError: true,
          );
          _reconnectAttempts = 0;
        },
        onError: (Object error) {
          state = state.copyWith(
            status: WebSocketStatus.error,
            errorMessage: error.toString(),
          );
          _scheduleReconnect();
        },
        onDone: () {
          state = state.copyWith(status: WebSocketStatus.disconnected);
          _scheduleReconnect();
        },
      );

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
  // ignore: avoid_print
  print('[WebSocketService] No JWT found; skipping auth.');
}
    } catch (error) {
      state = state.copyWith(
        status: WebSocketStatus.error,
        errorMessage: error.toString(),
      );
      _scheduleReconnect();
    }
  }


  void send(String payload) {
    if (!state.canSend) return;
    _channel?.sink.add(payload);
  }

  Future<void> disconnect() async {
    _cancelReconnect();
    _reconnectAttempts = 0;

    await _subscription?.cancel();
    await _channel?.sink.close();

    _subscription = null;
    _channel = null;
    state = const WebSocketState(status: WebSocketStatus.disconnected);
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;

    _cancelReconnect();

    _reconnectAttempts++;
    final delay = Duration(seconds: _reconnectAttempts * 2);

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
    _subscription?.cancel();
    _channel?.sink.close();
    _messageController.close();
    super.dispose();
  }
}

