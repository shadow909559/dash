import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../tasks/models/task.dart';
import '../../planner/models/goal.dart';
import '../../planner/services/planner_service.dart';
import '../../tasks/services/task_service.dart';

class TasksState {
  final List<Task> tasks;
  final bool isLoading;
  final String? errorMessage;
  final String? filterGoalId;

  const TasksState({
    this.tasks = const [],
    this.isLoading = false,
    this.errorMessage,
    this.filterGoalId,
  });

  TasksState copyWith({
    List<Task>? tasks,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    String? filterGoalId,
  }) {
    return TasksState(
      tasks: tasks ?? this.tasks,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : errorMessage ?? this.errorMessage,
      filterGoalId: filterGoalId ?? this.filterGoalId,
    );
  }

  List<Task> get filteredTasks {
    if (filterGoalId != null && filterGoalId!.isNotEmpty) {
      return tasks.where((t) => t.goalId == filterGoalId).toList();
    }
    return tasks;
  }
}

class TasksNotifier extends StateNotifier<TasksState> {
  TasksNotifier(this._ref) : super(const TasksState());

  final Ref _ref;
  GoalsService get _plannerService => _ref.read(goalsServiceProvider);
  TaskService get _taskService => _ref.read(taskServiceProvider);

  Future<void> loadTasks({bool refresh = false}) async {
    if (state.isLoading && !refresh) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final allGoalsData = await _plannerService.listGoals();
      final goals = allGoalsData.map((g) => Goal.fromJson(g as Map<String, dynamic>)).toList();
      final allTasks = <Task>[];
      for (final goal in goals) {
        try {
          final tasksData = await _plannerService.listTasks(goal.id);
          final tasks = tasksData.map((t) => Task.fromJson(t as Map<String, dynamic>)).toList();
          allTasks.addAll(tasks);
        } catch (_) {
          // skip goal if tasks fail
        }
      }
      state = state.copyWith(tasks: allTasks, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> loadTasksForGoal(String goalId) async {
    state = state.copyWith(isLoading: true, clearError: true, filterGoalId: goalId);
    try {
      final data = await _plannerService.listTasks(goalId);
      final tasks = data.map((t) => Task.fromJson(t as Map<String, dynamic>)).toList();
      final existing = [...state.tasks];
      existing.removeWhere((t) => t.goalId == goalId);
      existing.addAll(tasks);
      state = state.copyWith(tasks: existing, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<Task> createTask(String? goalId, {required String name, String? description}) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final data = await _taskService.createTask(goalId, name: name, description: description);
      final task = Task.fromJson(data as Map<String, dynamic>);
      final tasks = [...state.tasks, task];
      state = state.copyWith(tasks: tasks, isLoading: false);
      return task;
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> completeTask(String id) async {
    final tasks = state.tasks.map((t) => t.id == id ? t.copyWith(status: 'completed') : t).toList();
    state = state.copyWith(tasks: tasks, clearError: true);
  }

  Future<void> deleteTask(String id) async {
    final tasks = state.tasks.where((t) => t.id != id).toList();
    state = state.copyWith(tasks: tasks, clearError: true);
    await loadTasks(refresh: true);
  }

  void setFilterGoalId(String? goalId) {
    state = state.copyWith(filterGoalId: goalId);
  }

  void clearError() {
    state = state.copyWith(clearError: true);
  }
}

final tasksProvider = StateNotifierProvider<TasksNotifier, TasksState>((ref) {
  return TasksNotifier(ref);
});
