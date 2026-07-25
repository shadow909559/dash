import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../../core/routing/app_routes.dart';
import './models/plugin.dart';
import './providers/plugins_provider.dart';

class PluginsPage extends ConsumerWidget {
  const PluginsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final state = ref.watch(pluginsProvider);
    final notifier = ref.read(pluginsProvider.notifier);

    final plugins = state.plugins.where((p) => p.status == PluginStatus.installed).toList();

    return Scaffold(
      appBar: AppBar(
        title: const Text('Plugins'),
        actions: [
          if (plugins.isNotEmpty)
            IconButton(
              onPressed: () {
                notifier.loadPlugins();
              },
              icon: const Icon(Icons.refresh_outlined),
              tooltip: 'Refresh',
            ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: notifier.loadPlugins,
        child: _buildBody(context, ref, state, plugins, theme, colorScheme),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _showInstallDialog(context, ref, theme, colorScheme),
        icon: Icon(Icons.add, color: colorScheme.onPrimaryContainer),
        label: Text('Install', style: TextStyle(color: colorScheme.onPrimaryContainer)),
      ),
    );
  }

  Widget _buildBody(
    BuildContext context,
    WidgetRef ref,
    PluginState state,
    List<PluginModel> plugins,
    ThemeData theme,
    ColorScheme colorScheme,
  ) {
    if (state.isLoading && plugins.isEmpty) {
      return _buildLoadingSkeleton(theme);
    }

    if (plugins.isEmpty) {
      return _buildEmptyState(theme, colorScheme);
    }

    return ListView.separated(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      itemCount: plugins.length,
      separatorBuilder: (_, __) => const SizedBox(height: 12),
      itemBuilder: (context, index) {
        final plugin = plugins[index];
        return _PluginCard(
          plugin: plugin,
          onTap: () => context.push('${AppRoutes.plugins}/${plugin.id}'),
          onToggle: (enable) => ref.read(pluginsProvider.notifier).togglePlugin(plugin.id, enable),
        );
      },
    );
  }

  Widget _buildLoadingSkeleton(ThemeData theme) {
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: 6,
      itemBuilder: (_, __) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Row(
              children: [
                Container(width: 40, height: 40, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(10))),
                const SizedBox(width: 16),
                Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
                  Container(height: 14, width: 120, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                  const SizedBox(height: 8),
                  Container(height: 10, width: 200, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                ])),
              ],
            ),
          ),
        ),
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme, ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(20),
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.extension_off_rounded, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text('No plugins installed', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Install plugins to extend DASH capabilities', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  void _showInstallDialog(BuildContext context, WidgetRef ref, ThemeData theme, ColorScheme colorScheme) {
    showModalBottomSheet(
      context: context,
      showDragHandle: true,
      builder: (ctx) {
        return DraggableScrollableSheet(
          initialChildSize: 0.6,
          minChildSize: 0.3,
          maxChildSize: 0.95,
          expand: false,
          builder: (context, scrollController) {
            return Column(
              children: [
                Padding(
                  padding: const EdgeInsets.fromLTRB(20, 12, 20, 8),
                  child: Row(
                    children: [
                      Text('Install Plugin', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
                      const Spacer(),
                      IconButton(onPressed: () => Navigator.pop(ctx), icon: const Icon(Icons.close)),
                    ],
                  ),
                ),
                const Divider(height: 1),
                Expanded(
                  child: ListView(
                    controller: scrollController,
                    padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                    children: [
                      _InstallTile(
                        name: 'Code Interpreter',
                        description: 'Execute Python code and visualize data',
                        icon: Icons.code,
                        color: Colors.blue,
                        onInstall: () {
                          _installDemoPlugin(ref, 'code-interpreter', 'Code Interpreter', '1.2.0', Icons.code, Colors.blue);
                          Navigator.pop(ctx);
                        },
                      ),
                      _InstallTile(
                        name: 'Web Scraper',
                        description: 'Extract data from websites automatically',
                        icon: Icons.public,
                        color: Colors.green,
                        onInstall: () {
                          _installDemoPlugin(ref, 'web-scraper', 'Web Scraper', '0.9.5', Icons.public, Colors.green);
                          Navigator.pop(ctx);
                        },
                      ),
                      _InstallTile(
                        name: 'Image Generation',
                        description: 'Generate images from text prompts',
                        icon: Icons.image,
                        color: Colors.purple,
                        onInstall: () {
                          _installDemoPlugin(ref, 'image-gen', 'Image Generation', '2.1.0', Icons.image, Colors.purple);
                          Navigator.pop(ctx);
                        },
                      ),
                      _InstallTile(
                        name: 'Data Connector',
                        description: 'Connect to databases and APIs',
                        icon: Icons.storage,
                        color: Colors.teal,
                        onInstall: () {
                          _installDemoPlugin(ref, 'data-connector', 'Data Connector', '1.0.3', Icons.storage, Colors.teal);
                          Navigator.pop(ctx);
                        },
                      ),
                      _InstallTile(
                        name: 'Audio Transcriber',
                        description: 'Transcribe and translate audio files',
                        icon: Icons.record_voice_over,
                        color: Colors.orange,
                        onInstall: () {
                          _installDemoPlugin(ref, 'audio-transcriber', 'Audio Transcriber', '0.5.0', Icons.record_voice_over, Colors.orange);
                          Navigator.pop(ctx);
                        },
                      ),
                    ],
                  ),
                ),
              ],
            );
          },
        );
      },
    );
  }

  Future<void> _installDemoPlugin(
    WidgetRef ref,
    String id,
    String name,
    String version,
    IconData icon,
    Color color,
  ) async {
    final plugin = PluginModel(
      id: id,
      name: name,
      description: '$name plugin for DASH',
      version: version,
      enabled: true,
      icon: icon,
      permissions: const [
        PluginPermission(id: 'p1', name: 'Network access', description: 'Access to network resources'),
        PluginPermission(id: 'p2', name: 'File system', description: 'Read and write files'),
      ],
    );
    await ref.read(pluginsProvider.notifier).installPlugin(plugin);
  }
}

class _PluginCard extends StatelessWidget {
  final PluginModel plugin;
  final VoidCallback onTap;
  final ValueChanged<bool> onToggle;

  const _PluginCard({
    required this.plugin,
    required this.onTap,
    required this.onToggle,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(10),
                decoration: BoxDecoration(
                  color: plugin.enabled ? colorScheme.primaryContainer.withValues(alpha: 0.4) : colorScheme.surfaceContainerHighest,
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(plugin.icon, color: plugin.enabled ? colorScheme.primary : colorScheme.onSurface.withValues(alpha: 0.4), size: 22),
              ),
              const SizedBox(width: 14),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(plugin.name, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 2),
                    Text(plugin.description, maxLines: 1, overflow: TextOverflow.ellipsis, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.7))),
                    const SizedBox(height: 6),
                    Row(
                      children: [
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                          decoration: BoxDecoration(
                            color: colorScheme.surfaceContainerHighest,
                            borderRadius: BorderRadius.circular(8),
                          ),
                          child: Text(plugin.version, style: theme.textTheme.labelSmall),
                        ),
                        const SizedBox(width: 8),
                        Text('${plugin.permissions.length} permissions', style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                      ],
                    ),
                  ],
                ),
              ),
              Switch(
                value: plugin.enabled,
                onChanged: plugin.status == PluginStatus.installed ? onToggle : null,
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _InstallTile extends StatelessWidget {
  final String name;
  final String description;
  final IconData icon;
  final Color color;
  final VoidCallback onInstall;

  const _InstallTile({
    required this.name,
    required this.description,
    required this.icon,
    required this.color,
    required this.onInstall,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      child: ListTile(
        contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        leading: Container(
          width: 40,
          height: 40,
          decoration: BoxDecoration(
            color: color.withValues(alpha: 0.1),
            borderRadius: BorderRadius.circular(10),
          ),
          child: Icon(icon, color: color, size: 22),
        ),
        title: Text(name, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
        subtitle: Text(description, maxLines: 2, overflow: TextOverflow.ellipsis),
        trailing: FilledButton.tonal(
          onPressed: onInstall,
          child: const Text('Install'),
        ),
      ),
    );
  }
}
