import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../models/plugin.dart';

class PluginService {
  static const _kInstalledKey = 'installed_plugins';
  static const _kEnabledKey = 'enabled_plugins';

  PluginService();

  Future<SharedPreferences> _prefs() => SharedPreferences.getInstance();

  Future<List<PluginModel>> getInstalledPlugins() async {
    final prefs = await _prefs();
    final raw = prefs.getStringList(_kInstalledKey) ?? [];
    return raw.map((j) {
      final map = jsonDecode(j) as Map<String, dynamic>;
      return _fromMap(map);
    }).toList();
  }

  Future<List<PluginModel>> getAvailablePlugins() async {
    await Future.delayed(const Duration(milliseconds: 300));
    return [];
  }

  Future<PluginModel> installPlugin(PluginModel plugin) async {
    final prefs = await _prefs();
    final existing = await getInstalledPlugins();
    final updated = <PluginModel>[
      plugin,
      ...existing.where((p) => p.id != plugin.id),
    ];
    final serialized = updated.map((p) => jsonEncode(_toMap(p))).toList();
    await prefs.setStringList(_kInstalledKey, serialized);
    final enabledList = prefs.getStringList(_kEnabledKey) ?? [];
    if (plugin.enabled && !enabledList.contains(plugin.id)) {
      enabledList.add(plugin.id);
      await prefs.setStringList(_kEnabledKey, enabledList);
    }
    return plugin;
  }

  Future<void> uninstallPlugin(String pluginId) async {
    final prefs = await _prefs();
    final existing = await getInstalledPlugins();
    final updated = existing.where((p) => p.id != pluginId).toList();
    final serialized = updated.map((p) => jsonEncode(_toMap(p))).toList();
    await prefs.setStringList(_kInstalledKey, serialized);
    final enabledList = prefs.getStringList(_kEnabledKey) ?? [];
    if (enabledList.contains(pluginId)) {
      enabledList.remove(pluginId);
      await prefs.setStringList(_kEnabledKey, enabledList);
    }
  }

  Future<PluginModel> togglePlugin(String pluginId, bool enable) async {
    final prefs = await _prefs();
    final existing = await getInstalledPlugins();
    final updated = existing.map((p) {
      return p.id == pluginId ? p.copyWith(enabled: enable) : p;
    }).toList();
    final serialized = updated.map((p) => jsonEncode(_toMap(p))).toList();
    await prefs.setStringList(_kInstalledKey, serialized);
    final enabledList = prefs.getStringList(_kEnabledKey) ?? [];
    if (enable) {
      if (!enabledList.contains(pluginId)) {
        enabledList.add(pluginId);
      }
    } else {
      enabledList.remove(pluginId);
    }
    await prefs.setStringList(_kEnabledKey, enabledList);
    return updated.firstWhere((p) => p.id == pluginId);
  }

  Map<String, dynamic> _toMap(PluginModel plugin) {
    return {
      'id': plugin.id,
      'name': plugin.name,
      'description': plugin.description,
      'version': plugin.version,
      'enabled': plugin.enabled,
      'iconCodePoint': plugin.icon.codePoint,
      'iconFontFamily': plugin.icon.fontPackage,
      'iconMatchTextDirection': plugin.icon.matchTextDirection,
      'permissions': plugin.permissions
          .map((p) => {
                'id': p.id,
                'name': p.name,
                'description': p.description,
                'isGranted': p.isGranted,
              })
          .toList(),
      if (plugin.author != null) 'author': plugin.author,
      if (plugin.installedAt != null)
        'installedAt': plugin.installedAt!.toIso8601String(),
    };
  }

  PluginModel _fromMap(Map<String, dynamic> map) {
    final iconCode = map['iconCodePoint'] as int? ?? Icons.add.codePoint;
    final fontFamily = map['iconFontFamily'] as String?;
    final matchDir = map['iconMatchTextDirection'] as bool? ?? false;
    final icon = IconData(iconCode, fontFamily: fontFamily, matchTextDirection: matchDir);

    final perms = (map['permissions'] as List?)
            ?.map((p) => PluginPermission(
                  id: p['id'] as String,
                  name: p['name'] as String,
                  description: p['description'] as String,
                  isGranted: p['isGranted'] as bool? ?? true,
                ))
            .toList() ??
        const <PluginPermission>[];

    return PluginModel(
      id: map['id'] as String,
      name: map['name'] as String,
      description: map['description'] as String,
      version: map['version'] as String,
      enabled: map['enabled'] as bool? ?? true,
      permissions: perms,
      icon: icon,
      author: map['author'] as String?,
      installedAt: map['installedAt'] != null
          ? DateTime.tryParse(map['installedAt'] as String)
          : null,
      status: PluginStatus.installed,
    );
  }
}

final pluginServiceProvider = Provider<PluginService>((ref) {
  return PluginService();
});
