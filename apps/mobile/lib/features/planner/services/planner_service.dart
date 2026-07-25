import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';

class GoalsService {
  final Ref _ref;
  GoalsService(this._ref);

  Future<Map<String, String>> _headers() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<List<dynamic>> listGoals() async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$goalsPath'), headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data is List ? data : (data['items'] ?? data);
    }
    throw ApiException(response.statusCode, 'Failed to load goals');
  }

  Future<dynamic> createGoal({required String name, String? description}) async {
    final headers = await _headers();
    final response = await http.post(
      Uri.parse('$defaultBackendUrl$goalsPath'),
      headers: headers,
      body: jsonEncode({
        'name': name,
        if (description != null) 'description': description,
      }),
    );
    if (response.statusCode == 201 || response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to create goal');
  }

  Future<dynamic> getGoal(String id) async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$goalsPath/$id'), headers: headers);
    if (response.statusCode == 200) return jsonDecode(response.body);
    if (response.statusCode == 404) return null;
    throw ApiException(response.statusCode, 'Failed to load goal');
  }

  Future<dynamic> startGoal(String id) async {
    final headers = await _headers();
    final response = await http.post(Uri.parse('$defaultBackendUrl$goalsPath/$id/start'), headers: headers);
    if (response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to start goal');
  }

  Future<List<dynamic>> listTasks(String goalId) async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$goalsPath/$goalId/tasks'), headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data is List ? data : (data['items'] ?? data);
    }
    throw ApiException(response.statusCode, 'Failed to load tasks');
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final goalsServiceProvider = Provider<GoalsService>((ref) {
  return GoalsService(ref);
});
