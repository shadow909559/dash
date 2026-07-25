import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/app_theme.dart';
import '../../features/planner/models/goal.dart';
import '../../features/planner/providers/goals_provider.dart';
import '../../features/tasks/models/task.dart';
import '../../features/tasks/providers/tasks_provider.dart';

class TaskDetailsPage extends ConsumerStatefulWidget {
  const TaskDetailsPage({required this.taskId, super.key});

  final String taskId;

  @override
  ConsumerState<TaskDetailsPage> createState() => _TaskDetailsPageState();
}

class _TaskDetailsPageState extends ConsumerState<TaskDetailsPage> {
  bool _isLoading = true;
  String? _errorMessage;
  Task? _task;
  Goal? _goal;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadData());
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final allTasks = ref.read(tasksProvider).tasks;
      final found = allTasks.firstWhere((t) => t.id == widget.taskId, orElse: () => _task ?? Task(id: '', goalId: '', name: '', status: '', createdAt: DateTime.now(), updatedAt: DateTime.now()));
      String? goalName;
      if (found.goalId.isNotEmpty) {
        final goals = ref.read(goalsProvider).goals;
        final goal = goals.firstWhere((g) => g.id == found.goalId, orElse: () => _goal ?? Goal(id: '', userId: '', name: '', status: '', createdAt: DateTime.now(), updatedAt: DateTime.now()));
        goalName = goal.name;
        _goal = goal.id.isNotEmpty ? goal : null;
      }
      setState(() {
        _task = found.id.isNotEmpty ? found : null;
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _completeTask() async {
    if (_task == null) return;
    try {
      await ref.read(tasksProvider.notifier).completeTask(_task!.id);
      setState(() {
        _task = _task!.copyWith(status: 'completed');
      });
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Task completed')));
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  Future<void> _deleteTask() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Task'),
        content: const Text('Are you sure you want to delete this task?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(tasksProvider.notifier).deleteTask(_task!.id);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Task deleted')));
        context.pop();
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (_isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Task Details')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_errorMessage != null || _task == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Task Details')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              children: [
                Icon(Icons.error_outline, size: 48, color: colorScheme.error),
                const SizedBox(height: 16),
                Text(_errorMessage ?? 'Task not found', textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton.tonal(onPressed: _loadData, child: const Text('Retry')),
              ],
            ),
          ),
        ),
      );
    }

    final statusColor = _task!.status == 'completed' ? Colors.green : _task!.status == 'in_progress' ? Colors.orange : colorScheme.outline;

    return Scaffold(
      appBar: AppBar(
        title: Text(_task!.name),
        actions: [
          if (_task!.status != 'completed')
            IconButton(onPressed: _completeTask, icon: const Icon(Icons.check_circle_outline), tooltip: 'Complete'),
          IconButton(onPressed: _deleteTask, icon: Icon(Icons.delete_outline, color: colorScheme.error), tooltip: 'Delete'),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Row(
                    children: [
                      Icon(Icons.info_outline, color: statusColor, size: 20),
                      const SizedBox(width: 8),
                      Text('Task Details', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                    ],
                  ),
                  const SizedBox(height: 16),
                  _InfoRow(label: 'Status', value: _task!.status, color: statusColor, theme: theme),
                  const SizedBox(height: 12),
                  _InfoRow(label: 'Goal', value: _goal?.name ?? _task!.goalId, theme: theme),
                  const SizedBox(height: 12),
                  _InfoRow(label: 'Attempt', value: '${_task!.attempt}', theme: theme),
                  const SizedBox(height: 12),
                  _InfoRow(label: 'Created', value: DateFormat.yMMMd().format(_task!.createdAt), theme: theme),
                  const SizedBox(height: 12),
                  _InfoRow(label: 'Updated', value: DateFormat.yMMMd().format(_task!.updatedAt), theme: theme),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          if (_task!.description != null && _task!.description!.isNotEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text('Description', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
                    const SizedBox(height: 8),
                    Text(_task!.description!),
                  ],
                ),
              ),
            ),
        ],
      ),
    );
  }
}

class _InfoRow extends StatelessWidget {
  const _InfoRow({required this.label, required this.value, this.color, required this.theme});

  final String label;
  final String value;
  final Color? color;
  final ThemeData theme;

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisAlignment: MainAxisAlignment.spaceBetween,
      children: [
        Text(label, style: theme.textTheme.bodyMedium),
        Flexible(
          child: Text(
            value,
            textAlign: TextAlign.end,
            style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500),
          ),
        ),
      ],
    );
  }
}
