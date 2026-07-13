import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

import '../constants.dart';

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
  (ref) => WebSocketService(),
);

class WebSocketService extends StateNotifier<WebSocketState> {
  WebSocketService()
      : super(const WebSocketState(status: WebSocketStatus.disconnected));

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;

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
      _subscription = channel.stream.listen(
        (message) {
          state = state.copyWith(
            status: WebSocketStatus.connected,
            lastMessage: message?.toString(),
            clearError: true,
          );
        },
        onError: (Object error) {
          state = state.copyWith(
            status: WebSocketStatus.error,
            errorMessage: error.toString(),
          );
        },
        onDone: () {
          state = state.copyWith(status: WebSocketStatus.disconnected);
        },
      );

      state = state.copyWith(status: WebSocketStatus.connected);
    } catch (error) {
      state = state.copyWith(
        status: WebSocketStatus.error,
        errorMessage: error.toString(),
      );
    }
  }

  void send(String payload) {
    if (!state.canSend) {
      return;
    }

    _channel?.sink.add(payload);
  }

  Future<void> disconnect() async {
    await _subscription?.cancel();
    await _channel?.sink.close();
    _subscription = null;
    _channel = null;
    state = const WebSocketState(status: WebSocketStatus.disconnected);
  }

  @override
  void dispose() {
    unawaited(_subscription?.cancel());
    unawaited(_channel?.sink.close());
    super.dispose();
  }
}
