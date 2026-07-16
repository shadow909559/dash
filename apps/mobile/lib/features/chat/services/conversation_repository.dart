import 'dart:convert';
import 'package:http/http.dart' as http;
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../../core/constants.dart';
import '../../../features/auth/services/auth_service.dart';
import '../models/conversation.dart';
import '../models/chat_message.dart';

class ConversationRepository {
  final Ref _ref;

  ConversationRepository(this._ref);

  String get _baseUrl => '$defaultBackendUrl/api/v1/conversations';

  Future<Map<String, String>> _authHeaders() async {
    final auth = _ref.read(authServiceProvider);
    final token = await auth.getValidAccessToken();
    return {
      'Content-Type': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  /// Fetch all conversations for the current user.
  Future<ConversationListResponse> list({
    int limit = 50,
    int offset = 0,
    bool includeArchived = false,
  }) async {
    final headers = await _authHeaders();
    final uri = Uri.parse(_baseUrl).replace(queryParameters: {
      'limit': limit.toString(),
      'offset': offset.toString(),
      'include_archived': includeArchived.toString(),
    });

    final response = await http.get(uri, headers: headers);
    if (response.statusCode == 200) {
      return ConversationListResponse.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load conversations: ${response.statusCode}');
  }

  /// Search conversations by title.
  Future<List<Conversation>> search(String query, {int limit = 20}) async {
    final headers = await _authHeaders();
    final uri = Uri.parse('$_baseUrl/search').replace(queryParameters: {
      'q': query,
      'limit': limit.toString(),
    });

    final response = await http.get(uri, headers: headers);
    if (response.statusCode == 200) {
      final list = jsonDecode(response.body) as List;
      return list.map((e) => Conversation.fromJson(e)).toList();
    }
    throw Exception('Failed to search conversations: ${response.statusCode}');
  }

  /// Create a new conversation.
  Future<Conversation> create({String? title, String? model}) async {
    final headers = await _authHeaders();
    final response = await http.post(
      Uri.parse(_baseUrl),
      headers: headers,
      body: jsonEncode({
        if (title != null) 'title': title,
        if (model != null) 'model': model,
      }),
    );

    if (response.statusCode == 201) {
      return Conversation.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to create conversation: ${response.statusCode}');
  }

  /// Get a single conversation by id.
  Future<Conversation> get(String id) async {
    final headers = await _authHeaders();
    final response = await http.get(Uri.parse('$_baseUrl/$id'), headers: headers);

    if (response.statusCode == 200) {
      final data = jsonDecode(response.body) as Map<String, dynamic>;
      // The full response includes more fields; map to Conversation list view
      return Conversation.fromJson(data);
    }
    throw Exception('Failed to load conversation: ${response.statusCode}');
  }

  /// Update conversation metadata.
  Future<Conversation> update(
    String id, {
    String? title,
    bool? isPinned,
    bool? isFavorited,
    bool? isArchived,
    String? model,
  }) async {
    final headers = await _authHeaders();
    final body = <String, dynamic>{};
    if (title != null) body['title'] = title;
    if (isPinned != null) body['is_pinned'] = isPinned;
    if (isFavorited != null) body['is_favorited'] = isFavorited;
    if (isArchived != null) body['is_archived'] = isArchived;
    if (model != null) body['model'] = model;

    final response = await http.patch(
      Uri.parse('$_baseUrl/$id'),
      headers: headers,
      body: jsonEncode(body),
    );

    if (response.statusCode == 200) {
      return Conversation.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to update conversation: ${response.statusCode}');
  }

  /// Delete a conversation permanently.
  Future<bool> delete(String id) async {
    final headers = await _authHeaders();
    final response = await http.delete(
      Uri.parse('$_baseUrl/$id'),
      headers: headers,
    );
    return response.statusCode == 204;
  }

  /// Get messages for a conversation (for infinite scrolling).
  Future<MessageListResponse> getMessages(
    String conversationId, {
    int limit = 100,
    int offset = 0,
    String? beforeId,
  }) async {
    final headers = await _authHeaders();
    final queryParams = <String, String>{
      'limit': limit.toString(),
      'offset': offset.toString(),
    };
    if (beforeId != null) queryParams['before_id'] = beforeId;

    final uri = Uri.parse('$_baseUrl/$conversationId/messages')
        .replace(queryParameters: queryParams);

    final response = await http.get(uri, headers: headers);
    if (response.statusCode == 200) {
      return MessageListResponse.fromJson(jsonDecode(response.body));
    }
    throw Exception('Failed to load messages: ${response.statusCode}');
  }

  /// Pin or unpin a conversation.
  Future<Conversation> togglePin(String id) async {
    // First get current state
    final conv = await get(id);
    return await update(id, isPinned: !conv.isPinned);
  }

  /// Favorite or unfavorite a conversation.
  Future<Conversation> toggleFavorite(String id) async {
    final conv = await get(id);
    return await update(id, isFavorited: !conv.isFavorited);
  }

  /// Archive a conversation.
  Future<Conversation> archive(String id) async {
    return await update(id, isArchived: true);
  }

  /// Rename a conversation.
  Future<Conversation> rename(String id, String title) async {
    return await update(id, title: title);
  }
}

// ──────────────────────────────────────────────
// Response models
// ──────────────────────────────────────────────

class ConversationListResponse {
  final List<Conversation> items;
  final int total;
  final bool hasMore;
  final String? nextCursor;

  const ConversationListResponse({
    required this.items,
    required this.total,
    required this.hasMore,
    this.nextCursor,
  });

  factory ConversationListResponse.fromJson(Map<String, dynamic> json) =>
      ConversationListResponse(
        items: (json['items'] as List)
            .map((e) => Conversation.fromJson(e))
            .toList(),
        total: json['total'] as int,
        hasMore: json['has_more'] as bool? ?? false,
        nextCursor: json['next_cursor'] as String?,
      );
}

class MessageListResponse {
  final List<ChatMessage> items;
  final int total;
  final bool hasMore;
  final String? nextCursor;

  const MessageListResponse({
    required this.items,
    required this.total,
    required this.hasMore,
    this.nextCursor,
  });

  factory MessageListResponse.fromJson(Map<String, dynamic> json) =>
      MessageListResponse(
        items: (json['items'] as List)
            .map((e) => ChatMessage.fromJson(e))
            .toList(),
        total: json['total'] as int,
        hasMore: json['has_more'] as bool? ?? false,
        nextCursor: json['next_cursor'] as String?,
      );
}

// ──────────────────────────────────────────────
// Riverpod provider
// ──────────────────────────────────────────────

final conversationRepositoryProvider = Provider<ConversationRepository>((ref) {
  return ConversationRepository(ref);
});