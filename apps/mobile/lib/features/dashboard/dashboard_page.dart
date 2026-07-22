import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../../core/services/websocket_service.dart';
import '../../core/theme/app_theme.dart';

class DashboardPage extends ConsumerWidget {
  const DashboardPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final socketState = ref.watch(webSocketServiceProvider);
    final socketService = ref.read(webSocketServiceProvider.notifier);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final chatTheme = theme.extension<ChatTheme>();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Header
        Text(
          'Dashboard',
          style: theme.textTheme.headlineMedium?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'Welcome to DASH AI Operating System',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: colorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
        const SizedBox(height: 24),

        // Quick actions
        _SectionHeader(title: 'Quick Actions', theme: theme),
        const SizedBox(height: 8),
        Row(
          children: [
            Expanded(
              child: _ActionCard(
                icon: Icons.chat_bubble_outline,
                label: 'New Chat',
                color: colorScheme.primary,
                onTap: () => context.go(AppRoutes.chat),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _ActionCard(
                icon: Icons.memory_outlined,
                label: 'Memory',
                color: colorScheme.tertiary,
                onTap: () => context.go(AppRoutes.memory),
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: _ActionCard(
                icon: Icons.settings_outlined,
                label: 'Settings',
                color: colorScheme.secondary,
                onTap: () => context.go(AppRoutes.settings),
              ),
            ),
          ],
        ),
        const SizedBox(height: 24),

        // Connection status
        _SectionHeader(title: 'Connection', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: ListTile(
            leading: Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: socketState.status == WebSocketStatus.connected
                    ? Colors.green
                    : socketState.status == WebSocketStatus.connecting ||
                            socketState.status == WebSocketStatus.reconnecting
                        ? Colors.orange
                        : Colors.red,
              ),
            ),
            title: const Text('WebSocket'),
            subtitle: Text(_connectionLabel(socketState.status)),
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
        if (socketState.status == WebSocketStatus.connected &&
            chatTheme != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Card(
              child: ListTile(
                leading: Icon(Icons.check_circle,
                    color: Colors.green.shade600, size: 20),
                title: const Text('Connected', style: TextStyle(fontSize: 14)),
                subtitle: const Text(
                  'Real-time communication active',
                  style: TextStyle(fontSize: 12),
                ),
              ),
            ),
          ),
        if (socketState.errorMessage != null)
          Padding(
            padding: const EdgeInsets.only(top: 8),
            child: Card(
              color: colorScheme.errorContainer.withValues(alpha: 0.3),
              child: ListTile(
                leading: Icon(Icons.error_outline, color: colorScheme.error),
                title: Text(
                  socketState.errorMessage!,
                  style: TextStyle(color: colorScheme.error, fontSize: 13),
                ),
              ),
            ),
          ),
        const SizedBox(height: 24),

        // Features overview
        _SectionHeader(title: 'Features', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: Column(
            children: [
              _FeatureTile(
                icon: Icons.chat_bubble_outline,
                iconColor: colorScheme.primary,
                title: 'Intelligent Chat',
                subtitle: 'Natural conversations with AI assistance',
                onTap: () => context.go(AppRoutes.chat),
              ),
              const Divider(height: 1, indent: 56, endIndent: 16),
              _FeatureTile(
                icon: Icons.memory_outlined,
                iconColor: colorScheme.tertiary,
                title: 'Memory Management',
                subtitle: 'Persistent knowledge across sessions',
                onTap: () => context.go(AppRoutes.memory),
              ),
              const Divider(height: 1, indent: 56, endIndent: 16),
              _FeatureTile(
                icon: Icons.sync,
                iconColor: colorScheme.secondary,
                title: 'Multi-Device Sync',
                subtitle: 'Seamless synchronization across devices',
                onTap: () {},
              ),
              const Divider(height: 1, indent: 56, endIndent: 16),
              _FeatureTile(
                icon: Icons.security,
                iconColor: Colors.green,
                title: 'Secure & Private',
                subtitle: 'End-to-end encryption for your data',
                onTap: () {},
              ),
            ],
          ),
        ),
        const SizedBox(height: 24),

        // Recent activity placeholder
        _SectionHeader(title: 'Recent Activity', theme: theme),
        const SizedBox(height: 8),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Column(
                children: [
                  Icon(
                    Icons.history,
                    size: 32,
                    color: colorScheme.onSurface.withValues(alpha: 0.2),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    'No recent activity',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.4),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  String _connectionLabel(WebSocketStatus status) {
    switch (status) {
      case WebSocketStatus.connected:
        return 'Connected and ready';
      case WebSocketStatus.connecting:
        return 'Connecting...';
      case WebSocketStatus.reconnecting:
        return 'Reconnecting...';
      case WebSocketStatus.disconnected:
        return 'Not connected';
      case WebSocketStatus.error:
        return 'Connection error';
    }
  }
}

class _SectionHeader extends StatelessWidget {
  const _SectionHeader({required this.title, required this.theme});

  final String title;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w600,
        color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
        letterSpacing: 0.5,
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({
    required this.icon,
    required this.label,
    required this.color,
    required this.onTap,
  });

  final IconData icon;
  final String label;
  final Color color;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        onTap: onTap,
        borderRadius: BorderRadius.circular(12),
        child: Padding(
          padding: const EdgeInsets.symmetric(vertical: 20, horizontal: 12),
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(12),
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.1),
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(
                label,
                style: Theme.of(context).textTheme.labelMedium?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _FeatureTile extends StatelessWidget {
  const _FeatureTile({
    required this.icon,
    required this.iconColor,
    required this.title,
    required this.subtitle,
    required this.onTap,
  });

  final IconData icon;
  final Color iconColor;
  final String title;
  final String subtitle;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Container(
        padding: const EdgeInsets.all(8),
        decoration: BoxDecoration(
          color: iconColor.withValues(alpha: 0.1),
          borderRadius: BorderRadius.circular(8),
        ),
        child: Icon(icon, color: iconColor, size: 20),
      ),
      title: Text(title, style: const TextStyle(fontSize: 14)),
      subtitle: Text(
        subtitle,
        style: const TextStyle(fontSize: 12),
      ),
      trailing: const Icon(Icons.chevron_right, size: 18),
      onTap: onTap,
    );
  }
}

