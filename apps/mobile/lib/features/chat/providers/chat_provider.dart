import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/websocket_service.dart';
import '../models/chat_message.dart';

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
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

final chatProvider =
    StateNotifierProvider<ChatService, ChatState>((ref) => ChatService(ref));

class ChatService extends StateNotifier<ChatState> {
  ChatService(this._ref) : super(const ChatState(messages: [])) {
    _ws = _ref.read(webSocketServiceProvider.notifier);

    _wsSubscription = _ws.messageStream.listen(
      _handleIncomingMessage,
      onError: (e, st) {
        state = state.copyWith(
          errorMessage: e.toString(),
          isTyping: false,
        );
      },
    );

    _ws.connect();
  }

  final Ref _ref;
  late final WebSocketService _ws;
  StreamSubscription<String>? _wsSubscription;

  int _messageCounter = 0;
  int _streamingAssistantCounter = 0;

  void _syncConnectionStatus() {
    final wsStatus = _ref.read(webSocketServiceProvider).status;
    state = state.copyWith(connectionStatus: wsStatus);
  }

  String _nextMessageId() {
    _messageCounter++;
    return 'msg_${DateTime.now().microsecondsSinceEpoch}_$_messageCounter';
  }

  String _nextAssistantStreamingId() {
    _streamingAssistantCounter++;
    return 'a_stream_${DateTime.now().microsecondsSinceEpoch}_$_streamingAssistantCounter';
  }

  void _handleIncomingMessage(String raw) {
    _syncConnectionStatus();

    Map<String, dynamic> json;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) {
        _addUnknownAssistantMessage(raw);
        return;
      }
      json = decoded;
    } catch (_) {
      _addUnknownAssistantMessage(raw);
      return;
    }

    final type = json['type']?.toString();
    switch (type) {
      case 'chat.token':
        _handleToken(json);
        return;
      case 'chat.done':
        _handleDone(json);
        return;
      case 'chat.error':
        _handleError(json);
        return;
      default:
        _addUnknownAssistantMessage(raw);
        return;
    }
  }
void _handleToken(Map<String, dynamic> json) {
  print("TOKEN RECEIVED: ${json['content']}");

  final messageId = json['message_id']?.toString();
  final content = json['content']?.toString() ?? '';

  state = state.copyWith(
    isTyping: true,
    errorMessage: null,
    clearError: true,
  );

  final updated = List<ChatMessage>.from(state.messages);

  final idx = messageId == null
      ? -1
      : updated.lastIndexWhere(
          (m) => m.role == MessageRole.assistant && m.id == messageId,
        );

  if (idx != -1) {
    final current = updated[idx];
    updated[idx] = current.copyWith(
      content: current.content + content,
      status: MessageStatus.streaming,
    );
  } else {
    updated.add(
      ChatMessage(
        id: messageId ?? _nextAssistantStreamingId(),
        role: MessageRole.assistant,
        content: content,
        timestamp: DateTime.now(),
        status: MessageStatus.streaming,
      ),
    );
  }

  print("STATE AFTER TOKEN:");
  for (final m in updated) {
    print("${m.role}: ${m.content}");
  }

  state = state.copyWith(messages: updated);
}

  void _handleDone(Map<String, dynamic> json) {
    final messageId = json['message_id']?.toString();
    final updated = List<ChatMessage>.from(state.messages);

    if (messageId != null) {
      final idx = updated.lastIndexWhere(
        (m) =>
            m.role == MessageRole.assistant &&
            m.id == messageId &&
            m.isStreaming,
      );
      if (idx != -1) {
        updated[idx] = updated[idx].copyWith(status: MessageStatus.complete);
      }
    } else {
      for (int i = updated.length - 1; i >= 0; i--) {
        final m = updated[i];
        if (m.role == MessageRole.assistant && m.isStreaming) {
          updated[i] = m.copyWith(status: MessageStatus.complete);
          break;
        }
      }
    }

    state = state.copyWith(messages: updated, isTyping: false);
  }

  void _handleError(Map<String, dynamic> json) {
    final err = json['error']?.toString() ?? 'Unknown error';

    final updated = List<ChatMessage>.from(state.messages);
    for (int i = updated.length - 1; i >= 0; i--) {
      final m = updated[i];
      if (m.role == MessageRole.assistant && m.isStreaming) {
        updated[i] = m.copyWith(status: MessageStatus.error);
        break;
      }
    }

    state = state.copyWith(
      messages: updated,
      isTyping: false,
      errorMessage: err,
    );
  }

  void _addUnknownAssistantMessage(String raw) {
    final updated = List<ChatMessage>.from(state.messages);

    final lastIdx = updated.lastIndexWhere(
      (m) => m.role == MessageRole.assistant && m.isStreaming,
    );

    if (lastIdx != -1) {
      final last = updated[lastIdx];
      updated[lastIdx] = last.copyWith(content: last.content + raw);
    } else {
      updated.add(
        ChatMessage(
          id: _nextAssistantStreamingId(),
          role: MessageRole.assistant,
          content: raw,
          timestamp: DateTime.now(),
          status: MessageStatus.complete,
        ),
      );
    }

    state = state.copyWith(messages: updated, isTyping: false);
  }

  void _markLastUserMessageSent() {
    final updated = List<ChatMessage>.from(state.messages);
    for (int i = updated.length - 1; i >= 0; i--) {
      final m = updated[i];
      if (m.isUser && m.status == MessageStatus.sending) {
        updated[i] = m.copyWith(status: MessageStatus.sent);
        break;
      }
    }
    state = state.copyWith(messages: updated);
  }
void sendMessage(String content) {
  final text = content.trim();
  if (text.isEmpty) return;

  final wsStatus = _ref.read(webSocketServiceProvider).status;
  if (wsStatus != WebSocketStatus.connected) return;

  final id = _nextMessageId();

  print("STATE BEFORE SEND:");
  for (final m in state.messages) {
    print("${m.role}: ${m.content}");
  }

  final userMessage = ChatMessage(
    id: id,
    role: MessageRole.user,
    content: text,
    timestamp: DateTime.now(),
    status: MessageStatus.sending,
  );

  state = state.copyWith(
    messages: [...state.messages, userMessage],
    isTyping: false,
    errorMessage: null,
    clearError: true,
  );

  print("STATE AFTER ADDING USER:");
  for (final m in state.messages) {
    print("${m.role}: ${m.content}");
  }

  _ws.send(
    jsonEncode({
      'type': 'chat.send',
      'message_id': id,
      'content': text,
    }),
  );

  _markLastUserMessageSent();
}
  Future<void> reconnect() async {
    await _ws.disconnect();
    await _ws.connect();
  }

  void clearMessages() {
    state = state.copyWith(messages: []);
  }

  @override
  void dispose() {
    _wsSubscription?.cancel();
    super.dispose();
  }
}

