import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/routing/app_routes.dart';
import './models/plugin.dart';
import './providers/plugins_provider.dart';

class PluginDetailsPage extends ConsumerStatefulWidget {
  final String pluginId;

  const PluginDetailsPage({
    super.key,
    required this.pluginId,
  });

  @override
  ConsumerState<PluginDetailsPage> createState() => _PluginDetailsPageState();
}

class _PluginDetailsPageState extends ConsumerState<PluginDetailsPage> {
  bool _isEnabled = true;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final plugin = ref.watch(pluginsProvider).plugins.firstWhere(
          (p) => p.id == widget.pluginId,
          orElse: () => _fallbackPlugin(widget.pluginId),
        );

    _isEnabled = plugin.enabled;

    return Scaffold(
      appBar: AppBar(
        title: Text(plugin.name),
        actions: [
          PopupMenuButton<String>(
            onSelected: (value) {
              if (value == 'uninstall') {
                _confirmUninstall(context, ref, plugin);
              }
            },
            itemBuilder: (ctx) => [
              const PopupMenuItem(
                value: 'uninstall',
                child: Row(
                  children: [
                    Icon(Icons.delete_outline, size: 18),
                    SizedBox(width: 12),
                    Text('Uninstall'),
                  ],
                ),
              ),
            ],
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
        children: [
          _buildHeader(plugin, theme, colorScheme),
          const SizedBox(height: 24),
          _buildSectionTitle('About', theme, colorScheme),
          const SizedBox(height: 8),
          _buildAboutCard(plugin, theme, colorScheme),
          const SizedBox(height: 24),
          _buildSectionTitle('Permissions', theme, colorScheme),
          const SizedBox(height: 8),
          _buildPermissionsCard(plugin, theme, colorScheme),
          const SizedBox(height: 24),
          _buildSectionTitle('Settings', theme, colorScheme),
          const SizedBox(height: 8),
          _buildSettingsCard(plugin, theme, colorScheme),
          const SizedBox(height: 32),
        ],
      ),
    );
  }

  Widget _buildHeader(PluginModel plugin, ThemeData theme, ColorScheme colorScheme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Row(
          children: [
            Container(
              padding: const EdgeInsets.all(12),
              decoration: BoxDecoration(
                color: _isEnabled ? colorScheme.primaryContainer.withValues(alpha: 0.4) : colorScheme.surfaceContainerHighest,
                borderRadius: BorderRadius.circular(14),
              ),
              child: Icon(plugin.icon, size: 28, color: _isEnabled ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.4)),
            ),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(plugin.name, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 2),
                  Text('v${plugin.version}', style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
                  if (plugin.author != null) ...[
                    const SizedBox(height: 2),
                    Text('by ${plugin.author}', style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                  ],
                ],
              ),
            ),
            Switch(
              value: _isEnabled,
              onChanged: (value) async {
                setState(() => _isEnabled = value);
                await ref.read(pluginsProvider.notifier).togglePlugin(plugin.id, value);
              },
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title, ThemeData theme, ColorScheme colorScheme) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w600,
        color: colorScheme.onSurface.withValues(alpha: 0.7),
      ),
    );
  }

  Widget _buildAboutCard(PluginModel plugin, ThemeData theme, ColorScheme colorScheme) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(plugin.description, style: theme.textTheme.bodyMedium?.copyWith(height: 1.5)),
            const SizedBox(height: 12),
            Row(
              children: [
                Icon(Icons.calendar_today_outlined, size: 16, color: colorScheme.onSurface.withValues(alpha: 0.5)),
                const SizedBox(width: 8),
                Text('Installed: ${plugin.installedAt != null ? '${plugin.installedAt!.day}/${plugin.installedAt!.month}/${plugin.installedAt!.year}' : 'Unknown'}', style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildPermissionsCard(PluginModel plugin, ThemeData theme, ColorScheme colorScheme) {
    if (plugin.permissions.isEmpty) {
      return Card(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Text('No permissions required', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
        ),
      );
    }

    return Card(
      child: Column(
        children: plugin.permissions.map((perm) {
          return SwitchListTile(
            secondary: Icon(perm.isGranted ? Icons.lock_open : Icons.lock, size: 20),
            title: Text(perm.name, style: theme.textTheme.bodyMedium),
            subtitle: Text(perm.description, style: theme.textTheme.bodySmall),
            value: perm.isGranted,
            onChanged: (v) {},
          );
        }).toList(),
      ),
    );
  }

  Widget _buildSettingsCard(PluginModel plugin, ThemeData theme, ColorScheme colorScheme) {
    return Card(
      child: Column(
        children: [
          SwitchListTile(
            secondary: const Icon(Icons.notifications_active_outlined, size: 20),
            title: const Text('Enable notifications'),
            subtitle: const Text('Show plugin notifications'),
            value: _isEnabled,
            onChanged: (v) {},
          ),
          const Divider(height: 1, indent: 56, endIndent: 16),
          SwitchListTile(
            secondary: Icon(_isEnabled ? Icons.auto_awesome : Icons.pause_circle_outline, size: 20),
            title: Text('Auto-start', style: theme.textTheme.bodyMedium),
            subtitle: const Text('Launch plugin on app start'),
            value: _isEnabled,
            onChanged: (v) {},
          ),
        ],
      ),
    );
  }

  Future<void> _confirmUninstall(BuildContext context, WidgetRef ref, PluginModel plugin) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('Uninstall ${plugin.name}?'),
        content: Text('Are you sure you want to uninstall ${plugin.name}?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Uninstall')),
        ],
      ),
    );

    if (confirmed == true && context.mounted) {
      await ref.read(pluginsProvider.notifier).uninstallPlugin(plugin.id);
      if (context.mounted) context.pop();
    }
  }
}

PluginModel _fallbackPlugin(String pluginId) {
  return PluginModel(
    id: pluginId,
    name: 'Unknown Plugin',
    description: 'Plugin not found',
    version: '0.0.0',
    icon: Icons.extension,
    enabled: false,
    status: PluginStatus.installed,
  );
}
