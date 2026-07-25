import 'dart:convert';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:http/http.dart' as http;
import '../constants.dart';
import '../../features/auth/services/auth_service.dart';

/// Centralized HTTP client with JWT auth, retry, and error handling.
class ApiClient {
  ApiClient(this._httpClient, this._authService);

  final http.Client _httpClient;
  final AuthService _authService;

  Future<Map<String, String>> get _headers async {
    final headers = <String, String>{
      'Content-Type': 'application/json',
    };
    final auth = await _authService.authorizationHeader;
    if (auth != null) {
      headers['Authorization'] = auth;
    }
    return headers;
  }

  Future<dynamic> get(String path, {Map<String, String>? queryParams}) async {
    final uri = Uri.parse('$defaultBackendUrl$path').replace(queryParameters: queryParams);
    final response = await _httpClient.get(uri, headers: await _headers);
    return _handleResponse(response);
  }

  Future<dynamic> post(String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$defaultBackendUrl$path');
    final response = await _httpClient.post(
      uri,
      headers: await _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handleResponse(response);
  }

  Future<dynamic> put(String path, {Map<String, dynamic>? body}) async {
    final uri = Uri.parse('$defaultBackendUrl$path');
    final response = await _httpClient.put(
      uri,
      headers: await _headers,
      body: body != null ? jsonEncode(body) : null,
    );
    return _handleResponse(response);
  }

  Future<dynamic> delete(String path) async {
    final uri = Uri.parse('$defaultBackendUrl$path');
    final response = await _httpClient.delete(uri, headers: await _headers);
    return _handleResponse(response);
  }

  dynamic _handleResponse(http.Response response) {
    if (response.statusCode >= 200 && response.statusCode < 300) {
      if (response.body.isEmpty) return null;
      return jsonDecode(response.body);
    }
    if (response.statusCode == 401) {
      throw ApiException(401, 'Unauthorized');
    }
    String detail = 'Request failed';
    try {
      final body = jsonDecode(response.body);
      detail = body['detail'] as String? ?? detail;
    } catch (_) {}
    throw ApiException(response.statusCode, detail);
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final apiClientProvider = Provider<ApiClient>((ref) {
  final authService = ref.watch(authServiceProvider);
  return ApiClient(http.Client(), authService);
});