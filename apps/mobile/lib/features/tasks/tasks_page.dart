import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../../features/tasks/models/task.dart';
import '../../features/tasks/providers/tasks_provider.dart';
import '../../features/planner/providers/goals_provider.dart';

class TasksPage extends ConsumerStatefulWidget {
  const TasksPage({super.key});

  @override
  ConsumerState<TasksPage> createState() => _TasksPageState();
}

class _TasksPageState extends ConsumerState<TasksPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(tasksProvider.notifier).loadTasks();
    });
  }

  Future<void> _handleRefresh() async {
    await ref.read(tasksProvider.notifier).loadTasks(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final tasksState = ref.watch(tasksProvider);
    final filtered = tasksState.filteredTasks;

    return Column(
      children: [
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(Icons.check_circle_outline, color: colorScheme.primary, size: 24),
              const SizedBox(width: 12),
              Text(
                'Tasks',
                style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              DropdownButton<String?>(
                value: tasksState.filterGoalId,
                hint: const Text('Filter by goal', style: TextStyle(fontSize: 14)),
                items: [
                  const DropdownMenuItem(value: null, child: Text('All Goals')),
                  ...ref.read(goalsProvider).goals.map((g) => DropdownMenuItem(value: g.id, child: Text(g.name))),
                ],
                onChanged: (value) => ref.read(tasksProvider.notifier).setFilterGoalId(value),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: RefreshIndicator(
            onRefresh: _handleRefresh,
            child: tasksState.isLoading && tasksState.tasks.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : tasksState.errorMessage != null && tasksState.tasks.isEmpty
                    ? _buildErrorState(tasksState.errorMessage!)
                    : filtered.isEmpty
                        ? _buildEmptyState()
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            itemCount: filtered.length,
                            itemBuilder: (context, index) => _TaskTile(task: filtered[index], theme: theme, colorScheme: colorScheme),
                          ),
          ),
        ),
      ],
    );
  }

  Widget _buildEmptyState() {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(color: colorScheme.primaryContainer.withValues(alpha: 0.3), shape: BoxShape.circle),
              child: Icon(Icons.task_alt_outlined, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text('No tasks yet', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Create a task to get started', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(String message) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.error_outline, size: 48, color: colorScheme.error),
            const SizedBox(height: 16),
            Text('Something went wrong', style: theme.textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(message, textAlign: TextAlign.center, style: theme.textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton.tonal(onPressed: () => ref.read(tasksProvider.notifier).loadTasks(refresh: true), child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}

class _TaskTile extends StatelessWidget {
  const _TaskTile({required this.task, required this.theme, required this.colorScheme});

  final Task task;
  final ThemeData theme;
  final ColorScheme colorScheme;

  @override
  Widget build(BuildContext context) {
    final statusColor = task.status == 'completed' ? Colors.green : task.status == 'in_progress' ? Colors.orange : colorScheme.outline;
    final goalName = task.goalId.length > 8 ? 'Goal ${task.goalId.substring(0, 8)}...' : 'Goal ${task.goalId}';
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: () => context.push('${AppRoutes.taskDetails}/${task.id}'),
        leading: Icon(Icons.circle, size: 12, color: statusColor),
        title: Text(task.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            if (task.description != null && task.description!.isNotEmpty)
              Text(task.description!, maxLines: 1, overflow: TextOverflow.ellipsis),
            Text(goalName, style: TextStyle(fontSize: 12, color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
        trailing: Chip(label: Text(task.status, style: const TextStyle(fontSize: 12)), visualDensity: VisualDensity.compact),
      ),
    );
  }
}
