import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:intl/intl.dart';

import '../planner/providers/planner_provider.dart';

class CalendarPage extends ConsumerStatefulWidget {
  const CalendarPage({super.key});

  @override
  ConsumerState<CalendarPage> createState() => _CalendarPageState();
}

class _CalendarPageState extends ConsumerState<CalendarPage> {
  late DateTime _focusedMonth;

  @override
  void initState() {
    super.initState();
    _focusedMonth = DateTime.now();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final plannerState = ref.watch(plannerProvider);

    final firstDay = DateTime(_focusedMonth.year, _focusedMonth.month, 1);
    final daysInMonth = DateTime(_focusedMonth.year, _focusedMonth.month + 1, 0).day;
    final startWeekday = firstDay.weekday % 7;

    final eventDays = <int, List<String>>{};
    final today = DateTime.now();
    for (final task in plannerState.tasks) {
      final day = task.createdAt;
      if (day.year == _focusedMonth.year && day.month == _focusedMonth.month) {
        final key = day.day;
        eventDays.putIfAbsent(key, () => []).add(task.name);
      }
    }
    for (final goal in plannerState.goals) {
      final day = goal.createdAt;
      if (day.year == _focusedMonth.year && day.month == _focusedMonth.month) {
        final key = day.day;
        eventDays.putIfAbsent(key, () => []).add(goal.name);
      }
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(plannerProvider.notifier).loadDashboard(refresh: true),
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text(
            'Calendar',
            style: theme.textTheme.headlineMedium?.copyWith(fontWeight: FontWeight.bold),
          ),
          const SizedBox(height: 4),
          Text(
            'View tasks and goals by date',
            style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)),
          ),
          const SizedBox(height: 24),
          Card(
            child: Padding(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 16),
              child: Row(
                children: [
                  IconButton(onPressed: () {
                    setState(() {
                      _focusedMonth = DateTime(_focusedMonth.year, _focusedMonth.month - 1);
                    });
                  }, icon: const Icon(Icons.chevron_left)),
                  Expanded(
                    child: Text(
                      DateFormat.yMMMM().format(_focusedMonth),
                      textAlign: TextAlign.center,
                      style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600),
                    ),
                  ),
                  IconButton(onPressed: () {
                    setState(() {
                      _focusedMonth = DateTime(_focusedMonth.year, _focusedMonth.month + 1);
                    });
                  }, icon: const Icon(Icons.chevron_right)),
                ],
              ),
            ),
          ),
          const SizedBox(height: 16),
          Row(
            children: const ['Su', 'Mo', 'Tu', 'We', 'Th', 'Fr', 'Sa'].map((d) {
              return Expanded(
                child: Center(
                  child: Text(d, style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Colors.grey)),
                ),
              );
            }).toList(),
          ),
          const SizedBox(height: 8),
          GridView.count(
            shrinkWrap: true,
            physics: const NeverScrollableScrollPhysics(),
            crossAxisCount: 7,
            childAspectRatio: 1.0,
            padding: EdgeInsets.zero,
            children: List.generate(startWeekday + daysInMonth, (index) {
              if (index < startWeekday) return const SizedBox.shrink();
              final day = index - startWeekday + 1;
              final isToday = today.year == _focusedMonth.year && today.month == _focusedMonth.month && today.day == day;
              final hasEvents = eventDays.containsKey(day);
              return GestureDetector(
                onTap: () => _showDayDetails(context, day),
                child: Container(
                  margin: const EdgeInsets.all(4),
                  decoration: BoxDecoration(
                    color: isToday ? colorScheme.primaryContainer : null,
                    borderRadius: BorderRadius.circular(12),
                  ),
                  child: Column(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: [
                      Text(
                        '$day',
                        style: TextStyle(
                          fontWeight: isToday ? FontWeight.bold : FontWeight.normal,
                          color: isToday ? colorScheme.onPrimaryContainer : null,
                        ),
                      ),
                      if (hasEvents)
                        Row(
                          mainAxisAlignment: MainAxisAlignment.center,
                          children: List.generate(eventDays[day]!.length.clamp(0, 3), (i) {
                            return Container(
                              width: 6,
                              height: 6,
                              margin: const EdgeInsets.symmetric(horizontal: 1),
                              decoration: BoxDecoration(color: colorScheme.primary, shape: BoxShape.circle),
                            );
                          }),
                        ),
                    ],
                  ),
                ),
              );
            }),
          ),
          const SizedBox(height: 24),
          Row(
            children: [
              Container(width: 10, height: 10, decoration: BoxDecoration(color: colorScheme.primary, shape: BoxShape.circle)),
              const SizedBox(width: 8),
              Text('Task or goal created', style: theme.textTheme.bodySmall),
            ],
          ),
          if (plannerState.tasks.isEmpty && plannerState.goals.isEmpty)
            Padding(
              padding: const EdgeInsets.only(top: 32),
              child: Column(
                children: [
                  Icon(Icons.calendar_month_outlined, size: 48, color: colorScheme.onSurface.withValues(alpha: 0.2)),
                  const SizedBox(height: 16),
                  Text('No events yet', style: theme.textTheme.titleMedium),
                  const SizedBox(height: 8),
                  Text('Create goals and tasks to see them here', style: theme.textTheme.bodySmall),
                ],
              ),
            ),
        ],
      ),
    );
  }

  void _showDayDetails(BuildContext context, int day) {
    final plannerState = ref.read(plannerProvider);
    final tasks = plannerState.tasks.where((t) {
      return t.createdAt.year == _focusedMonth.year &&
          t.createdAt.month == _focusedMonth.month &&
          t.createdAt.day == day;
    }).toList();
    final goals = plannerState.goals.where((g) {
      return g.createdAt.year == _focusedMonth.year &&
          g.createdAt.month == _focusedMonth.month &&
          g.createdAt.day == day;
    }).toList();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: Text('${_focusedMonth.month}/$day'),
        content: SingleChildScrollView(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            mainAxisSize: MainAxisSize.min,
            children: [
              if (goals.isNotEmpty) ...[
                Text('Goals', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                ...goals.map((g) => Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('• ${g.name}'))),
              ],
              if (tasks.isNotEmpty) ...[
                if (goals.isNotEmpty) const SizedBox(height: 16),
                Text('Tasks', style: Theme.of(context).textTheme.titleSmall),
                const SizedBox(height: 8),
                ...tasks.map((t) => Padding(padding: const EdgeInsets.symmetric(vertical: 4), child: Text('• ${t.name}'))),
              ],
              if (goals.isEmpty && tasks.isEmpty)
                const Text('No events on this day'),
            ],
          ),
        ),
        actions: [TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Close'))],
      ),
    );
  }
}