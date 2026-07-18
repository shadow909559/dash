import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/websocket_service.dart';

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final socketState = ref.watch(webSocketServiceProvider);
    final socketService = ref.read(webSocketServiceProvider.notifier);

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text(
          'Remote control shell',
          style: Theme.of(context).textTheme.headlineSmall,
        ),
        const SizedBox(height: 16),
        Card(
          child: ListTile(
            leading: const Icon(Icons.cable),
            title: const Text('WebSocket'),
            subtitle: Text(socketState.status.name),
            trailing: FilledButton.tonal(
              onPressed: socketState.status == WebSocketStatus.connected
                  ? () => socketService.disconnect()
                  : () => socketService.connect(),
              child: Text(
                socketState.status == WebSocketStatus.connected
                    ? 'Disconnect'
                    : 'Connect',
              ),
            ),
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: ListTile(
            leading: Icon(Icons.mic_none),
            title: Text('Voice'),
            subtitle: Text('Placeholder'),
          ),
        ),
        const SizedBox(height: 12),
        const Card(
          child: ListTile(
            leading: Icon(Icons.computer),
            title: Text('Desktop agent'),
            subtitle: Text('Placeholder'),
          ),
        ),
      ],
    );
  }
}
