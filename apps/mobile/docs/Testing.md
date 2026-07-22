# DASH Flutter — Testing Guide

## Test Suite Overview

The Flutter test suite covers models, services, and widget rendering. All tests are in `apps/mobile/test/`.

## Running Tests

```bash
cd apps/mobile

# Run all tests
flutter test

# Run a specific test file
flutter test test/chat_provider_test.dart

# Run with coverage
flutter test --coverage

# View coverage report
genhtml coverage/lcov.info -o coverage/html
```

## Test Structure

```
test/
├── auth_service_test.dart      # Auth model tests (4 tests)
├── chat_provider_test.dart     # ChatMessage & Conversation model tests (15 tests)
├── sync_test.dart              # OfflineQueue & SyncState tests (5 tests)
└── widget_test.dart            # Widget rendering test (1 test)
```

## Test Categories

### Model Tests (File: `test/chat_provider_test.dart`)

Tests for `ChatMessage` and `Conversation` models:

- **ChatMessage creation** — User and assistant roles
- **Streaming detection** — `isStreaming` getter
- **copyWith** — Immutable updates
- **JSON serialization** — `toJson` / `fromJson` round-trip
- **Legacy format** — Backward compatibility with `created_at` field
- **Conversation defaults** — Default values for optional fields
- **displayTitle** — Falls back to 'New Chat'
- **timeAgo** — Relative time formatting (just now, m, h, d)

### Auth Model Tests (File: `test/auth_service_test.dart`)

Tests for `AuthUser` and `AuthTokenResponse`:

- **User from JSON** — Correct field mapping
- **User to JSON** — Round-trip serialization
- **Token from JSON** — All fields including defaults
- **Default token_type** — Fallback to 'bearer'

### Sync Tests (File: `test/sync_test.dart`)

Tests for `OfflineMessageQueue` and `SyncState`:

- **Enqueue/dequeue** — FIFO ordering
- **removeSent** — Selective removal
- **incrementRetries** — Retry counting
- **SyncState defaults** — Initial state
- **copyWith** — State transitions

### Widget Tests (File: `test/widget_test.dart`)

- **Splash scaffold** — App renders without errors

## Writing New Tests

### Model Test Pattern

```dart
test('describes the behavior', () async {
  // Arrange
  final model = MyModel(...);

  // Act
  final result = model.someMethod();

  // Assert
  expect(result, equals(expectedValue));
});
```

### Widget Test Pattern

```dart
testWidgets('describes widget behavior', (tester) async {
  // Arrange
  await tester.pumpWidget(const MyWidget());

  // Act
  await tester.tap(find.byIcon(Icons.add));
  await tester.pump();

  // Assert
  expect(find.text('Result'), findsOneWidget);
});
```

## Best Practices

1. **Test models thoroughly** — Models are the foundation of state management
2. **Avoid pumpAndSettle** when timers/network are involved — use `pump()` instead
3. **Use `TestWidgetsFlutterBinding.ensureInitialized()`** in all test files
4. **Test edge cases** — Empty strings, null values, boundary conditions
5. **Test JSON round-trips** — Ensure serialization is reversible
6. **Keep tests fast** — Avoid network calls and timers in unit tests

## CI Integration

Tests run automatically on every PR. The CI pipeline:

1. `flutter analyze` — Zero issues required
2. `flutter test` — All tests must pass
3. `dart format --set-exit-if-changed` — Code must be formatted
