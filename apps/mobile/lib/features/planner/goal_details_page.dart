import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../core/routing/app_routes.dart';
import 'models/goal.dart';
import 'services/planner_service.dart';
import 'providers/goals_provider.dart';
import 'providers/planner_provider.dart';
import '../tasks/models/task.dart';
import '../tasks/providers/tasks_provider.dart';

class GoalDetailsPage extends ConsumerStatefulWidget {
  const GoalDetailsPage({required this.goalId, super.key});

  final String goalId;

  @override
  ConsumerState<GoalDetailsPage> createState() => _GoalDetailsPageState();
}

class _GoalDetailsPageState extends ConsumerState<GoalDetailsPage> with SingleTickerProviderStateMixin {
  late TabController _tabController;
  bool _isLoading = false;
  String? _errorMessage;
  Goal? _goal;
  List<Task> _tasks = [];

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 3, vsync: this);
    WidgetsBinding.instance.addPostFrameCallback((_) => _loadData());
  }

  @override
  void dispose() {
    _tabController.dispose();
    super.dispose();
  }

  Future<void> _loadData() async {
    setState(() {
      _isLoading = true;
      _errorMessage = null;
    });
    try {
      final plannerService = ref.read(goalsServiceProvider);
      final goalData = await plannerService.getGoal(widget.goalId);
      final tasksData = await plannerService.listTasks(widget.goalId);
      setState(() {
        _goal = goalData != null ? Goal.fromJson(goalData as Map<String, dynamic>) : null;
        _tasks = tasksData.map((t) => Task.fromJson(t as Map<String, dynamic>)).toList();
        _isLoading = false;
      });
    } catch (e) {
      setState(() {
        _errorMessage = e.toString();
        _isLoading = false;
      });
    }
  }

  Future<void> _handleStart() async {
    try {
      final plannerService = ref.read(goalsServiceProvider);
      await plannerService.startGoal(widget.goalId);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Goal started')));
        await _loadData();
        await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to start goal: $e')));
    }
  }

  Future<void> _showCreateTaskDialog() async {
    final nameController = TextEditingController();
    final descController = TextEditingController();
    if (!mounted) return;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('New Task'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(labelText: 'Task name', hintText: 'Task name'),
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
                final taskService = ref.read(tasksProvider.notifier);
                final data = await taskService.createTask(widget.goalId, name: name, description: descController.text.trim());
                final newTask = Task.fromJson(data as Map<String, dynamic>);
                setState(() {
                  _tasks = [..._tasks, newTask];
                });
                await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Task created')));
              } catch (e) {
                if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to create task: $e')));
              }
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }

  Future<void> _deleteGoal() async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Delete Goal'),
        content: const Text('Are you sure you want to delete this goal?'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(onPressed: () => Navigator.pop(ctx, true), child: const Text('Delete')),
        ],
      ),
    );
    if (confirmed != true) return;
    try {
      await ref.read(goalsProvider.notifier).deleteGoal(widget.goalId);
      await ref.read(plannerProvider.notifier).loadDashboard(refresh: true);
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(const SnackBar(content: Text('Goal deleted')));
        context.pop();
      }
    } catch (e) {
      if (mounted) ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('Failed to delete goal: $e')));
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (_isLoading && _goal == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Goal Details')),
        body: const Center(child: CircularProgressIndicator()),
      );
    }

    if (_errorMessage != null || _goal == null) {
      return Scaffold(
        appBar: AppBar(title: const Text('Goal Details')),
        body: Center(
          child: Padding(
            padding: const EdgeInsets.all(32),
            child: Column(
              children: [
                Icon(Icons.error_outline, size: 48, color: colorScheme.error),
                const SizedBox(height: 16),
                Text(_errorMessage ?? 'Goal not found', textAlign: TextAlign.center),
                const SizedBox(height: 16),
                FilledButton.tonal(onPressed: _loadData, child: const Text('Retry')),
              ],
            ),
          ),
        ),
      );
    }

    final statusColor = _goal!.status == 'active' ? Colors.green : _goal!.status == 'completed' ? Colors.blue : colorScheme.outline;

    return Scaffold(
      appBar: AppBar(
        title: Text(_goal!.name),
        actions: [
          if (_goal!.status != 'active')
            IconButton(onPressed: _handleStart, icon: const Icon(Icons.play_arrow), tooltip: 'Start Goal'),
          IconButton(onPressed: _deleteGoal, icon: Icon(Icons.delete_outline, color: colorScheme.error), tooltip: 'Delete'),
        ],
      ),
      body: Column(
        children: [
          TabBar(
            controller: _tabController,
            tabs: const [
              Tab(text: 'Overview'),
              Tab(text: 'Tasks'),
              Tab(text: 'History'),
            ],
          ),
          Expanded(
            child: TabBarView(
              controller: _tabController,
              children: [
                _buildOverview(theme, colorScheme, statusColor),
                _buildTasks(theme, colorScheme),
                _buildHistory(theme, colorScheme),
              ],
            ),
          ),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateTaskDialog,
        icon: const Icon(Icons.add),
        label: const Text('New Task'),
      ),
    );
  }

  Widget _buildOverview(ThemeData theme, ColorScheme colorScheme, Color statusColor) {
    return ListView(
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
                    Text('Overview', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  ],
                ),
                const SizedBox(height: 16),
                _InfoRow(label: 'Status', value: _goal!.status, color: statusColor, theme: theme),
                const SizedBox(height: 12),
                _InfoRow(label: 'Created', value: DateFormat.yMMMd().format(_goal!.createdAt), theme: theme),
                const SizedBox(height: 12),
                _InfoRow(label: 'Updated', value: DateFormat.yMMMd().format(_goal!.updatedAt), theme: theme),
              ],
            ),
          ),
        ),
        const SizedBox(height: 16),
        if (_goal!.description != null && _goal!.description!.isNotEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Description', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
                  const SizedBox(height: 8),
                  Text(_goal!.description!),
                ],
              ),
            ),
          ),
      ],
    );
  }

  Widget _buildTasks(ThemeData theme, ColorScheme colorScheme) {
    final pendingTasks = _tasks.where((t) => t.status != 'completed').toList();
    final completedTasks = _tasks.where((t) => t.status == 'completed').toList();

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        if (pendingTasks.isEmpty && completedTasks.isEmpty)
          Center(
            child: Padding(
              padding: const EdgeInsets.all(32),
              child: Text('No tasks yet', style: theme.textTheme.bodyMedium),
            ),
          ),
        ...pendingTasks.map((t) => _TaskItem(task: t, theme: theme, colorScheme: colorScheme)),
        if (completedTasks.isNotEmpty) ...[
          const SizedBox(height: 16),
          Text('Completed', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
          const SizedBox(height: 8),
          ...completedTasks.map((t) => _TaskItem(task: t, theme: theme, colorScheme: colorScheme)),
        ],
      ],
    );
  }

  Widget _buildHistory(ThemeData theme, ColorScheme colorScheme) {
    final sorted = [..._tasks]..sort((a, b) => b.createdAt.compareTo(a.createdAt));
    if (sorted.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Text('No history yet', style: theme.textTheme.bodyMedium),
        ),
      );
    }
    return ListView.builder(
      padding: const EdgeInsets.all(16),
      itemCount: sorted.length,
      itemBuilder: (context, index) => _TaskItem(task: sorted[index], theme: theme, colorScheme: colorScheme),
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
        Chip(label: Text(value, style: TextStyle(color: color ?? theme.colorScheme.onSurface, fontSize: 12)), visualDensity: VisualDensity.compact),
      ],
    );
  }
}

class _TaskItem extends StatelessWidget {
  const _TaskItem({required this.task, required this.theme, required this.colorScheme});

  final Task task;
  final ThemeData theme;
  final ColorScheme colorScheme;

  @override
  Widget build(BuildContext context) {
    final statusColor = task.status == 'completed' ? Colors.green : task.status == 'in_progress' ? Colors.orange : colorScheme.outline;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Icon(Icons.circle, size: 12, color: statusColor),
        title: Text(task.name, style: const TextStyle(fontWeight: FontWeight.w500)),
        subtitle: task.description != null && task.description!.isNotEmpty ? Text(task.description!, maxLines: 1, overflow: TextOverflow.ellipsis) : null,
        trailing: Chip(label: Text(task.status, style: const TextStyle(fontSize: 12)), visualDensity: VisualDensity.compact),
        onTap: () => context.push('${AppRoutes.taskDetails}/${task.id}'),
      ),
    );
  }
}
