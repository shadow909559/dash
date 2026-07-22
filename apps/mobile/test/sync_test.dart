import 'package:flutter_test/flutter_test.dart';
import 'package:dash_mobile/core/sync/offline_queue.dart';
import 'package:dash_mobile/core/sync/sync_state.dart';

void main() {
  TestWidgetsFlutterBinding.ensureInitialized();

  group('OfflineMessageQueue', () {
    test('enqueue and dequeue messages', () async {
      final queue = OfflineMessageQueue();
      await queue.clear();
      expect(queue.isEmpty, isTrue);

      final msg1 = QueuedMessage(
        id: 'msg_1',
        type: 'chat.send',
        payload: {'content': 'Hello'},
        timestamp: DateTime.now(),
      );

      final msg2 = QueuedMessage(
        id: 'msg_2',
        type: 'chat.send',
        payload: {'content': 'World'},
        timestamp: DateTime.now(),
      );

      await queue.enqueue(msg1);
      await queue.enqueue(msg2);

      expect(queue.length, equals(2));
      expect(queue.isNotEmpty, isTrue);

      final dequeued1 = queue.dequeue();
      expect(dequeued1?.id, equals('msg_1'));
      expect(dequeued1?.payload['content'], equals('Hello'));

      final dequeued2 = queue.dequeue();
      expect(dequeued2?.id, equals('msg_2'));

      expect(queue.isEmpty, isTrue);
    });

    test('removeSent removes specified message IDs', () async {
      final queue = OfflineMessageQueue();
      await queue.clear();

      final msg1 = QueuedMessage(
        id: 'msg_10',
        type: 'chat.send',
        payload: {'content': 'Test 1'},
        timestamp: DateTime.now(),
      );

      final msg2 = QueuedMessage(
        id: 'msg_11',
        type: 'chat.send',
        payload: {'content': 'Test 2'},
        timestamp: DateTime.now(),
      );

      await queue.enqueue(msg1);
      await queue.enqueue(msg2);

      await queue.removeSent(['msg_10']);
      expect(queue.length, equals(1));

      final remaining = queue.peek();
      expect(remaining?.id, equals('msg_11'));
    });

    test('incrementRetries increments retry counter on all queued messages', () async {
      final queue = OfflineMessageQueue();
      await queue.clear();

      final msg = QueuedMessage(
        id: 'msg_20',
        type: 'chat.send',
        payload: {'content': 'Retry me'},
        timestamp: DateTime.now(),
        retryCount: 0,
      );

      await queue.enqueue(msg);
      await queue.incrementRetries();

      final updated = queue.peek();
      expect(updated?.retryCount, equals(1));
    });
  });

  group('SyncState', () {
    test('default constructor values', () {
      const state = SyncState();
      expect(state.status, equals(SyncStatus.disconnected));
      expect(state.serviceStatus, equals(SyncServiceStatus.idle));
      expect(state.session, isNull);
      expect(state.pendingMessages, equals(0));
    });

    test('copyWith updates fields correctly', () {
      const state = SyncState();
      final updated = state.copyWith(
        status: SyncStatus.connected,
        serviceStatus: SyncServiceStatus.syncing,
        pendingMessages: 5,
        session: const SyncSession(
          sessionId: 'sess_1',
          clientId: 'client_1',
          recoveryCount: 2,
        ),
      );

      expect(updated.status, equals(SyncStatus.connected));
      expect(updated.serviceStatus, equals(SyncServiceStatus.syncing));
      expect(updated.pendingMessages, equals(5));
      expect(updated.session?.sessionId, equals('sess_1'));
      expect(updated.session?.recoveryCount, equals(2));
    });
  });
}
