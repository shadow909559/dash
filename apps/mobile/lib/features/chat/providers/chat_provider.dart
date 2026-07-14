import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/websocket_service.dart';
import '../models/chat_message.dart';

/// State holder for the chat feature.
class ChatState {
  final List<ChatMessage> messages;
  final bool isTyping;
  final WebSocketStatus connectionStatus;
  final String? errorMessage;

  const ChatState({
    required this.messages,
    this.isTyping = false,
    this.connectionStatus = WebSocketStatus.disconnected,
    this.errorMessage,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isTyping,
    WebSocketStatus? connectionStatus,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isTyping: isTyping ?? this.isTyping,
      connectionStatus: connectionStatus ?? this.connectionStatus,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
    );
  }
}

final chatProvider = StateNotifierProvider<ChatService, ChatState>((ref) {
  final wsService = ref.watch(webSocketServiceProvider.notifier);
  return ChatService(ref, wsService);
});

class ChatService extends StateNotifier<ChatState> {
  ChatService(this._ref, this._wsService)
      : super(const ChatState(messages: [])) {
    _init();
  }

  final Ref _ref;
  final WebSocketService _wsService;
  StreamSubscription<String>? _wsSubscription;
  int _messageCounter = 0;

  void _init() {
    // Listen to WebSocket state changes
    _ref.listen<WebSocketState>(webSocketServiceProvider, (_, next) {
      state = state.copyWith(
        connectionStatus: next.status,
        errorMessage: next.errorMessage,
        clearError: true,
      );
    });

    // Listen to incoming messages
    _wsSubscription = _wsService.messageStream.listen(_handleIncomingMessage);

    // Auto-connect if not already connected
    if (state.connectionStatus == WebSocketStatus.disconnected) {
      _wsService.connect();
    }
  }

  void _handleIncomingMessage(String raw) {
    try {
      final json = jsonDecode(raw) as Map<String, dynamic>;
      final type = json['type'] as String?;

      switch (type) {
        case 'echo':
          _handleEcho(json);
          break;
        case 'token':
          _handleToken(json);
          break;
        case 'done':
          _handleDone(json);
          break;
        default:
          // Treat unknown messages as assistant responses
          _addAssistantMessage(json['received']?.toString() ?? raw);
      }
    } catch (_) {
      // If not valid JSON, treat as plain text assistant response
      _addAssistantMessage(raw);
    }
  }

  void _handleEcho(Map<String, dynamic> json) {
    final received = json['received'];
    if (received is Map<String, dynamic>) {
      final content = received['content'] as String? ?? received.toString();
      // Mark the last user message as sent, add echo as assistant
      _markLastUserMessageSent();
      _addAssistantMessage(content);
    } else {
      _addAssistantMessage(received?.toString() ?? '');
    }
  }

  void _handleToken(Map<String, dynamic> json) {
    final content = json['content'] as String? ?? '';
    state = state.copyWith(isTyping: false);

    final messages = [...state.messages];
    if (messages.isNotEmpty && messages.last.isStreaming) {
      // Append to the existing streaming message
      messages[messages.length - 1] = messages.last.copyWith(
        content: messages.last.content + content,
      );
    } else {
      // Start a new streaming message
      messages.add(ChatMessage(
        id: _nextId(),
        role: MessageRole.assistant,
        content: content,
        timestamp: DateTime.now(),
        status: MessageStatus.streaming,
      ));
    }
    state = state.copyWith(messages: messages);
  }

  void _handleDone(Map<String, dynamic> json) {
    final messages = [...state.messages];
    if (messages.isNotEmpty && messages.last.isStreaming) {
      messages[messages.length - 1] = messages.last.copyWith(
        status: MessageStatus.complete,
      );
    }
    state = state.copyWith(messages: messages, isTyping: false);
  }

  void _addAssistantMessage(String content) {
    final message = ChatMessage(
      id: _nextId(),
      role: MessageRole.assistant,
      content: content,
      timestamp: DateTime.now(),
      status: MessageStatus.complete,
    );
    state = state.copyWith(
      messages: [...state.messages, message],
      isTyping: false,
    );
  }

  void _markLastUserMessageSent() {
    final messages = [...state.messages];
    for (int i = messages.length - 1; i >= 0; i--) {
      if (messages[i].isUser && messages[i].status == MessageStatus.sending) {
        messages[i] = messages[i].copyWith(status: MessageStatus.sent);
        break;
      }
    }
    state = state.copyWith(messages: messages);
  }

  /// Send a user message over WebSocket.
  void sendMessage(String content) {
    if (content.trim().isEmpty) return;
    if (!_wsService.state.canSend) return;

    final userMessage = ChatMessage(
      id: _nextId(),
      role: MessageRole.user,
      content: content,
      timestamp: DateTime.now(),
      status: MessageStatus.sending,
    );

    state = state.copyWith(
      messages: [...state.messages, userMessage],
      isTyping: true,
    );

    // Send as JSON
    final payload = jsonEncode({
      'type': 'message',
      'content': content,
    });
    _wsService.send(payload);
  }

  /// Clear all messages from the conversation.
  void clearMessages() {
    state = state.copyWith(messages: []);
  }

  /// Manually reconnect the WebSocket.
  Future<void> reconnect() async {
    await _wsService.disconnect();
    await _wsService.connect();
  }

  String _nextId() {
    _messageCounter++;
    return 'msg_${DateTime.now().millisecondsSinceEpoch}_$_messageCounter';
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}