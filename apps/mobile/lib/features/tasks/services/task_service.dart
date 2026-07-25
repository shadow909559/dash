import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';

class TaskService {
  final Ref _ref;
  TaskService(this._ref);

  Future<Map<String, String>> _headers() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<List<dynamic>> listTasks(String? goalId) async {
    final headers = await _headers();
    final path = goalId != null ? '$goalsPath/$goalId/tasks' : goalsPath;
    final response = await http.get(Uri.parse('$defaultBackendUrl$path'), headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data is List ? data : (data['items'] ?? data);
    }
    throw ApiException(response.statusCode, 'Failed to load tasks');
  }

  Future<dynamic> createTask(String? goalId, {required String name, String? description}) async {
    final headers = await _headers();
    final path = goalId != null ? '$goalsPath/$goalId/tasks' : goalsPath;
    final response = await http.post(
      Uri.parse('$defaultBackendUrl$path'),
      headers: headers,
      body: jsonEncode({
        'name': name,
        'description': description,
      }),
    );
    if (response.statusCode == 201 || response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to create task');
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final taskServiceProvider = Provider<TaskService>((ref) {
  return TaskService(ref);
});
