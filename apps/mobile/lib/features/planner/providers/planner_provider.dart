import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../planner/models/goal.dart';
import '../../tasks/models/task.dart';
import '../../planner/services/planner_service.dart';

class PlannerState {
  final List<Goal> goals;
  final List<Task> tasks;
  final bool isLoading;
  final String? errorMessage;
  final int activeGoalsCount;
  final int pendingTasksCount;
  final int completedTodayCount;

  const PlannerState({
    this.goals = const [],
    this.tasks = const [],
    this.isLoading = false,
    this.errorMessage,
    this.activeGoalsCount = 0,
    this.pendingTasksCount = 0,
    this.completedTodayCount = 0,
  });

  PlannerState copyWith({
    List<Goal>? goals,
    List<Task>? tasks,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    int? activeGoalsCount,
    int? pendingTasksCount,
    int? completedTodayCount,
  }) {
    return PlannerState(
      goals: goals ?? this.goals,
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
      activeGoalsCount: activeGoalsCount ?? this.activeGoalsCount,
      pendingTasksCount: pendingTasksCount ?? this.pendingTasksCount,
      completedTodayCount: completedTodayCount ?? this.completedTodayCount,
    );
  }
}

class PlannerNotifier extends StateNotifier<PlannerState> {
  PlannerNotifier(this._ref) : super(const PlannerState());

  final Ref _ref;
  GoalsService get _goalsService => _ref.read(goalsServiceProvider);

  Future<void> loadDashboard({bool refresh = false}) async {
    if (state.isLoading && !refresh) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final goalsData = await _goalsService.listGoals();
      final goals = goalsData.map((g) => Goal.fromJson(g as Map<String, dynamic>)).toList();
      final allTasks = <Task>[];
      for (final goal in goals) {
        try {
          final tasksData = await _goalsService.listTasks(goal.id);
          final tasks = tasksData.map((t) => Task.fromJson(t as Map<String, dynamic>)).toList();
          allTasks.addAll(tasks);
        } catch (_) {
          // skip goal if tasks fail
        }
      }
      final now = DateTime.now();
      final activeGoals = goals.where((g) => g.status == 'active').length;
      final pendingTasks = allTasks.where((t) => t.status == 'pending').length;
      final completedToday = allTasks.where((t) {
        final c = t.createdAt;
        return t.status == 'completed' &&
            c.year == now.year &&
            c.month == now.month &&
            c.day == now.day;
      }).length;
      state = state.copyWith(
        goals: goals,
        tasks: allTasks,
        isLoading: false,
        activeGoalsCount: activeGoals,
        pendingTasksCount: pendingTasks,
        completedTodayCount: completedToday,
      );
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

final plannerProvider = StateNotifierProvider<PlannerNotifier, PlannerState>((ref) {
  return PlannerNotifier(ref);
});
