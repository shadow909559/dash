import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../planner/models/goal.dart';
import '../../planner/services/planner_service.dart';

class GoalsState {
  final List<Goal> goals;
  final bool isLoading;
  final String? errorMessage;
  final String searchQuery;
  final String? statusFilter;

  const GoalsState({
    this.goals = const [],
    this.isLoading = false,
    this.errorMessage,
    this.searchQuery = '',
    this.statusFilter,
  });

  GoalsState copyWith({
    List<Goal>? goals,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    String? searchQuery,
    String? statusFilter,
  }) {
    return GoalsState(
      goals: goals ?? this.goals,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
      searchQuery: searchQuery ?? this.searchQuery,
      statusFilter: statusFilter ?? this.statusFilter,
    );
  }

  List<Goal> get filteredGoals {
    var result = goals;
    if (searchQuery.isNotEmpty) {
      final q = searchQuery.toLowerCase();
      result = result.where((g) => g.name.toLowerCase().contains(q) || (g.description?.toLowerCase().contains(q) ?? false)).toList();
    }
    if (statusFilter != null && statusFilter!.isNotEmpty) {
      result = result.where((g) => g.status == statusFilter).toList();
    }
    return result;
  }
}

class GoalsNotifier extends StateNotifier<GoalsState> {
  GoalsNotifier(this._ref) : super(const GoalsState());

  final Ref _ref;
  GoalsService get _goalsService => _ref.read(goalsServiceProvider);

  Future<void> loadGoals({bool refresh = false}) async {
    if (state.isLoading && !refresh) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await _goalsService.listGoals();
      final goals = data.map((g) => Goal.fromJson(g as Map<String, dynamic>)).toList();
      state = state.copyWith(goals: goals, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> createGoal({required String name, String? description}) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await _goalsService.createGoal(name: name, description: description);
      final goal = Goal.fromJson(data as Map<String, dynamic>);
      final goals = [...state.goals, goal];
      state = state.copyWith(goals: goals, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> deleteGoal(String id) async {
    final goals = state.goals.where((g) => g.id != id).toList();
    state = state.copyWith(goals: goals, clearError: true);
    await _goalsService.getGoal(id);
    state = state.copyWith(errorMessage: 'Delete not implemented by backend', clearError: false);
    await loadGoals(refresh: true);
  }

  void setSearchQuery(String query) {
    state = state.copyWith(searchQuery: query);
  }

  void setStatusFilter(String? status) {
    state = state.copyWith(statusFilter: status);
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

final goalsProvider = StateNotifierProvider<GoalsNotifier, GoalsState>((ref) {
  return GoalsNotifier(ref);
});
