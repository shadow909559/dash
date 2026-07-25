import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';
import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';

class PersonalService {
  final Ref _ref;
  PersonalService(this._ref);

  Future<Map<String, String>> _headers() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<dynamic> getProfile() async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$personalPath/profile'), headers: headers);
    if (response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to load profile');
  }

  Future<dynamic> updateProfile(Map<String, dynamic> data) async {
    final headers = await _headers();
    final response = await http.post(
      Uri.parse('$defaultBackendUrl$personalPath/profile'),
      headers: headers,
      body: jsonEncode(data),
    );
    if (response.statusCode == 200 || response.statusCode == 201) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to update profile');
  }

  Future<dynamic> getDailySummary() async {
    final headers = await _headers();
    final response = await http.get(Uri.parse('$defaultBackendUrl$personalPath/summary'), headers: headers);
    if (response.statusCode == 200) return jsonDecode(response.body);
    throw ApiException(response.statusCode, 'Failed to load summary');
  }
}

class ApiException implements Exception {
  ApiException(this.statusCode, this.message);
  final int statusCode;
  final String message;
  @override
  String toString() => message;
}

final personalServiceProvider = Provider<PersonalService>((ref) {
  return PersonalService(ref);
});
