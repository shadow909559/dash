import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/automation.dart';
import '../services/automation_service.dart';

class AutomationHistoryState {
  const AutomationHistoryState({
    required this.items,
    this.isLoading = false,
    this.errorMessage,
  });

  final List<AutomationHistory> items;
  final bool isLoading;
  final String? errorMessage;

  AutomationHistoryState copyWith({
    List<AutomationHistory>? items,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
  }) {
    return AutomationHistoryState(
      items: items ?? this.items,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
    );
  }
}

class AutomationState {
  const AutomationState({
    required this.automations,
    this.isLoading = false,
    this.errorMessage,
    this.isExecuting = false,
    this.executingId,
  });

  final List<Automation> automations;
  final bool isLoading;
  final String? errorMessage;
  final bool isExecuting;
  final String? executingId;

  AutomationState copyWith({
    List<Automation>? automations,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    bool? isExecuting,
    String? executingId,
  }) {
    return AutomationState(
      automations: automations ?? this.automations,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      isExecuting: isExecuting ?? this.isExecuting,
      executingId: executingId ?? this.executingId,
    );
  }
}

class AutomationNotifier extends StateNotifier<AutomationState> {
  AutomationNotifier(this._service)
      : super(const AutomationState(automations: []));

  final AutomationService _service;

  Future<void> loadAutomations({bool refresh = false}) async {
    if (!refresh && state.automations.isNotEmpty) return;
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final items = await _service.listAutomations();
      final automations = items
          .map((e) => Automation.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(automations: automations, isLoading: false);
    } catch (e) {
      state = state.copyWith(
        isLoading: false,
        errorMessage: e.toString(),
      );
    }
  }

  Future<void> createAutomation({
    required String name,
    required String triggerType,
    required String toolName,
    List<dynamic>? toolArguments,
    bool enabled = true,
    String? description,
    Map<String, dynamic>? schedule,
  }) async {
    try {
      final data = await _service.createAutomation(
        name: name,
        triggerType: triggerType,
        toolName: toolName,
        toolArguments: toolArguments,
        enabled: enabled,
        description: description,
        schedule: schedule,
      );
      final automation = Automation.fromJson(data as Map<String, dynamic>);
      final updated = List<Automation>.from(state.automations);
      updated.add(automation);
      state = state.copyWith(automations: updated);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> updateAutomation(String id, Map<String, dynamic> updateData) async {
    try {
      final data = await _service.updateAutomation(id, updateData: updateData);
      final updatedAutomation =
          Automation.fromJson(data as Map<String, dynamic>);
      final updated = List<Automation>.from(state.automations);
      final idx = updated.indexWhere((a) => a.id == id);
      if (idx != -1) {
        updated[idx] = updatedAutomation;
        state = state.copyWith(automations: updated);
      }
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> deleteAutomation(String id) async {
    try {
      await _service.deleteAutomation(id);
      final updated = List<Automation>.from(state.automations);
      updated.removeWhere((a) => a.id == id);
      state = state.copyWith(automations: updated);
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> toggleAutomation(String id, bool enabled) async {
    try {
      await _service.toggleAutomation(id, enabled);
      final updated = List<Automation>.from(state.automations);
      final idx = updated.indexWhere((a) => a.id == id);
      if (idx != -1) {
        updated[idx] = updated[idx].copyWith(
          enabled: enabled,
          updatedAt: DateTime.now(),
        );
        state = state.copyWith(automations: updated);
      }
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
      rethrow;
    }
  }

  Future<void> executeAutomation(String id) async {
    state = state.copyWith(isExecuting: true, executingId: id, clearError: true);
    try {
      await _service.updateAutomation(
            id,
            updateData: {'execute': true},
          );
    } catch (e) {
      state = state.copyWith(
        isExecuting: false,
        executingId: null,
        errorMessage: e.toString(),
      );
      rethrow;
    }
    state = state.copyWith(isExecuting: false, executingId: null);
  }
}

final automationProvider =
    StateNotifierProvider<AutomationNotifier, AutomationState>((ref) {
  final service = ref.watch(automationServiceProvider);
  return AutomationNotifier(service);
});

final automationHistoryProvider =
    StateNotifierProvider.family<AutomationHistoryNotifier, AutomationHistoryState, String>(
  (ref, automationId) {
    final service = ref.watch(automationServiceProvider);
    return AutomationHistoryNotifier(service, automationId);
  },
);

class AutomationHistoryNotifier extends StateNotifier<AutomationHistoryState> {
  AutomationHistoryNotifier(this._service, this.automationId)
      : super(const AutomationHistoryState(items: []));

  final AutomationService _service;
  final String automationId;

  Future<void> loadHistory() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final items = await _service.getAutomationHistory(automationId);
      final history = items
          .map((e) => AutomationHistory.fromJson(e as Map<String, dynamic>))
          .toList();
      state = state.copyWith(items: history, isLoading: false);
    } catch (e) {
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }
}
