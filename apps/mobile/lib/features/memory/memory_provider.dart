import 'dart:async';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import './models/memory_item.dart';
import './services/memory_service.dart';

class MemoryState {
  final List<MemoryItem> items;
  final bool isLoading;
  final bool isRefreshing;
  final String? errorMessage;
  final String? selectedCategory;
  final String searchQuery;
  final List<MemoryItem> filteredItems;

  const MemoryState({
    this.items = const [],
    this.isLoading = true,
    this.isRefreshing = false,
    this.errorMessage,
    this.selectedCategory,
    this.searchQuery = '',
    this.filteredItems = const [],
  });

  MemoryState copyWith({
    List<MemoryItem>? items,
    bool? isLoading,
    bool? isRefreshing,
    String? errorMessage,
    bool clearError = false,
    String? selectedCategory,
    String? searchQuery,
    List<MemoryItem>? filteredItems,
  }) {
    return MemoryState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      isRefreshing: isRefreshing ?? this.isRefreshing,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      selectedCategory: selectedCategory ?? this.selectedCategory,
      searchQuery: searchQuery ?? this.searchQuery,
      filteredItems: filteredItems ?? this.filteredItems,
    );
  }
}

class MemoryNotifier extends StateNotifier<MemoryState> {
  MemoryNotifier(this._memoryService) : super(const MemoryState()) {
    loadMemories();
  }

  final MemoryService _memoryService;
  Timer? _searchDebounce;

  List<MemoryItem> _computeFiltered(List<MemoryItem> items) {
    var result = items;
    if (state.selectedCategory != null && state.selectedCategory!.isNotEmpty) {
      result = result.where((m) => m.category == state.selectedCategory).toList();
    }
    final q = state.searchQuery.toLowerCase();
    if (q.isNotEmpty) {
      result = result.where(
        (m) =>
            m.content.toLowerCase().contains(q) ||
            m.category.toLowerCase().contains(q) ||
            (m.source ?? '').toLowerCase().contains(q),
      ).toList();
    }
    return result;
  }

  Future<void> loadMemories() async {
    state = state.copyWith(isLoading: true, errorMessage: null, clearError: true);
    try {
      final raw = await _memoryService.listMemories();
      final items = raw.map((json) => MemoryItem.fromJson(json as Map<String, dynamic>)).toList();
      final filtered = _computeFiltered(items);
      state = state.copyWith(items: items, isLoading: false, filteredItems: filtered);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> refreshMemories() async {
    state = state.copyWith(isRefreshing: true, errorMessage: null, clearError: true);
    try {
      final raw = await _memoryService.listMemories();
      final items = raw.map((json) => MemoryItem.fromJson(json as Map<String, dynamic>)).toList();
      final filtered = _computeFiltered(items);
      state = state.copyWith(
        isRefreshing: false,
        items: items,
        filteredItems: filtered,
      );
    } catch (e) {
      state = state.copyWith(isRefreshing: false, errorMessage: e.toString());
    }
  }

  Future<void> createMemory({
    required String content,
    String? category,
    String? source,
    int importance = 1,
  }) async {
    state = state.copyWith(errorMessage: null, clearError: true);
    try {
      final json = await _memoryService.createMemory(
        content: content,
        category: category,
        source: source,
        importance: importance,
      );
      final item = MemoryItem.fromJson(json as Map<String, dynamic>);
      final newItems = [item, ...state.items];
      final filtered = _computeFiltered(newItems);
      state = state.copyWith(items: newItems, filteredItems: filtered);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> updateMemory(
    String id, {
    String? content,
    String? category,
    String? source,
    int? importance,
  }) async {
    state = state.copyWith(errorMessage: null, clearError: true);
    try {
      final json = await _memoryService.updateMemory(
        id,
        content: content,
        category: category,
        source: source,
        importance: importance,
      );
      final updated = MemoryItem.fromJson(json as Map<String, dynamic>);
      final newItems = state.items.map((m) => m.id == id ? updated : m).toList();
      final filtered = _computeFiltered(newItems);
      state = state.copyWith(items: newItems, filteredItems: filtered);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> deleteMemory(String id) async {
    state = state.copyWith(errorMessage: null, clearError: true);
    try {
      await _memoryService.deleteMemory(id);
      final newItems = state.items.where((m) => m.id != id).toList();
      final filtered = _computeFiltered(newItems);
      state = state.copyWith(items: newItems, filteredItems: filtered);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  void setSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      final filtered = _computeFiltered(state.items);
      state = state.copyWith(filteredItems: filtered);
    });
  }

  void setSelectedCategory(String? category) {
    state = state.copyWith(selectedCategory: category);
    final filtered = _computeFiltered(state.items);
    state = state.copyWith(filteredItems: filtered);
  }

  @override
  void dispose() {
    _searchDebounce?.cancel();
    super.dispose();
  }
}

final memoryProvider = StateNotifierProvider<MemoryNotifier, MemoryState>((ref) {
  return MemoryNotifier(ref.read(memoryServiceProvider));
});
