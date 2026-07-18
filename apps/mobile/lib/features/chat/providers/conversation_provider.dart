import 'dart:async';

import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/conversation.dart';
import '../services/conversation_repository.dart';

/// State for the conversation list sidebar.
class ConversationListState {
  final List<Conversation> conversations;
  final bool isLoading;
  final String? errorMessage;
  final String? searchQuery;
  final List<Conversation> searchResults;
  final bool isSearching;

  const ConversationListState({
    this.conversations = const [],
    this.isLoading = false,
    this.errorMessage,
    this.searchQuery,
    this.searchResults = const [],
    this.isSearching = false,
  });

  ConversationListState copyWith({
    List<Conversation>? conversations,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    String? searchQuery,
    List<Conversation>? searchResults,
    bool? isSearching,
  }) {
    return ConversationListState(
      conversations: conversations ?? this.conversations,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      searchQuery: searchQuery ?? this.searchQuery,
      searchResults: searchResults ?? this.searchResults,
      isSearching: isSearching ?? this.isSearching,
    );
  }

  List<Conversation> get pinnedConversations =>
      conversations.where((c) => c.isPinned).toList();

  List<Conversation> get activeConversations =>
      conversations.where((c) => !c.isPinned).toList();
}

class ConversationListNotifier extends StateNotifier<ConversationListState> {
  final ConversationRepository _repository;

  ConversationListNotifier(this._repository)
      : super(const ConversationListState()) {
    load();
  }

  Timer? _searchDebounce;

  /// Load conversations from the API.
  Future<void> load({bool includeArchived = false}) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final response = await _repository.list(
        includeArchived: includeArchived,
      );
      state = state.copyWith(
        conversations: response.items,
        isLoading: false,
      );
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  /// Create a new conversation.
  Future<Conversation?> create({String? title}) async {
    try {
      final conversation = await _repository.create(title: title);
      state = state.copyWith(
        conversations: [conversation, ...state.conversations],
      );
      return conversation;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return null;
    }
  }

  /// Delete a conversation.
  Future<bool> delete(String id) async {
    try {
      final success = await _repository.delete(id);
      if (success) {
        state = state.copyWith(
          conversations: state.conversations.where((c) => c.id != id).toList(),
        );
      }
      return success;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return false;
    }
  }

  /// Rename a conversation.
  Future<Conversation?> rename(String id, String title) async {
    try {
      final updated = await _repository.rename(id, title);
      _updateConversation(updated);
      return updated;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return null;
    }
  }

  /// Toggle pin status.
  Future<Conversation?> togglePin(String id) async {
    try {
      final updated = await _repository.togglePin(id);
      _updateConversation(updated);
      return updated;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return null;
    }
  }

  /// Toggle favorite status.
  Future<Conversation?> toggleFavorite(String id) async {
    try {
      final updated = await _repository.toggleFavorite(id);
      _updateConversation(updated);
      return updated;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return null;
    }
  }

  /// Archive a conversation.
  Future<Conversation?> archive(String id) async {
    try {
      final updated = await _repository.archive(id);
      state = state.copyWith(
        conversations: state.conversations.where((c) => c.id != id).toList(),
      );
      return updated;
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      return null;
    }
  }

  /// Search conversations with debounce.
  void search(String query) {
    if (query.isEmpty) {
      state = state.copyWith(
        searchQuery: null,
        searchResults: [],
        isSearching: false,
      );
      return;
    }

    state = state.copyWith(searchQuery: query, isSearching: true);

    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () async {
      try {
        final results = await _repository.search(query);
        state = state.copyWith(
          searchResults: results,
          isSearching: false,
        );
      } catch (e) {
        state = state.copyWith(
          isSearching: false,
          errorMessage: e.toString(),
        );
      }
    });
  }

  /// Update a single conversation in the list.
  void _updateConversation(Conversation updated) {
    final conversations = state.conversations.map((c) {
      return c.id == updated.id ? updated : c;
    }).toList();
    state = state.copyWith(conversations: conversations);
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    super.dispose();
  }
}

final conversationListProvider =
    StateNotifierProvider<ConversationListNotifier, ConversationListState>(
  (ref) => ConversationListNotifier(
    ref.read(conversationRepositoryProvider),
  ),
);

/// Provider for the currently active conversation ID.
final activeConversationIdProvider = StateProvider<String?>((ref) => null);