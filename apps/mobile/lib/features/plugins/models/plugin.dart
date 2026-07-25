library;

import 'package:flutter/material.dart';

enum PluginStatus { installed, notInstalled, updateAvailable }

class PluginModel {
  final String id;
  final String name;
  final String description;
  final String version;
  final bool enabled;
  final List<PluginPermission> permissions;
  final IconData icon;
  final String? author;
  final DateTime? installedAt;
  final PluginStatus status;

  const PluginModel({
    required this.id,
    required this.name,
    required this.description,
    required this.version,
    this.enabled = true,
    this.permissions = const [],
    required this.icon,
    this.author,
    this.installedAt,
    this.status = PluginStatus.installed,
  });

  PluginModel copyWith({
    bool? enabled,
    PluginStatus? status,
  }) {
    return PluginModel(
      id: id,
      name: name,
      description: description,
      version: version,
      enabled: enabled ?? this.enabled,
      permissions: permissions,
      icon: icon,
      author: author,
      installedAt: installedAt,
      status: status ?? this.status,
    );
  }
}

class PluginPermission {
  final String id;
  final String name;
  final String description;
  final bool isGranted;

  const PluginPermission({
    required this.id,
    required this.name,
    required this.description,
    this.isGranted = true,
  });

  PluginPermission copyWith({bool? isGranted}) {
    return PluginPermission(
      id: id,
      name: name,
      description: description,
      isGranted: isGranted ?? this.isGranted,
    );
  }
}
