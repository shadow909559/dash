# DASH Flutter — Developer Guide

## Code Style

- Follow the [Flutter style guide](https://flutter.dev/docs/development/tools/formatting)
- Use `dart format` before committing
- Use `const` constructors where possible (enforced by linter)
- Prefer `withValues(alpha:)` over `withOpacity()` for color opacity

## State Management Conventions

### Riverpod Patterns

```dart
// Simple state
final myStateProvider = StateProvider<Type>((ref) => initialValue);

// Complex state with methods
final myServiceProvider = StateNotifierProvider<MyService, MyState>(
  (ref) => MyService(ref),
);

// Singleton
final myRepoProvider = Provider<MyRepository>((ref) => MyRepository(ref));
```

### State Immutability

- All state classes use `copyWith` pattern
- Never mutate state directly — always create new instances
- Use `@immutable` annotation on model classes

## Naming Conventions

- **Files:** `snake_case.dart`
- **Classes:** `PascalCase`
- **Methods/Variables:** `camelCase`
- **Private members:** `_camelCase`
- **Providers:** `camelCaseProvider`
- **State classes:** `ThingState`
- **Notifiers:** `ThingService` or `ThingNotifier`

## Widget Structure

```
- ConsumerStatefulWidget (with automaticKeepAlive)
  - _WidgetState extends ConsumerState<Widget>
    - build() -> Widget tree
    - _helper methods for sub-widgets
    - Event handlers
```

## Testing Conventions

- Model tests: pure Dart, no widget tree needed
- Widget tests: use `pump()` not `pumpAndSettle()` when timers active
- Test files match `*_test.dart` pattern
- One `group()` per class or feature

## Git Workflow

1. Create feature branch from `main`
2. Run `flutter analyze` — must be clean
3. Run `flutter test` — all must pass
4. Submit PR with description
5. Squash merge to `main`

## Performance Notes

- Use `const` widgets where possible
- Avoid unnecessary rebuilds with `select()` on providers
- Keep `ListView.builder()` for long lists
- Use `AutomaticKeepAliveClientMixin` for tab pages
- Dispose controllers and subscriptions in `dispose()`
