import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../services/auth_service.dart';
import '../../../core/services/websocket_service.dart';
import '../models/auth_user.dart';

/// Possible states of the authentication flow.
enum AuthStatus {
  /// Initial state — we are checking SharedPreferences.
  unknown,
  /// User is authenticated.
  authenticated,
  /// User is not authenticated.
  unauthenticated,
}

/// State held by [AuthNotifier].
class AuthState {
  final AuthStatus status;
  final AuthUser? user;
  final String? errorMessage;
  final bool isLoading;

  const AuthState({
    required this.status,
    this.user,
    this.errorMessage,
    this.isLoading = false,
  });

  AuthState copyWith({
    AuthStatus? status,
    AuthUser? user,
    String? errorMessage,
    bool clearError = false,
    bool? isLoading,
  }) {
    return AuthState(
      status: status ?? this.status,
      user: user ?? this.user,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
      isLoading: isLoading ?? this.isLoading,
    );
  }

  static const unknown = AuthState(status: AuthStatus.unknown);
  static const unauthenticated = AuthState(status: AuthStatus.unauthenticated);
}

/// Notifier that manages authentication state.
class AuthNotifier extends StateNotifier<AuthState> {
  AuthNotifier(this._ref, this._authService) : super(AuthState.unknown);

  final Ref _ref;
  final AuthService _authService;

  // ---------- initialise ----------

  /// Check SharedPreferences for a persisted session.
  Future<void> checkSession() async {
    debugPrint('[AuthNotifier] checkSession: starting...');
    final restored = await _authService.tryRestoreSession();
    debugPrint('[AuthNotifier] checkSession: restored=$restored, isAuthenticated=${_authService.isAuthenticated}');
    if (restored && _authService.isAuthenticated) {
      state = AuthState(
        status: AuthStatus.authenticated,
        user: _authService.user,
      );
      debugPrint('[AuthNotifier] checkSession: Session restored, user=${_authService.user?.email}');
    } else {
      state = AuthState.unauthenticated;
      debugPrint('[AuthNotifier] checkSession: No session found');
    }
  }

  // ---------- login ----------

  /// Authenticate with email and password.
  Future<void> login({
    required String email,
    required String password,
  }) async {
    debugPrint('[AuthNotifier] login: starting for email=$email');
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final user = await _authService.login(email: email, password: password);
      debugPrint('[AuthNotifier] login: success, user=${user.email}');
      state = AuthState(
        status: AuthStatus.authenticated,
        user: user,
      );
      _reconnectWebSocket();
    } on AuthException catch (e) {
      debugPrint('[AuthNotifier] login: AuthException: ${e.message}');
      state = AuthState.unauthenticated.copyWith(errorMessage: e.message);
    } catch (e) {
      debugPrint('[AuthNotifier] login: unexpected error: $e');
      state = AuthState.unauthenticated.copyWith(
        errorMessage: 'Connection error. Please try again.',
      );
    }
  }

  // ---------- register ----------

  /// Register a new account and automatically log in.
  Future<void> register({
    required String email,
    required String username,
    required String password,
  }) async {
    debugPrint('[AuthNotifier] register: starting for email=$email, username=$username');
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final user = await _authService.register(
        email: email,
        username: username,
        password: password,
      );
      debugPrint('[AuthNotifier] register: success, user=${user.email}');
      state = AuthState(
        status: AuthStatus.authenticated,
        user: user,
      );
      _reconnectWebSocket();
    } on AuthException catch (e) {
      debugPrint('[AuthNotifier] register: AuthException: ${e.message}');
      state = AuthState.unauthenticated.copyWith(errorMessage: e.message);
    } catch (e) {
      debugPrint('[AuthNotifier] register: unexpected error: $e');
      state = AuthState.unauthenticated.copyWith(
        errorMessage: 'Connection error. Please try again.',
      );
    }
  }

  /// Reconnect WebSocket after authentication, without affecting auth state.
  void _reconnectWebSocket() {
    try {
      final ws = _ref.read(webSocketServiceProvider.notifier);
      // Fire-and-forget: WebSocket failure must NOT affect auth state.
      unawaited(ws.disconnect().then((_) => ws.connect()).catchError((_) {}));
    } catch (e) {
      // WebSocket failure should NEVER overwrite authenticated state.
      debugPrint('[AuthNotifier] WebSocket reconnect failed (non-fatal): $e');
    }
  }

  // ---------- logout ----------

  /// Log out and clear the session.
  Future<void> logout() async {
    await _authService.logout();
    state = AuthState.unauthenticated;
    final ws = _ref.read(webSocketServiceProvider.notifier);
    await ws.disconnect();
  }

  /// Clear any displayed error message.
  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

/// Riverpod provider for [AuthNotifier].
final authProvider =
    StateNotifierProvider<AuthNotifier, AuthState>((ref) {
  final authService = ref.watch(authServiceProvider);
  return AuthNotifier(ref, authService);
});
