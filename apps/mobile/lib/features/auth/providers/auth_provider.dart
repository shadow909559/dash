import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/auth_user.dart';
import '../services/auth_service.dart';

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
  AuthNotifier(this._authService) : super(AuthState.unknown);

  final AuthService _authService;

  // ---------- initialise ----------

  /// Check SharedPreferences for a persisted session.
  Future<void> checkSession() async {
    final restored = await _authService.tryRestoreSession();
    if (restored && _authService.isAuthenticated) {
      state = AuthState(
        status: AuthStatus.authenticated,
        user: _authService.user,
      );
    } else {
      state = AuthState.unauthenticated;
    }
  }

  // ---------- login ----------

  /// Authenticate with email and password.
  Future<void> login({
    required String email,
    required String password,
  }) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final user = await _authService.login(email: email, password: password);
      state = AuthState(
        status: AuthStatus.authenticated,
        user: user,
      );
    } on AuthException catch (e) {
      state = AuthState.unauthenticated.copyWith(errorMessage: e.message);
    } catch (e) {
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
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final user = await _authService.register(
        email: email,
        username: username,
        password: password,
      );
      state = AuthState(
        status: AuthStatus.authenticated,
        user: user,
      );
    } on AuthException catch (e) {
      state = AuthState.unauthenticated.copyWith(errorMessage: e.message);
    } catch (e) {
      state = AuthState.unauthenticated.copyWith(
        errorMessage: 'Connection error. Please try again.',
      );
    }
  }

  // ---------- logout ----------

  /// Log out and clear the session.
  Future<void> logout() async {
    await _authService.logout();
    state = AuthState.unauthenticated;
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
  return AuthNotifier(authService);
});