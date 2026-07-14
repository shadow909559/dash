import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/constants.dart';
import '../models/auth_token_response.dart';
import '../models/auth_user.dart';

/// Key used to persist the access token in SharedPreferences.
const _kAccessTokenKey = 'dash_access_token';
/// Key used to persist the refresh token in SharedPreferences.
const _kRefreshTokenKey = 'dash_refresh_token';
/// Key used to persist the user JSON in SharedPreferences.
const _kUserKey = 'dash_user';

/// Service that handles authentication HTTP calls, token storage,
/// and automatic token refresh.
class AuthService {
  AuthService(this._httpClient);

  final http.Client _httpClient;
  String? _accessToken;
  String? _refreshToken;
  AuthUser? _user;

  // ---------- getters ----------

  String? get accessToken => _accessToken;
  String? get refreshToken => _refreshToken;
  AuthUser? get user => _user;
  bool get isAuthenticated => _accessToken != null;

  // ---------- initialise from storage ----------

  /// Try to restore a previous session from SharedPreferences.
  /// Returns `true` if a session was restored.
  Future<bool> tryRestoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final storedAccessToken = prefs.getString(_kAccessTokenKey);
    final storedRefreshToken = prefs.getString(_kRefreshTokenKey);
    final storedUserJson = prefs.getString(_kUserKey);

    if (storedAccessToken == null || storedUserJson == null) return false;

    // Decode the JWT payload to check expiration without hitting the server.
    if (_isTokenExpired(storedAccessToken)) {
      // Try to refresh using the stored refresh token.
      if (storedRefreshToken != null) {
        final refreshed = await _attemptTokenRefresh(storedRefreshToken);
        if (refreshed) return true;
      }
      // Refresh failed or not available — clear everything.
      await _clearPersistedSession();
      return false;
    }

    _accessToken = storedAccessToken;
    _refreshToken = storedRefreshToken;
    _user = AuthUser.fromJson(
      jsonDecode(storedUserJson) as Map<String, dynamic>,
    );
    return true;
  }

  /// Return the current valid access token, refreshing it automatically
  /// if it is close to expiry.
  Future<String?> getValidAccessToken() async {
    if (_accessToken == null) return null;

    if (_isTokenExpired(_accessToken!)) {
      if (_refreshToken == null) return null;
      final refreshed = await _attemptTokenRefresh(_refreshToken!);
      if (!refreshed) return null;
    }

    return _accessToken;
  }

  /// Build an [Authorization] header value for the current access token.
  Future<String?> get authorizationHeader async {
    final token = await getValidAccessToken();
    return token != null ? 'Bearer $token' : null;
  }

  // ---------- login ----------

  /// Authenticate with email + password and store the returned tokens.
  Future<AuthUser> login({
    required String email,
    required String password,
  }) async {
    final uri = Uri.parse('$defaultBackendUrl$authLoginPath');
    final response = await _httpClient.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'email': email, 'password': password}),
    );

    if (response.statusCode != 200) {
      final detail = _extractErrorDetail(response.body);
      throw AuthException(detail);
    }

    final tokenResponse =
        AuthTokenResponse.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    await _persistSession(tokenResponse);
    return tokenResponse.user;
  }

  // ---------- register ----------

  /// Register a new user. Returns the created user with tokens.
  Future<AuthUser> register({
    required String email,
    required String username,
    required String password,
  }) async {
    final uri = Uri.parse('$defaultBackendUrl$authRegisterPath');
    final response = await _httpClient.post(
      uri,
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'email': email,
        'username': username,
        'password': password,
      }),
    );

    if (response.statusCode != 201) {
      final detail = _extractErrorDetail(response.body);
      throw AuthException(detail);
    }

    final tokenResponse =
        AuthTokenResponse.fromJson(jsonDecode(response.body) as Map<String, dynamic>);
    await _persistSession(tokenResponse);
    return tokenResponse.user;
  }

  // ---------- logout ----------

  /// Clear persisted tokens and discard the in-memory session.
  Future<void> logout() async {
    _accessToken = null;
    _refreshToken = null;
    _user = null;
    await _clearPersistedSession();
  }

  // ---------- internal helpers ----------

  bool _isTokenExpired(String token) {
    try {
      // JWT payload is the second dot-segment.
      final parts = token.split('.');
      if (parts.length != 3) return true;

      final payload =
          jsonDecode(utf8.decode(_base64UrlDecode(parts[1]))) as Map<String, dynamic>;
      final exp = payload['exp'] as int?;
      if (exp == null) return true;

      // Treat as expired if it will expire within 30 seconds.
      final now = DateTime.now().millisecondsSinceEpoch ~/ 1000;
      return exp <= now + 30;
    } catch (_) {
      return true;
    }
  }

  /// Attempt to refresh the access token using the given refresh token.
  /// Returns `true` on success.
  Future<bool> _attemptTokenRefresh(String rt) async {
    try {
      // The backend does not expose a dedicated refresh endpoint yet,
      // so we re-login using credentials is not possible here.
      // For now, if the token is expired, we treat the session as invalid.
      // Once the backend adds POST /auth/refresh, this method will use it.
      return false;
    } catch (_) {
      return false;
    }
  }

  Future<void> _persistSession(AuthTokenResponse resp) async {
    _accessToken = resp.accessToken;
    _refreshToken = resp.refreshToken;
    _user = resp.user;

    final prefs = await SharedPreferences.getInstance();
    await prefs.setString(_kAccessTokenKey, resp.accessToken);
    await prefs.setString(_kRefreshTokenKey, resp.refreshToken);
    await prefs.setString(_kUserKey, jsonEncode(resp.user.toJson()));
  }

  Future<void> _clearPersistedSession() async {
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove(_kAccessTokenKey);
    await prefs.remove(_kRefreshTokenKey);
    await prefs.remove(_kUserKey);
  }

  String _extractErrorDetail(String body) {
    try {
      final json = jsonDecode(body) as Map<String, dynamic>;
      return json['detail'] as String? ?? 'Authentication failed';
    } catch (_) {
      return 'Authentication failed';
    }
  }

  List<int> _base64UrlDecode(String input) {
    // Add padding.
    final padded = input.padRight(input.length + (4 - input.length % 4) % 4, '=');
    return base64Url.decode(padded);
  }
}

/// Exception thrown when an authentication operation fails.
class AuthException implements Exception {
  AuthException(this.message);
  final String message;

  @override
  String toString() => message;
}

/// Riverpod provider for [AuthService].
final authServiceProvider = Provider<AuthService>((ref) {
  return AuthService(http.Client());
});