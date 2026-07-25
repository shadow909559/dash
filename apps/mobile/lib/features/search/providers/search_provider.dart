import 'dart:async';
import 'package:flutter/foundation.dart';
import 'package:flutter/widgets.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../chat/services/conversation_repository.dart';
import '../../memory/services/memory_service.dart';
import '../../tasks/services/task_service.dart';

class SearchResultItem {
  final String id;
  final String title;
  final String snippet;
  final String category;
  final Map<String, dynamic>? raw;
  final double relevance;

  const SearchResultItem({
    required this.id,
    required this.title,
    required this.snippet,
    required this.category,
    this.raw,
    this.relevance = 1.0,
  });
}

class SearchState {
  final String query;
  final List<SearchResultItem> results;
  final bool isLoading;
  final String? errorMessage;
  final bool isSearching;
  final List<String> recentSearches;
  final SearchTab selectedTab;
  final Map<SearchTab, List<SearchResultItem>> tabResults;

  const SearchState({
    this.query = '',
    this.results = const [],
    this.isLoading = false,
    this.errorMessage,
    this.isSearching = false,
    this.recentSearches = const [],
    this.selectedTab = SearchTab.all,
    this.tabResults = const {},
  });

  SearchState copyWith({
    String? query,
    List<SearchResultItem>? results,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isSearching,
    List<String>? recentSearches,
    SearchTab? selectedTab,
    Map<SearchTab, List<SearchResultItem>>? tabResults,
  }) {
    return SearchState(
      query: query ?? this.query,
      results: results ?? this.results,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isSearching: isSearching ?? this.isSearching,
      recentSearches: recentSearches ?? this.recentSearches,
      selectedTab: selectedTab ?? this.selectedTab,
      tabResults: tabResults ?? this.tabResults,
    );
  }

  List<SearchResultItem> get filteredResults {
    final tab = selectedTab;
    if (tab == SearchTab.all) return results;
    final raw = tabResults[tab];
    if (raw == null) return const [];
    final q = query.toLowerCase();
    if (q.isEmpty) return raw;
    return raw.where((item) {
      final match = item.title.toLowerCase().contains(q) ||
          item.snippet.toLowerCase().contains(q);
      if (tab == SearchTab.all) return match;
      return match && _matchesCategory(item, tab);
    }).toList();
  }

  bool _matchesCategory(SearchResultItem item, SearchTab tab) {
    switch (tab) {
      case SearchTab.chats:
        return item.category == 'conversation';
      case SearchTab.memory:
        return item.category == 'memory';
      case SearchTab.tasks:
        return item.category == 'task';
      case SearchTab.files:
        return item.category == 'file';
      case SearchTab.all:
        return true;
    }
  }

  List<SearchResultItem> get categoryResults {
    return tabResults[selectedTab] ?? const [];
  }
}

enum SearchTab { all, chats, memory, tasks, files }

class SearchNotifier extends StateNotifier<SearchState> {
  final ConversationRepository _conversationRepository;
  final MemoryService _memoryService;
  final TaskService _taskService;
  Timer? _debounce;

  static const _kRecentKey = 'search_recent';

  SearchNotifier(this._conversationRepository, this._memoryService, this._taskService)
      : super(const SearchState()) {
    _loadRecent();
  }

  Future<void> _loadRecent() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      final recent = prefs.getStringList(_kRecentKey) ?? [];
      state = state.copyWith(recentSearches: recent);
    } catch (e) {
      debugPrint('Failed to load recent searches: $e');
    }
  }

  Future<void> _saveRecent(List<String> recentSearches) async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setStringList(_kRecentKey, recentSearches);
    } catch (e) {
      debugPrint('Failed to save recent searches: $e');
    }
  }

  Future<void> _addToRecent(String query) async {
    if (query.trim().isEmpty) return;
    final trimmed = query.trim();
    final recent = List<String>.from(state.recentSearches);
    recent.remove(trimmed);
    recent.insert(0, trimmed);
    if (recent.length > 10) recent.removeRange(10, recent.length);
    state = state.copyWith(recentSearches: recent);
    await _saveRecent(recent);
  }

  Future<void> clearRecentSearches() async {
    state = state.copyWith(recentSearches: []);
    await _saveRecent(const <String>[]);
  }

  void selectTab(SearchTab tab) {
    state = state.copyWith(selectedTab: tab);
  }

  void setQuery(String query) {
    if (query == state.query) return;
    _debounce?.cancel();
    if (query.isEmpty) {
      state = state.copyWith(query: query, results: const [], tabResults: const {}, isSearching: false);
      return;
    }

    state = state.copyWith(query: query, isSearching: true);

    _debounce = Timer(const Duration(milliseconds: 350), () {
      _performSearch(query);
    });
  }

  Future<void> _performSearch(String query) async {
    state = state.copyWith(
      query: query,
      isSearching: true,
      isLoading: true,
      clearError: true,
    );

    try {
      final lowerQuery = query.toLowerCase();
      final tabResults = <SearchTab, List<SearchResultItem>>{
        SearchTab.chats: const [],
        SearchTab.memory: const [],
        SearchTab.tasks: const [],
        SearchTab.files: const [],
      };

      List<SearchResultItem> chatResults = const [];
      try {
        final conversations = await _conversationRepository.search(query);
        chatResults = conversations.map((conv) {
          return SearchResultItem(
            id: conv.id,
            title: conv.title ?? 'Untitled conversation',
            snippet: 'Last updated: ${_formatDate(conv.updatedAt)}',
            category: 'conversation',
            relevance: _relevance(conv.title ?? '', query),
          );
        }).toList();
      } catch (e) {
        debugPrint('Conversation search failed: $e');
      }

      List<SearchResultItem> memoryResults = const [];
      try {
        final memories = await _memoryService.listMemories(limit: 50, offset: 0);
        final filtered = _filterMemories(memories, lowerQuery);
        memoryResults = filtered.map((m) {
          final content = m['content'] as String? ?? '';
          return SearchResultItem(
            id: m['id'] as String? ?? Object().hashCode.toString(),
            title: content.length > 40 ? '${content.substring(0, 40)}...' : content,
            snippet: content,
            category: 'memory',
            raw: m,
            relevance: _relevance(content, query),
          );
        }).toList();
      } catch (e) {
        debugPrint('Memory search failed: $e');
      }

      List<SearchResultItem> taskResults = const [];
      try {
        final tasks = await _taskService.listTasks(null);
        final taskList = tasks is List ? tasks : (tasks is Map ? ((tasks as Map)['items'] ?? <dynamic>[]) : <dynamic>[]);
        taskResults = (taskList as List).map((t) {
          final taskName = (t is Map) ? (t['name'] as String? ?? t['title'] as String? ?? 'Task') : 'Task';
          final taskDesc = (t is Map) ? (t['description'] as String? ?? '') : '';
          final taskId = (t is Map) ? (t['id'] as String? ?? Object().hashCode.toString()) : Object().hashCode.toString();
          return SearchResultItem(
            id: taskId,
            title: taskName,
            snippet: taskDesc,
            category: 'task',
            raw: null,
            relevance: _relevance('$taskName $taskDesc', query),
          );
        }).toList();
      } catch (e) {
        debugPrint('Task search failed: $e');
      }

      tabResults[SearchTab.chats] = chatResults;
      tabResults[SearchTab.memory] = memoryResults;
      tabResults[SearchTab.tasks] = taskResults;

      final all = <SearchResultItem>[...chatResults, ...memoryResults, ...taskResults];
      all.sort((a, b) => b.relevance.compareTo(a.relevance));

      state = state.copyWith(
        results: all,
        tabResults: tabResults,
        isSearching: false,
        isLoading: false,
      );

      await _addToRecent(query);
    } catch (e, st) {
      debugPrint('Search failed: $e\n$st');
      state = state.copyWith(
        isSearching: false,
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  List<Map<String, dynamic>> _filterMemories(List<dynamic> memories, String query) {
    final result = <Map<String, dynamic>>[];
    for (final m in memories) {
      if (m is Map<String, dynamic>) {
        final content = (m['content'] as String? ?? '').toLowerCase();
        final category = (m['category'] as String? ?? '').toLowerCase();
        if (content.contains(query) || category.contains(query)) {
          result.add(m);
        }
      }
    }
    return result;
  }

  double _relevance(String field, String query) {
    if (field.toLowerCase().startsWith(query)) return 1.0;
    if (field.toLowerCase().contains(query)) return 0.8;
    final words = query.toLowerCase().split(' ');
    int matchCount = 0;
    for (final w in words) {
      if (w.isEmpty) continue;
      if (field.toLowerCase().contains(w)) matchCount++;
    }
    if (words.isEmpty) return 0.0;
    return 0.1 + 0.7 * (matchCount / words.length);
  }

  String _formatDate(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.month}/${dt.day}/${dt.year}';
  }

  @override
  void dispose() {
    _debounce?.cancel();
    super.dispose();
  }
}

final searchProvider = StateNotifierProvider<SearchNotifier, SearchState>((ref) {
  final conversationRepository = ref.watch(conversationRepositoryProvider);
  final memoryService = ref.watch(memoryServiceProvider);
  final taskService = ref.watch(taskServiceProvider);
  return SearchNotifier(conversationRepository, memoryService, taskService);
});

