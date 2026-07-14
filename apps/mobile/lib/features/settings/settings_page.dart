import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/constants.dart';
import '../../core/routing/app_routes.dart';
import '../../core/services/websocket_service.dart';
import '../auth/providers/auth_provider.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final socketState = ref.watch(webSocketServiceProvider);
    final authState = ref.watch(authProvider);
    final colorScheme = Theme.of(context).colorScheme;

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

        Card(
          child: Column(
            children: [
              const ListTile(
                leading: Icon(Icons.dns_outlined),
                title: Text('Backend URL'),
                subtitle: Text(defaultBackendUrl),
              ),
              const Divider(height: 1),
              const ListTile(
                leading: Icon(Icons.sensors_outlined),
                title: Text('WebSocket URL'),
                subtitle: Text(defaultWebSocketUrl),
              ),
              const Divider(height: 1),
              ListTile(
                leading: const Icon(Icons.info_outline),
                title: const Text('Connection'),
                subtitle: Text(socketState.status.name),
              ),
            ],
          ),
        ),
        if (socketState.errorMessage != null) ...[
          const SizedBox(height: 12),
          Card(
            child: ListTile(
              leading: Icon(
                Icons.error_outline,
                color: colorScheme.error,
              ),
              title: const Text('WebSocket error'),
              subtitle: Text(socketState.errorMessage!),
            ),
          ),
        ],
        const SizedBox(height: 24),

        // Logout button
        Card(
          child: ListTile(
            leading: Icon(Icons.logout, color: colorScheme.error),
            title: Text('Logout', style: TextStyle(color: colorScheme.error)),
            onTap: () async {
              final confirmed = await showDialog<bool>(
                context: context,
                builder: (ctx) => AlertDialog(
                  title: const Text('Logout'),
                  content: const Text('Are you sure you want to log out?'),
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
      ],
    );
  }
}
