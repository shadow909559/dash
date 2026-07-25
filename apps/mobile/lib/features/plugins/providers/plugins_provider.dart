import 'package:flutter/foundation.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/plugin.dart';
import '../services/plugin_service.dart';

class PluginState {
  final List<PluginModel> plugins;
  final bool isLoading;
  final String? errorMessage;
  final List<PluginModel> availablePlugins;

  const PluginState({
    this.plugins = const [],
    this.isLoading = false,
    this.errorMessage,
    this.availablePlugins = const [],
  });

  PluginState copyWith({
    List<PluginModel>? plugins,
    bool? isLoading,
    String? errorMessage,
    bool clearError = false,
    List<PluginModel>? availablePlugins,
  }) {
    return PluginState(
      plugins: plugins ?? this.plugins,
      isLoading: isLoading ?? this.isLoading,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      availablePlugins: availablePlugins ?? this.availablePlugins,
    );
  }
}

class PluginsNotifier extends StateNotifier<PluginState> {
  final PluginService _pluginService;

  PluginsNotifier(this._pluginService)
      : super(const PluginState()) {
    loadPlugins();
    loadAvailablePlugins();
  }

  Future<void> loadPlugins() async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final plugins = await _pluginService.getInstalledPlugins();
      state = state.copyWith(plugins: plugins, isLoading: false);
    } catch (e, st) {
      debugPrint('Failed to load plugins: $e\n$st');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> loadAvailablePlugins() async {
    try {
      final available = await _pluginService.getAvailablePlugins();
      state = state.copyWith(availablePlugins: available);
    } catch (e) {
      debugPrint('Failed to load available plugins: $e');
    }
  }

  Future<void> installPlugin(PluginModel plugin) async {
    state = state.copyWith(isLoading: true, clearError: true);
    try {
      final installed = await _pluginService.installPlugin(plugin);
      state = state.copyWith(
        plugins: [installed, ...state.plugins],
        isLoading: false,
      );
    } catch (e, st) {
      debugPrint('Failed to install plugin: $e\n$st');
      state = state.copyWith(isLoading: false, errorMessage: e.toString());
    }
  }

  Future<void> uninstallPlugin(String pluginId) async {
    try {
      await _pluginService.uninstallPlugin(pluginId);
      state = state.copyWith(
        plugins: state.plugins.where((p) => p.id != pluginId).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }

  Future<void> togglePlugin(String pluginId, bool enable) async {
    try {
      final updated = await _pluginService.togglePlugin(pluginId, enable);
      state = state.copyWith(
        plugins: state.plugins.map((p) {
          return p.id == pluginId ? updated : p;
        }).toList(),
      );
    } catch (e) {
      state = state.copyWith(errorMessage: e.toString());
    }
  }
}

final pluginsProvider = StateNotifierProvider<PluginsNotifier, PluginState>((ref) {
  final pluginService = ref.watch(pluginServiceProvider);
  return PluginsNotifier(pluginService);
});
