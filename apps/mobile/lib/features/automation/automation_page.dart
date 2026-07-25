import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';

import '../../core/routing/app_routes.dart';
import '../automation/models/automation.dart';
import '../automation/providers/automation_provider.dart';

class AutomationPage extends ConsumerStatefulWidget {
  const AutomationPage({super.key});

  @override
  ConsumerState<AutomationPage> createState() => _AutomationPageState();
}

class _AutomationPageState extends ConsumerState<AutomationPage> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(automationProvider.notifier).loadAutomations(refresh: true);
    });
  }

  Future<void> _handleRefresh() async {
    await ref.read(automationProvider.notifier).loadAutomations(refresh: true);
  }

  Future<void> _openDialog({Automation? automation}) async {
    final nameController = TextEditingController(text: automation?.name ?? '');
    final descController =
        TextEditingController(text: automation?.description ?? '');
    final toolController =
        TextEditingController(text: automation?.toolName ?? '');
    final argsController =
        TextEditingController(text: automation?.toolArguments.join(', ') ?? '');
    final scheduleController =
        TextEditingController(text: _formatSchedule(automation?.schedule) ?? '');
    var enabled = automation?.enabled ?? true;
    var trigger = automation?.triggerType ?? 'event';

    final result = await showDialog<bool>(
      context: context,
      builder: (ctx) => StatefulBuilder(
        builder: (context, setModalState) => _AutomationDialog(
          nameController: nameController,
          descController: descController,
          toolController: toolController,
          argsController: argsController,
          scheduleController: scheduleController,
          trigger: trigger,
          enabled: enabled,
          onTriggerChanged: (v) => setModalState(() => trigger = v),
          onEnabledChanged: (v) => setModalState(() => enabled = v),
        ),
      ),
    );

    if (result != true || !mounted) return;

    final notifier = ref.read(automationProvider.notifier);
    final name = nameController.text.trim();
    final desc = descController.text.trim().isEmpty ? null : descController.text.trim();
    final toolName = toolController.text.trim();
    final argsText = argsController.text.trim();
    final scheduleText = scheduleController.text.trim();
    final schedule = scheduleText.isEmpty ? null : {'cron': scheduleText};

    if (automation == null) {
      await notifier.createAutomation(
        name: name,
        triggerType: trigger,
        toolName: toolName,
        toolArguments: argsText.isEmpty
            ? []
            : argsText.split(',').map((e) => e.trim()).toList(),
        enabled: enabled,
        description: desc,
        schedule: schedule,
      );
    } else {
      await notifier.updateAutomation(automation.id, {
        'name': name,
        if (desc != null) 'description': desc,
        'trigger_type': trigger,
        'tool_name': toolName,
        'tool_arguments': argsText.isEmpty
            ? []
            : argsText.split(',').map((e) => e.trim()).toList(),
        'enabled': enabled,
        if (schedule != null) 'schedule': schedule,
      });
    }

    if (mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(
              automation == null ? 'Automation created' : 'Automation updated'),
        ),
      );
    }
  }

  String? _formatSchedule(Map<String, dynamic>? schedule) {
    if (schedule == null) return null;
    return schedule['cron']?.toString() ?? schedule.toString();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(automationProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Automations'),
        actions: [
          IconButton(
            icon: const Icon(Icons.add),
            onPressed: () => _openDialog(),
            tooltip: 'Create automation',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _handleRefresh,
        child: state.isLoading && state.automations.isEmpty
            ? ListView(
                children: const [
                  SizedBox(height: 120),
                  Center(child: CircularProgressIndicator()),
                ],
              )
            : state.errorMessage != null && state.automations.isEmpty
                ? ListView(
                    children: [
                      const SizedBox(height: 120),
                      Center(
                        child: Column(
                          children: [
                            Icon(Icons.error_outline,
                                size: 48,
                                color: colorScheme.error),
                            const SizedBox(height: 16),
                            Text('Error loading automations',
                                style: theme.textTheme.bodyLarge),
                            const SizedBox(height: 8),
                            Text(state.errorMessage!,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                                )),
                            const SizedBox(height: 16),
                            FilledButton.icon(
                              onPressed: _handleRefresh,
                              icon: const Icon(Icons.refresh),
                              label: const Text('Retry'),
                            ),
                          ],
                        ),
                      ),
                    ],
                  )
                : state.automations.isEmpty
                    ? ListView(
                        children: [
                          const SizedBox(height: 120),
                          Center(
                            child: Column(
                              children: [
                                Icon(Icons.auto_awesome_mosaic_outlined,
                                    size: 48,
                                    color: colorScheme.onSurface.withValues(alpha: 0.3)),
                                const SizedBox(height: 16),
                                Text('No automations yet',
                                    style: theme.textTheme.bodyLarge?.copyWith(
                                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                                    )),
                                const SizedBox(height: 8),
                                TextButton.icon(
                                  onPressed: () => _openDialog(),
                                  icon: const Icon(Icons.add),
                                  label: const Text('Create your first automation'),
                                ),
                              ],
                            ),
                          ),
                        ],
                      )
                    : ListView.builder(
                        padding: const EdgeInsets.symmetric(vertical: 8),
                        itemCount: state.automations.length,
                        itemBuilder: (context, index) {
                          final automation = state.automations[index];
                          final isExecuting =
                              state.isExecuting && state.executingId == automation.id;
                          return _AutomationTile(
                            automation: automation,
                            isExecuting: isExecuting,
                            onTap: () => context.go(
                              '${AppRoutes.automationHistory}/${automation.id}',
                            ),
                            onToggle: (value) async {
                              await ref
                                  .read(automationProvider.notifier)
                                  .toggleAutomation(automation.id, value);
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  SnackBar(
                                    content: Text(value
                                        ? 'Automation enabled'
                                        : 'Automation disabled'),
                                  ),
                                );
                              }
                            },
                            onExecute: () async {
                              await ref
                                  .read(automationProvider.notifier)
                                  .executeAutomation(automation.id);
                              if (context.mounted) {
                                ScaffoldMessenger.of(context).showSnackBar(
                                  const SnackBar(
                                    content: Text('Execution triggered'),
                                  ),
                                );
                              }
                            },
                            onEdit: () => _openDialog(automation: automation),
                            onDelete: () async {
                              final confirm = await showDialog<bool>(
                                context: context,
                                builder: (ctx) => AlertDialog(
                                  title: const Text('Delete automation'),
                                  content: Text(
                                      'Delete "${automation.name}"? This cannot be undone.'),
                                  actions: [
                                    TextButton(
                                      onPressed: () => Navigator.of(ctx).pop(false),
                                      child: const Text('Cancel'),
                                    ),
                                    FilledButton(
                                      onPressed: () => Navigator.of(ctx).pop(true),
                                      style: FilledButton.styleFrom(
                                        backgroundColor: colorScheme.error,
                                      ),
                                      child: const Text('Delete'),
                                    ),
                                  ],
                                ),
                              );
                              if (confirm == true && mounted) {
                                await ref
                                    .read(automationProvider.notifier)
                                    .deleteAutomation(automation.id);
                                if (context.mounted) {
                                  ScaffoldMessenger.of(context).showSnackBar(
                                    const SnackBar(
                                        content: Text('Automation deleted')),
                                  );
                                }
                              }
                            },
                          );
                        },
                      ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () => _openDialog(),
        icon: const Icon(Icons.add),
        label: const Text('New automation'),
      ),
    );
  }
}

class _AutomationTile extends StatelessWidget {
  const _AutomationTile({
    required this.automation,
    required this.isExecuting,
    required this.onTap,
    required this.onToggle,
    required this.onExecute,
    required this.onEdit,
    required this.onDelete,
  });

  final Automation automation;
  final bool isExecuting;
  final VoidCallback onTap;
  final ValueChanged<bool> onToggle;
  final VoidCallback onExecute;
  final VoidCallback onEdit;
  final VoidCallback onDelete;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Dismissible(
      key: Key(automation.id),
      direction: DismissDirection.endToStart,
      background: Container(
        color: colorScheme.error,
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        child: Icon(Icons.delete, color: colorScheme.onError),
      ),
      confirmDismiss: (direction) async {
        return await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Delete automation'),
            content:
                Text('Delete "${automation.name}"? This cannot be undone.'),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(false),
                child: const Text('Cancel'),
              ),
              FilledButton(
                onPressed: () => Navigator.of(ctx).pop(true),
                style: FilledButton.styleFrom(backgroundColor: colorScheme.error),
                child: const Text('Delete'),
              ),
            ],
          ),
        );
      },
      onDismissed: (_) => onDelete(),
      child: Card(
        margin: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
        child: InkWell(
          onTap: onTap,
          borderRadius: BorderRadius.circular(12),
          child: Padding(
            padding: const EdgeInsets.all(12),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Expanded(
                      child: Column(
                        crossAxisAlignment: CrossAxisAlignment.start,
                        children: [
                          Text(
                            automation.name,
                            style: theme.textTheme.titleMedium?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                          if (automation.description != null &&
                              automation.description!.isNotEmpty)
                            Padding(
                              padding: const EdgeInsets.only(top: 2),
                              child: Text(
                                automation.description!,
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                                ),
                                maxLines: 1,
                                overflow: TextOverflow.ellipsis,
                              ),
                            ),
                        ],
                      ),
                    ),
                    Switch(
                      value: automation.enabled,
                      onChanged: onToggle,
                    ),
                  ],
                ),
                const SizedBox(height: 8),
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Chip(
                      label: Text(
                        automation.triggerType == 'scheduled' ? 'Scheduled' : 'Event',
                        style: const TextStyle(fontSize: 11),
                      ),
                      visualDensity: VisualDensity.compact,
                    ),
                    Chip(
                      label: Text(
                        automation.toolName,
                        style: const TextStyle(fontSize: 11),
                      ),
                      visualDensity: VisualDensity.compact,
                    ),
                    if (isExecuting)
                      const Chip(
                        label: Text(
                          'Running...',
                          style: TextStyle(fontSize: 11),
                        ),
                        visualDensity: VisualDensity.compact,
                        backgroundColor: Colors.lightBlueAccent,
                      ),
                  ],
                ),
                const SizedBox(height: 8),
                Row(
                  children: [
                    TextButton.icon(
                      onPressed: onExecute,
                      icon: const Icon(Icons.play_arrow, size: 18),
                      label: const Text('Run', style: TextStyle(fontSize: 12)),
                    ),
                    TextButton.icon(
                      onPressed: onEdit,
                      icon: const Icon(Icons.edit, size: 18),
                      label: const Text('Edit', style: TextStyle(fontSize: 12)),
                    ),
                    const Spacer(),
                    TextButton(
                      onPressed: onTap,
                      child: const Text('History'),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _AutomationDialog extends StatefulWidget {
  const _AutomationDialog({
    required this.nameController,
    required this.descController,
    required this.toolController,
    required this.argsController,
    required this.scheduleController,
    required this.trigger,
    required this.enabled,
    required this.onTriggerChanged,
    required this.onEnabledChanged,
  });

  final TextEditingController nameController;
  final TextEditingController descController;
  final TextEditingController toolController;
  final TextEditingController argsController;
  final TextEditingController scheduleController;
  final String trigger;
  final bool enabled;
  final ValueChanged<String> onTriggerChanged;
  final ValueChanged<bool> onEnabledChanged;

  @override
  State<_AutomationDialog> createState() => _AutomationDialogState();
}

class _AutomationDialogState extends State<_AutomationDialog> {
  bool get _isValid =>
      widget.nameController.text.trim().isNotEmpty &&
      widget.toolController.text.trim().isNotEmpty;

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.nameController.text.trim().isEmpty
          ? 'New automation'
          : 'Edit automation'),
      content: SingleChildScrollView(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: widget.nameController,
              decoration: const InputDecoration(
                labelText: 'Name',
                hintText: 'e.g. Daily backup',
              ),
              onChanged: (_) => setState(() {}),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: widget.descController,
              decoration: const InputDecoration(
                labelText: 'Description',
                hintText: 'Optional description',
              ),
            ),
            const SizedBox(height: 12),
            SegmentedButton<String>(
              segments: const [
                ButtonSegment(
                  value: 'scheduled',
                  label: Text('Scheduled'),
                  icon: Icon(Icons.schedule),
                ),
                ButtonSegment(
                  value: 'event',
                  label: Text('Event'),
                  icon: Icon(Icons.event),
                ),
              ],
              selected: {widget.trigger},
              onSelectionChanged: (value) {
                widget.onTriggerChanged(value.first);
              },
            ),
            const SizedBox(height: 12),
            if (widget.trigger == 'scheduled')
              TextField(
                controller: widget.scheduleController,
                decoration: const InputDecoration(
                  labelText: 'Schedule (cron)',
                  hintText: '0 9 * * *',
                ),
              ),
            const SizedBox(height: 12),
            TextField(
              controller: widget.toolController,
              decoration: const InputDecoration(
                labelText: 'Tool name',
                hintText: 'e.g. shell.exec',
              ),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: widget.argsController,
              decoration: const InputDecoration(
                labelText: 'Tool arguments',
                hintText: 'arg1, arg2, arg3',
              ),
            ),
            const SizedBox(height: 12),
            SwitchListTile(
              title: const Text('Enabled'),
              value: widget.enabled,
              onChanged: widget.onEnabledChanged,
              contentPadding: EdgeInsets.zero,
            ),
          ],
        ),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(false),
          child: const Text('Cancel'),
        ),
        FilledButton(
          onPressed: _isValid
              ? () => Navigator.of(context).pop(true)
              : null,
          child: Text(widget.nameController.text.trim().isEmpty
              ? 'Create'
              : 'Save'),
        ),
      ],
    );
  }
}
