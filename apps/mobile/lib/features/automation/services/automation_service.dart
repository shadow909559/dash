import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';

class AutomationService {
  final Ref _ref;
  AutomationService(this._ref);

  Future<Map<String, String>> _headers() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<List<dynamic>> listAutomations() async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$automationPath'), headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data is List ? data : (data['items'] ?? data);
    }
    throw ApiException(response.statusCode, 'Failed to load automations');
  }

  Future<dynamic> createAutomation({required String name, required triggerType, required String toolName, List<dynamic>? toolArguments, bool enabled = true, String? description, Map<String, dynamic>? schedule}) async {
    final headers = await _headers();
    final body = <String, dynamic>{
      'name': name,
      'trigger_type': triggerType,
      'tool_name': toolName,
      'tool_arguments': toolArguments ?? [],
      'enabled': enabled,
    };
    if (description != null) body['description'] = description;
    if (schedule != null) body['schedule'] = schedule;
    final response = await http.post(
      Uri.parse('$defaultBackendUrl$automationPath'),
      headers: headers,
      body: jsonEncode(body),
    );
    if (response.statusCode == 201 || response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to create automation');
  }

  Future<dynamic> updateAutomation(String id, {Map<String, dynamic>? updateData}) async {
    final headers = await _headers();
    final response = await http.patch(
      Uri.parse('$defaultBackendUrl$automationPath/$id'),
      headers: headers,
      body: jsonEncode(updateData ?? {}),
    );
    if (response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to update automation');
  }

  Future<void> deleteAutomation(String id) async {
    final headers = await _headers();
    final response = await http.delete(Uri.parse('$defaultBackendUrl$automationPath/$id'), headers: headers);
    if (response.statusCode != 204 && response.statusCode != 200) {
      throw ApiException(response.statusCode, 'Failed to delete automation');
    }
  }

  Future<List<dynamic>> getAutomationHistory(String id) async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$automationPath/$id/history'), headers: headers);
    if (response.statusCode == 200) {
      final data = jsonDecode(response.body);
      return data is List ? data : (data['items'] ?? data);
    }
    throw ApiException(response.statusCode, 'Failed to load automation history');
  }

  Future<void> toggleAutomation(String id, bool enabled) async {
    return updateAutomation(id, updateData: {'enabled': enabled});
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final automationServiceProvider = Provider<AutomationService>((ref) {
  return AutomationService(ref);
});
