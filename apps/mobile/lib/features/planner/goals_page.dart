import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../planner/models/goal.dart';
import '../planner/providers/goals_provider.dart';
import '../planner/providers/planner_provider.dart';

class GoalsPage extends ConsumerStatefulWidget {
  const GoalsPage({super.key});

  @override
  ConsumerState<GoalsPage> createState() => _GoalsPageState();
}

class _GoalsPageState extends ConsumerState<GoalsPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(goalsProvider.notifier).loadGoals();
    });
  }

  Future<void> _handleRefresh() async {
    await ref.read(goalsProvider.notifier).loadGoals(refresh: true);
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final goalsState = ref.watch(goalsProvider);
    final filtered = goalsState.filteredGoals;

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(Icons.flag_outlined, color: colorScheme.primary, size: 24),
              const SizedBox(width: 12),
              Text(
                'Goals',
                style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold),
              ),
              const Spacer(),
              IconButton(
                onPressed: () => _showCreateDialog(context),
                icon: const Icon(Icons.add),
                tooltip: 'New Goal',
              ),
            ],
          ),
        ),
        const Divider(height: 1),

        // Search
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: TextField(
            decoration: InputDecoration(
              hintText: 'Search goals...',
              prefixIcon: const Icon(Icons.search, size: 20),
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(12)),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
            ),
            onChanged: (value) => ref.read(goalsProvider.notifier).setSearchQuery(value),
          ),
        ),

        // Status filter chips
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
          child: Row(
            children: [
              _StatusChip(label: 'All', selected: goalsState.statusFilter == null, onTap: () => ref.read(goalsProvider.notifier).setStatusFilter(null), theme: theme),
              const SizedBox(width: 8),
              _StatusChip(label: 'Active', selected: goalsState.statusFilter == 'active', onTap: () => ref.read(goalsProvider.notifier).setStatusFilter('active'), theme: theme),
              const SizedBox(width: 8),
              _StatusChip(label: 'Completed', selected: goalsState.statusFilter == 'completed', onTap: () => ref.read(goalsProvider.notifier).setStatusFilter('completed'), theme: theme),
              const SizedBox(width: 8),
              _StatusChip(label: 'Pending', selected: goalsState.statusFilter == 'pending', onTap: () => ref.read(goalsProvider.notifier).setStatusFilter('pending'), theme: theme),
            ],
          ),
        ),
        const SizedBox(height: 8),

        Expanded(
          child: RefreshIndicator(
            onRefresh: _handleRefresh,
            child: goalsState.isLoading && goalsState.goals.isEmpty
                ? const Center(child: CircularProgressIndicator())
                : goalsState.errorMessage != null && goalsState.goals.isEmpty
                    ? _buildErrorState(goalsState.errorMessage!)
                    : filtered.isEmpty
                        ? _buildEmptyState()
                        : ListView.builder(
                            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
                            itemCount: filtered.length,
                            itemBuilder: (context, index) => _GoalTile(goal: filtered[index], theme: theme, colorScheme: colorScheme),
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
              child: Icon(Icons.flag_outlined, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text('No goals yet', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text('Create a goal to start planning', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
            const SizedBox(height: 24),
            FilledButton.tonalIcon(onPressed: () => _showCreateDialog(context), icon: const Icon(Icons.add), label: const Text('Create Goal')),
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
            FilledButton.tonal(onPressed: () => ref.read(goalsProvider.notifier).loadGoals(refresh: true), child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  void _showCreateDialog(BuildContext context) {
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
              try {
                await ref.read(goalsProvider.notifier).createGoal(name: name, description: descController.text.trim());
                await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to create goal: $e')));
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}

class _StatusChip extends StatelessWidget {
  const _StatusChip({required this.label, required this.selected, required this.onTap, required this.theme});

  final String label;
  final bool selected;
  final VoidCallback onTap;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return FilterChip(
      label: Text(label),
      selected: selected,
      onSelected: (_) => onTap(),
      selectedColor: theme.colorScheme.primaryContainer,
    );
  }
}

class _GoalTile extends StatelessWidget {
  const _GoalTile({required this.goal, required this.theme, required this.colorScheme});

  final Goal goal;
  final ThemeData theme;
  final ColorScheme colorScheme;

  @override
  Widget build(BuildContext context) {
    final statusColor = goal.status == 'active' ? Colors.green : goal.status == 'completed' ? Colors.blue : colorScheme.outline;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        onTap: () => context.push('${AppRoutes.goalDetails}/${goal.id}'),
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
