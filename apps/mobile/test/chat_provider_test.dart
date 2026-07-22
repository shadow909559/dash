import 'package:flutter_test/flutter_test.dart';
import 'package:dash_mobile/features/chat/models/chat_message.dart';
import 'package:dash_mobile/features/chat/models/conversation.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('ChatMessage', () {
    test('creates a user message', () {
      final msg = ChatMessage(
        id: 'msg_1',
        role: MessageRole.user,
        content: 'Hello',
        timestamp: DateTime.now(),
      );

      expect(msg.isUser, isTrue);
      expect(msg.isAssistant, isFalse);
      expect(msg.isStreaming, isFalse);
      expect(msg.status, equals(MessageStatus.sent));
    });

    test('creates an assistant message', () {
      final msg = ChatMessage(
        id: 'msg_2',
        role: MessageRole.assistant,
        content: 'Hi there!',
        timestamp: DateTime.now(),
      );

      expect(msg.isUser, isFalse);
      expect(msg.isAssistant, isTrue);
    });

    test('identifies streaming messages', () {
      final msg = ChatMessage(
        id: 'msg_3',
        role: MessageRole.assistant,
        content: 'Thinking...',
        timestamp: DateTime.now(),
        status: MessageStatus.streaming,
      );

      expect(msg.isStreaming, isTrue);
    });

    test('copyWith updates fields', () {
      final msg = ChatMessage(
        id: 'msg_4',
        role: MessageRole.user,
        content: 'Original',
        timestamp: DateTime.now(),
      );

      final updated = msg.copyWith(content: 'Updated', status: MessageStatus.sending);
      expect(updated.content, equals('Updated'));
      expect(updated.status, equals(MessageStatus.sending));
      expect(updated.id, equals('msg_4'));
    });

    test('toJson and fromJson round-trip', () {
      final msg = ChatMessage(
        id: 'msg_5',
        role: MessageRole.assistant,
        content: 'Test content',
        timestamp: DateTime(2025, 1, 15, 10, 30),
        status: MessageStatus.complete,
      );

      final json = msg.toJson();
      final restored = ChatMessage.fromJson(json);

      expect(restored.id, equals(msg.id));
      expect(restored.role, equals(msg.role));
      expect(restored.content, equals(msg.content));
      expect(restored.status, equals(msg.status));
    });

    test('fromJson handles legacy format with created_at', () {
      final json = {
        'id': 'msg_6',
        'role': 'assistant',
        'content': 'Legacy',
        'created_at': '2025-01-15T10:30:00.000',
      };

      final msg = ChatMessage.fromJson(json);
      expect(msg.id, equals('msg_6'));
      expect(msg.content, equals('Legacy'));
      expect(msg.role, equals(MessageRole.assistant));
    });
  });

  group('Conversation', () {
    final now = DateTime.now();

    test('creates a conversation with defaults', () {
      final conv = Conversation(
        id: 'conv_1',
        createdAt: now,
        updatedAt: now,
      );

      expect(conv.id, equals('conv_1'));
      expect(conv.isPinned, isFalse);
      expect(conv.isFavorited, isFalse);
      expect(conv.isArchived, isFalse);
      expect(conv.displayTitle, equals('New Chat'));
    });

    test('displayTitle returns title when set', () {
      final conv = Conversation(
        id: 'conv_2',
        title: 'My Chat',
        createdAt: now,
        updatedAt: now,
      );

      expect(conv.displayTitle, equals('My Chat'));
    });

    test('copyWith creates updated copy', () {
      final conv = Conversation(
        id: 'conv_3',
        createdAt: now,
        updatedAt: now,
      );

      final updated = conv.copyWith(
        title: 'Renamed',
        isPinned: true,
        messageCount: 5,
      );

      expect(updated.title, equals('Renamed'));
      expect(updated.isPinned, isTrue);
      expect(updated.messageCount, equals(5));
      expect(updated.id, equals('conv_3'));
    });

    test('toJson and fromJson round-trip', () {
      final conv = Conversation(
        id: 'conv_4',
        title: 'Test',
        isPinned: true,
        isFavorited: false,
        isArchived: false,
        messageCount: 10,
        lastMessageAt: '2025-01-15T10:30:00.000',
        model: 'gpt-4',
        createdAt: now,
        updatedAt: now,
      );

      final json = conv.toJson();
      final restored = Conversation.fromJson(json);

      expect(restored.id, equals(conv.id));
      expect(restored.title, equals(conv.title));
      expect(restored.isPinned, equals(conv.isPinned));
      expect(restored.messageCount, equals(conv.messageCount));
    });

    test('timeAgo returns relative time', () {
      final justNow = Conversation(
        id: 'conv_5',
        createdAt: DateTime.now(),
        updatedAt: DateTime.now(),
      );
      expect(justNow.timeAgo, equals('Just now'));

      final minutesAgo = Conversation(
        id: 'conv_6',
        createdAt: DateTime.now().subtract(const Duration(minutes: 5)),
        updatedAt: DateTime.now().subtract(const Duration(minutes: 5)),
      );
      expect(minutesAgo.timeAgo, equals('5m ago'));

      final hoursAgo = Conversation(
        id: 'conv_7',
        createdAt: DateTime.now().subtract(const Duration(hours: 3)),
        updatedAt: DateTime.now().subtract(const Duration(hours: 3)),
      );
      expect(hoursAgo.timeAgo, equals('3h ago'));

      final daysAgo = Conversation(
        id: 'conv_8',
        createdAt: DateTime.now().subtract(const Duration(days: 2)),
        updatedAt: DateTime.now().subtract(const Duration(days: 2)),
      );
      expect(daysAgo.timeAgo, equals('2d ago'));
    });
  });
}

