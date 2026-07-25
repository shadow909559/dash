import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/app_theme.dart';
import 'calendar_page.dart';
import 'goals_page.dart';
import './providers/planner_provider.dart';
import './providers/goals_provider.dart';
import '../tasks/tasks_page.dart';
import '../tasks/models/task.dart';
import './models/goal.dart';

class PlannerPage extends ConsumerStatefulWidget {
  const PlannerPage({super.key});

  @override
  ConsumerState<PlannerPage> createState() => _PlannerPageState();
}

class _PlannerPageState extends ConsumerState<PlannerPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(plannerProvider.notifier).loadDashboard();
    });
  }

  Future<void> _handleRefresh() async {
    await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final plannerState = ref.watch(plannerProvider);

    return RefreshIndicator(
      onRefresh: _handleRefresh,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Planner',
            style: theme.textTheme.headlineMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const SizedBox(height: 4),
          Text(
            'Plan your goals and track tasks',
            style: theme.textTheme.bodyMedium?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.6),
            ),
          ),
          const SizedBox(height: 24),

          if (plannerState.isLoading && plannerState.goals.isEmpty)
            const Center(child: Padding(padding: EdgeInsets.all(48), child: CircularProgressIndicator()))
          else if (plannerState.errorMessage != null && plannerState.goals.isEmpty)
            _ErrorState(message: plannerState.errorMessage!, onRetry: _handleRefresh)
          else ...[
            // Stat cards
            Row(
              children: [
                Expanded(
                  child: _StatCard(
                    title: 'Active Goals',
                    value: '${plannerState.activeGoalsCount}',
                    icon: Icons.flag_outlined,
                    color: colorScheme.primary,
                    theme: theme,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _StatCard(
                    title: 'Pending Tasks',
                    value: '${plannerState.pendingTasksCount}',
                    icon: Icons.pending_outlined,
                    color: colorScheme.tertiary,
                    theme: theme,
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _StatCard(
                    title: 'Completed Today',
                    value: '${plannerState.completedTodayCount}',
                    icon: Icons.check_circle_outline,
                    color: Colors.green,
                    theme: theme,
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Quick actions
            _SectionHeader(title: 'Quick Actions', theme: theme),
            const SizedBox(height: 12),
            Row(
              children: [
                Expanded(
                  child: _ActionCard(
                    icon: Icons.add_circle_outline,
                    label: 'New Goal',
                    color: colorScheme.primary,
                    onTap: () => _showCreateGoalDialog(context),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionCard(
                    icon: Icons.task_alt_outlined,
                    label: 'View Tasks',
                    color: colorScheme.tertiary,
                    onTap: () => context.push(AppRoutes.tasks),
                  ),
                ),
                const SizedBox(width: 12),
                Expanded(
                  child: _ActionCard(
                    icon: Icons.calendar_month_outlined,
                    label: 'Calendar',
                    color: colorScheme.secondary,
                    onTap: () => context.push(AppRoutes.calendar),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 24),

            // Active goals
            _SectionHeader(title: 'Active Goals', theme: theme),
            const SizedBox(height: 12),
            if (plannerState.goals.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(32),
                  child: Center(
                    child: Column(
                      children: [
                        Icon(Icons.flag_outlined, size: 48, color: colorScheme.onSurface.withValues(alpha: 0.2)),
                        const SizedBox(height: 16),
                        Text('No goals yet', style: theme.textTheme.titleMedium),
                        const SizedBox(height: 8),
                        TextButton.icon(
                          onPressed: () => _showCreateGoalDialog(context),
                          icon: const Icon(Icons.add),
                          label: const Text('Create your first goal'),
                        ),
                      ],
                    ),
                  ),
                ),
              )
            else
              ...plannerState.goals.map((goal) => _GoalCard(
                goal: goal,
                theme: theme,
                colorScheme: colorScheme,
                onTap: () => context.push('${AppRoutes.goalDetails}/${goal.id}'),
              )),
            const SizedBox(height: 24),

            // Upcoming tasks
            _SectionHeader(title: 'Upcoming Tasks', theme: theme),
            const SizedBox(height: 12),
            if (plannerState.tasks.isEmpty)
              Card(
                child: Padding(
                  padding: const EdgeInsets.all(24),
                  child: Center(
                    child: Text('No tasks yet', style: theme.textTheme.bodyMedium),
                  ),
                ),
              )
            else
              ...plannerState.tasks.take(5).map((task) => _TaskCard(
                task: task,
                theme: theme,
                colorScheme: colorScheme,
                onTap: () => context.push('${AppRoutes.taskDetails}/${task.id}'),
              )),
          ],
        ],
      ),
    );
  }

  void _showCreateGoalDialog(BuildContext context) {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Goal'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Goal name', hintText: 'My awesome goal'),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descController,
              decoration: const InputDecoration(labelText: 'Description (optional)', hintText: 'Brief description'),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          FilledButton(
            onPressed: () async {
              final name = nameController.text.trim();
              if (name.isEmpty) return;
              Navigator.pop(ctx);
              await ref.read(goalsProvider.notifier).createGoal(name: name, description: descController.text.trim());
              await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}

class _StatCard extends StatelessWidget {
  const _StatCard({required this.title, required this.value, required this.icon, required this.color, required this.theme});

  final String title;
  final String value;
  final IconData icon;
  final Color color;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    final colorScheme = theme.colorScheme;
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Icon(icon, color: color, size: 20),
            const SizedBox(height: 12),
            Text(value, style: theme.textTheme.headlineSmall?.copyWith(fontWeight: FontWeight.bold, color: color)),
            const SizedBox(height: 4),
            Text(title, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      ),
    );
  }
}

class _ActionCard extends StatelessWidget {
  const _ActionCard({required this.icon, required this.label, required this.color, required this.onTap});

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
                decoration: BoxDecoration(color: color.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(12)),
                child: Icon(icon, color: color, size: 24),
              ),
              const SizedBox(height: 8),
              Text(label, style: Theme.of(context).textTheme.labelMedium?.copyWith(fontWeight: FontWeight.w600)),
            ],
          ),
        ),
      ),
    );
  }
}

class _GoalCard extends StatelessWidget {
  const _GoalCard({required this.goal, required this.theme, required this.colorScheme, required this.onTap});

  final Goal goal;
  final ThemeData theme;
  final ColorScheme colorScheme;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final statusColor = goal.status == 'active' ? Colors.green : goal.status == 'completed' ? Colors.blue : colorScheme.outline;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: onTap,
        leading: Container(
          width: 4,
          height: 40,
          decoration: BoxDecoration(color: statusColor, borderRadius: BorderRadius.circular(2)),
        ),
        title: Text(goal.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: goal.description != null && goal.description!.isNotEmpty ? Text(goal.description!, maxLines: 1, overflow: TextOverflow.ellipsis) : null,
        trailing: Chip(label: Text(goal.status, style: const TextStyle(fontSize: 12)), visualDensity: VisualDensity.compact),
      ),
    );
  }
}

class _TaskCard extends StatelessWidget {
  const _TaskCard({required this.task, required this.theme, required this.colorScheme, required this.onTap});

  final Task task;
  final ThemeData theme;
  final ColorScheme colorScheme;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    final statusColor = task.status == 'completed' ? Colors.green : task.status == 'in_progress' ? Colors.orange : colorScheme.outline;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: onTap,
        leading: Icon(Icons.circle, size: 12, color: statusColor),
        title: Text(task.name, style: const TextStyle(fontWeight: FontWeight.w500)),
        subtitle: Text('Goal: ${task.goalId}', style: TextStyle(fontSize: 12, color: colorScheme.onSurface.withValues(alpha: 0.6))),
        trailing: Chip(label: Text(task.status, style: const TextStyle(fontSize: 12)), visualDensity: VisualDensity.compact),
      ),
    );
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
      style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600, color: theme.colorScheme.onSurface.withValues(alpha: 0.6), letterSpacing: 0.5),
    );
  }
}

class _ErrorState extends StatelessWidget {
  const _ErrorState({required this.message, required this.onRetry});

  final String message;
  final VoidCallback onRetry;

  @override
  Widget build(BuildContext context) {
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
            FilledButton.tonal(onPressed: onRetry, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }
}
