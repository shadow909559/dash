import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/services/websocket_service.dart';
import '../models/chat_message.dart';

class ChatState {
  final List<ChatMessage> messages;
  final bool isStreaming;
  final bool isTyping;
  final WebSocketStatus connectionStatus;
  final String? errorMessage;

  const ChatState({
    required this.messages,
    this.isStreaming = false,
    this.isTyping = false,
    this.connectionStatus = WebSocketStatus.disconnected,
    this.errorMessage,
  });

  ChatState copyWith({
    List<ChatMessage>? messages,
    bool? isStreaming,
    bool? isTyping,
    WebSocketStatus? connectionStatus,
    String? errorMessage,
    bool clearError = false,
  }) {
    return ChatState(
      messages: messages ?? this.messages,
      isStreaming: isStreaming ?? this.isStreaming,
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

    // Listen to filtered chat messages only
    _wsSubscription = _ws.chatMessageStream.listen(
      _handleChatMessage,
      onError: (e, st) {
        state = state.copyWith(
          errorMessage: e.toString(),
          isStreaming: false,
        );
      },
    );

    // Listen to typing indicators
    _typingSub = _ws.typingStream.listen((isTyping) {
      state = state.copyWith(isTyping: isTyping);
    });

    // Listen to status changes
    _statusSub = _ws.statusStream.listen((status) {
      state = state.copyWith(connectionStatus: status);
    });

    _ws.connect();
  }

  final Ref _ref;
  late final WebSocketService _ws;
  StreamSubscription<Map<String, dynamic>>? _wsSubscription;
  StreamSubscription<bool>? _typingSub;
  StreamSubscription<WebSocketStatus>? _statusSub;

  int _messageCounter = 0;
  int _streamingAssistantCounter = 0;

  String _nextMessageId() {
    _messageCounter++;
    return 'msg_${DateTime.now().microsecondsSinceEpoch}_$_messageCounter';
  }

  String _nextAssistantStreamingId() {
    _streamingAssistantCounter++;
    return 'a_stream_${DateTime.now().microsecondsSinceEpoch}_$_streamingAssistantCounter';
  }

  /// Handle incoming chat messages from the filtered stream.
  /// Only receives: chat.token, chat.done, chat.error, chat.message, assistant, user
  void _handleChatMessage(Map<String, dynamic> json) {
    final type = json['type']?.toString() ?? '';

    switch (type) {
      case 'chat.token':
        _handleToken(json);
        break;
      case 'chat.done':
        _handleDone(json);
        break;
      case 'chat.error':
        _handleError(json);
        break;
      case 'chat.message':
      case 'assistant':
        _handleCompleteMessage(json);
        break;
      case 'user':
        // Server echoed user message — mark as sent
        _syncUserMessage(json);
        break;
      default:
        // Unknown chat type — log but don't create bubbles
        print('[ChatService] Unknown chat message type: $type');
    }
  }

  void _handleToken(Map<String, dynamic> json) {
    final messageId = json['message_id']?.toString();
    final content = json['content']?.toString() ?? '';

    state = state.copyWith(
      isStreaming: true,
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

    state = state.copyWith(
      messages: updated,
      isStreaming: false,
      isTyping: false,
    );
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
      isStreaming: false,
      isTyping: false,
      errorMessage: err,
    );
  }

  /// Handle a complete non-streamed assistant message.
  void _handleCompleteMessage(Map<String, dynamic> json) {
    final messageId = json['message_id']?.toString() ?? _nextAssistantStreamingId();
    final content = json['content']?.toString() ?? json['text']?.toString() ?? '';

    final updated = List<ChatMessage>.from(state.messages);
    updated.add(
      ChatMessage(
        id: messageId,
        role: MessageRole.assistant,
        content: content,
        timestamp: DateTime.now(),
        status: MessageStatus.complete,
      ),
    );

    state = state.copyWith(
      messages: updated,
      isStreaming: false,
      isTyping: false,
    );
  }

  /// Sync a user message that was echoed back by the server.
  void _syncUserMessage(Map<String, dynamic> json) {
    final messageId = json['message_id']?.toString();
    if (messageId == null) return;

    final updated = List<ChatMessage>.from(state.messages);
    for (int i = updated.length - 1; i >= 0; i--) {
      final m = updated[i];
      if (m.isUser && m.id == messageId && m.status == MessageStatus.sent) {
        updated[i] = m.copyWith(status: MessageStatus.sent);
        break;
      }
    }
    state = state.copyWith(messages: updated);
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

    final userMessage = ChatMessage(
      id: id,
      role: MessageRole.user,
      content: text,
      timestamp: DateTime.now(),
      status: MessageStatus.sending,
    );

    state = state.copyWith(
      messages: [...state.messages, userMessage],
      isStreaming: false,
      isTyping: false,
      errorMessage: null,
      clearError: true,
    );

    _ws.send(
      jsonEncode({
        'type': 'chat.send',
        'message_id': id,
        'content': text,
      }),
    );

    _markLastUserMessageSent();
  }

  void cancelStreaming() {
    final updated = List<ChatMessage>.from(state.messages);
    for (int i = updated.length - 1; i >= 0; i--) {
      final m = updated[i];
      if (m.role == MessageRole.assistant && m.isStreaming) {
        updated[i] = m.copyWith(status: MessageStatus.complete);
        break;
      }
    }
    state = state.copyWith(
      messages: updated,
      isStreaming: false,
      isTyping: false,
    );
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
    _typingSub?.cancel();
    _statusSub?.cancel();
    super.dispose();
  }
}