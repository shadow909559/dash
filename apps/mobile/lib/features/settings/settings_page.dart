import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants.dart';
import '../../core/services/websocket_service.dart';

class SettingsPage extends ConsumerWidget {
  const SettingsPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final socketState = ref.watch(webSocketServiceProvider);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
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
                color: Theme.of(context).colorScheme.error,
              ),
              title: const Text('WebSocket error'),
              subtitle: Text(socketState.errorMessage!),
            ),
          ),
        ],
      ],
    );
  }
}
