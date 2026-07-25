import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';

class MemoryService {
  final Ref _ref;
  MemoryService(this._ref);

  Future<Map<String, String>> _headers() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<List<dynamic>> listMemories({int limit = 50, int offset = 0}) async {
    final headers = await _headers();
    final uri = Uri.parse('$defaultBackendUrl$memoryPath').replace(queryParameters: {
      'limit': limit.toString(),
      'offset': offset.toString(),
    });
    final response = await http.get(uri, headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      return (data['items'] as List?) ?? [];
    }
    throw ApiException(response.statusCode, 'Failed to load memories');
  }

  Future<dynamic> getMemory(String id) async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$memoryPath/$id'), headers: headers);
    if (response.statusCode == 200) return jsonDecode(response.body);
    if (response.statusCode == 404) return null;
    throw ApiException(response.statusCode, 'Failed to load memory');
  }

  Future<dynamic> createMemory({required String content, String? category, String? source, int importance = 1}) async {
    final headers = await _headers();
    final response = await http.post(
      Uri.parse('$defaultBackendUrl$memoryPath'),
      headers: headers,
      body: jsonEncode({
        'content': content,
        if (category != null) 'category': category,
        if (source != null) 'source': source,
        'importance': importance,
      }),
    );
    if (response.statusCode == 201 || response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to create memory');
  }

  Future<dynamic> updateMemory(String id, {String? content, String? category, String? source, int? importance}) async {
    final headers = await _headers();
    final body = <String, dynamic>{};
    if (content != null) body['content'] = content;
    if (category != null) body['category'] = category;
    if (source != null) body['source'] = source;
    if (importance != null) body['importance'] = importance;
    final response = await http.patch(
      Uri.parse('$defaultBackendUrl$memoryPath/$id'),
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to update memory');
  }

  Future<void> deleteMemory(String id) async {
    final headers = await _headers();
    final response = await http.delete(Uri.parse('$defaultBackendUrl$memoryPath/$id'), headers: headers);
    if (response.statusCode != 204 && response.statusCode != 200) {
      throw ApiException(response.statusCode, 'Failed to delete memory');
    }
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final memoryServiceProvider = Provider<MemoryService>((ref) {
  return MemoryService(ref);
});
