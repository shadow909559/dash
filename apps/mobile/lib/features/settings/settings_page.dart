import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants.dart';
import '../../core/routing/app_routes.dart';
import '../../core/services/websocket_service.dart';
import '../auth/providers/auth_provider.dart';

/// Provider for the current theme mode.
final themeModeProvider = StateProvider<ThemeMode>((ref) => ThemeMode.dark);

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final socketState = ref.watch(webSocketServiceProvider);
    final authState = ref.watch(authProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final currentThemeMode = ref.watch(themeModeProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // User info card
        if (authState.user != null)
          Card(
            child: ListTile(
              leading: CircleAvatar(
                backgroundColor: colorScheme.primaryContainer,
                child: Text(
                  authState.user!.username[0].toUpperCase(),
                  style: TextStyle(color: colorScheme.onPrimaryContainer),
                ),
              ),
              title: Text(authState.user!.username),
              subtitle: Text(authState.user!.email),
            ),
          ),
        const SizedBox(height: 12),

        // Appearance section
        _SectionLabel(title: 'Appearance', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              SwitchListTile(
                secondary: Icon(
                  currentThemeMode == ThemeMode.dark
                      ? Icons.dark_mode
                      : Icons.light_mode,
                  color: currentThemeMode == ThemeMode.dark
                      ? Colors.amber
                      : Colors.orange,
                ),
                title: const Text('Dark Mode', style: TextStyle(fontSize: 14)),
                subtitle: Text(
                  currentThemeMode == ThemeMode.dark
                      ? 'Dark theme active'
                      : 'Light theme active',
                  style: const TextStyle(fontSize: 12),
                ),
                value: currentThemeMode == ThemeMode.dark,
                onChanged: (value) {
                  ref.read(themeModeProvider.notifier).state =
                      value ? ThemeMode.dark : ThemeMode.light;
                },
              ),
            ],
          ),
        ),
        const SizedBox(height: 16),

        // Connection section
        _SectionLabel(title: 'Connection', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 12, 16, 4),
                child: Row(
                  children: [
                    Icon(Icons.sensors_outlined,
                        size: 20, color: colorScheme.onSurface),
                    const SizedBox(width: 8),
                    Text(
                      'Connection Status',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                        color: colorScheme.onSurface.withValues(alpha: 0.7),
                      ),
                    ),
                    const Spacer(),
                    Container(
                      width: 10,
                      height: 10,
                      decoration: BoxDecoration(
                        shape: BoxShape.circle,
                        color: socketState.status == WebSocketStatus.connected
                            ? Colors.green
                            : socketState.status == WebSocketStatus.connecting
                                ? Colors.orange
                                : Colors.red,
                      ),
                    ),
                  ],
                ),
              ),
              ListTile(
                leading: const Icon(Icons.dns_outlined, size: 20),
                title:
                    const Text('Backend URL', style: TextStyle(fontSize: 14)),
                subtitle: Text(
                  defaultBackendUrl,
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: const Icon(Icons.link_outlined, size: 20),
                title: const Text('WebSocket URL',
                    style: TextStyle(fontSize: 14)),
                subtitle: Text(
                  defaultWebSocketUrl,
                  style: TextStyle(
                    fontSize: 12,
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: const Icon(Icons.info_outline, size: 20),
                title:
                    const Text('Status', style: TextStyle(fontSize: 14)),
                subtitle: Text(
                  _connectionLabel(socketState.status),
                  style: TextStyle(
                    fontSize: 12,
                    color: socketState.status == WebSocketStatus.connected
                        ? Colors.green
                        : colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
                trailing: socketState.status == WebSocketStatus.connected
                    ? Container(
                        width: 10,
                        height: 10,
                        decoration: const BoxDecoration(
                          color: Colors.green,
                          shape: BoxShape.circle,
                        ),
                      )
                    : null,
              ),
            ],
          ),
        ),

        if (socketState.errorMessage != null) ...[
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: Icon(Icons.error_outline, color: colorScheme.error),
              title: const Text('WebSocket error'),
              subtitle: Text(socketState.errorMessage!),
            ),
          ),
        ],
        const SizedBox(height: 16),

        // Navigation section
        _SectionLabel(title: 'Navigate', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              ListTile(
                leading: Icon(Icons.memory, color: colorScheme.primary),
                title: const Text('Memory Browser'),
                subtitle: const Text('View and manage memories'),
                trailing: const Icon(Icons.chevron_right, size: 18),
                onTap: () => context.go(AppRoutes.memory),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(Icons.info_outline, color: colorScheme.primary),
                title: const Text('About'),
                subtitle: const Text('App info and version'),
                trailing: const Icon(Icons.chevron_right, size: 18),
                onTap: () => context.go(AppRoutes.about),
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Logout section
        _SectionLabel(title: 'Account', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: ListTile(
            leading: Icon(Icons.logout, color: colorScheme.error),
            title:
                Text('Logout', style: TextStyle(color: colorScheme.error)),
            onTap: () async {
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Logout'),
                  content: const Text(
                      'Are you sure you want to log out?'),
                  actions: [
                    TextButton(
                      onPressed: () => Navigator.of(ctx).pop(false),
                      child: const Text('Cancel'),
                    ),
                    FilledButton(
                      onPressed: () => Navigator.of(ctx).pop(true),
                      child: const Text('Logout'),
                    ),
                  ],
                ),
              );
              if (confirmed == true) {
                await ref.read(authProvider.notifier).logout();
                if (context.mounted) context.go(AppRoutes.login);
              }
            },
          ),
        ),
        const SizedBox(height: 24),

        // App version
        Center(
          child: Text(
            'v$appVersion',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.3),
            ),
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  String _connectionLabel(WebSocketStatus status) {
    switch (status) {
      case WebSocketStatus.connected:
        return 'Connected';
      case WebSocketStatus.connecting:
        return 'Connecting...';
      case WebSocketStatus.reconnecting:
        return 'Reconnecting...';
      case WebSocketStatus.disconnected:
        return 'Disconnected';
      case WebSocketStatus.error:
        return 'Error';
    }
  }
}

class _SectionLabel extends StatelessWidget {
  const _SectionLabel({required this.title, required this.theme});

  final String title;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 4, vertical: 2),
      child: Text(
        title,
        style: theme.textTheme.labelLarge?.copyWith(
          fontWeight: FontWeight.w600,
          color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
          letterSpacing: 0.5,
        ),
      ),
    );
  }
}

