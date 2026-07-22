import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';

/// AI Workspace page - central hub for AI-powered features.
class WorkspacePage extends ConsumerWidget {
  const WorkspacePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // Header
        Text(
          'AI Workspace',
          style: theme.textTheme.headlineMedium?.copyWith(
            fontWeight: FontWeight.bold,
          ),
        ),
        const SizedBox(height: 4),
        Text(
          'Your intelligent productivity hub',
          style: theme.textTheme.bodyMedium?.copyWith(
            color: colorScheme.onSurface.withValues(alpha: 0.6),
          ),
        ),
        const SizedBox(height: 24),

        // Quick actions grid
        _SectionHeader(title: 'Quick Actions', theme: theme),
        const SizedBox(height: 12),
        _ActionGrid(
          actions: [
            _ActionItem(
              icon: Icons.chat_bubble_outline,
              label: 'New Chat',
              color: colorScheme.primary,
              route: AppRoutes.chat,
            ),
            _ActionItem(
              icon: Icons.memory_outlined,
              label: 'Memories',
              color: colorScheme.tertiary,
              route: AppRoutes.memory,
            ),
            const _ActionItem(
              icon: Icons.auto_awesome,
              label: 'Automations',
              color: Colors.amber,
              route: null,
            ),
            const _ActionItem(
              icon: Icons.task_alt,
              label: 'Tasks',
              color: Colors.green,
              route: null,
            ),
            const _ActionItem(
              icon: Icons.extension_outlined,
              label: 'Plugins',
              color: Colors.purple,
              route: null,
            ),
            _ActionItem(
              icon: Icons.settings_outlined,
              label: 'Settings',
              color: colorScheme.secondary,
              route: AppRoutes.settings,
            ),
          ],
        ),
        const SizedBox(height: 24),

        // Smart Suggestions
        _SectionHeader(title: 'Smart Suggestions', theme: theme),
        const SizedBox(height: 12),
        _SuggestionChip(
          label: 'Summarize my recent conversations',
          icon: Icons.summarize_outlined,
          onTap: () => context.go(AppRoutes.chat),
        ),
        const SizedBox(height: 8),
        _SuggestionChip(
          label: 'Help me organize my projects',
          icon: Icons.folder_outlined,
          onTap: () {},
        ),
        const SizedBox(height: 8),
        _SuggestionChip(
          label: 'What do you know about me?',
          icon: Icons.person_outline,
          onTap: () => context.go(AppRoutes.memory),
        ),
        const SizedBox(height: 24),

        // Recent Activity
        _SectionHeader(title: 'Recent Activity', theme: theme),
        const SizedBox(height: 12),
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
                    'Start a conversation to see activity here',
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.4),
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ],
    );
  }
}

class _SectionHeader extends StatelessWidget {
  final String title;
  final ThemeData theme;

  const _SectionHeader({required this.title, required this.theme});

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

class _ActionItem {
  final IconData icon;
  final String label;
  final Color color;
  final String? route;

  const _ActionItem({
    required this.icon,
    required this.label,
    required this.color,
    this.route,
  });
}

class _ActionGrid extends StatelessWidget {
  final List<_ActionItem> actions;

  const _ActionGrid({required this.actions});

  @override
  Widget build(BuildContext context) {
    return GridView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      gridDelegate: const SliverGridDelegateWithFixedCrossAxisCount(
        crossAxisCount: 3,
        crossAxisSpacing: 12,
        mainAxisSpacing: 12,
        childAspectRatio: 0.85,
      ),
      itemCount: actions.length,
      itemBuilder: (context, index) {
        final action = actions[index];
        return Card(
          child: InkWell(
            onTap: () {
              if (action.route != null) {
                context.go(action.route!);
              }
            },
            borderRadius: BorderRadius.circular(12),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Container(
                    padding: const EdgeInsets.all(12),
                    decoration: BoxDecoration(
                      color: action.color.withValues(alpha: 0.1),
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Icon(action.icon, color: action.color, size: 28),
                  ),
                  const SizedBox(height: 8),
                  Text(
                    action.label,
                    textAlign: TextAlign.center,
                    style: Theme.of(context).textTheme.labelMedium?.copyWith(
                          fontWeight: FontWeight.w600,
                        ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }
}

class _SuggestionChip extends StatelessWidget {
  final String label;
  final IconData icon;
  final VoidCallback onTap;

  const _SuggestionChip({
    required this.label,
    required this.icon,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Card(
      child: ListTile(
        leading: Icon(icon, color: theme.colorScheme.primary, size: 24),
        title: Text(label, style: const TextStyle(fontSize: 14)),
        trailing: const Icon(Icons.arrow_forward_ios, size: 14),
        onTap: onTap,
      ),
    );
  }
}

