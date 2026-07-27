import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class ProcessesPage extends ConsumerStatefulWidget {
  const ProcessesPage({super.key});

  @override
  ConsumerState<ProcessesPage> createState() => _ProcessesPageState();
}

class _ProcessesPageState extends ConsumerState<ProcessesPage> {
  String _searchQuery = '';
  String _sortBy = 'cpu_percent';
  bool _sortDesc = true;

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(systemMonitorProvider);
    final processes = state.snapshot?.processes ?? [];

    // Filter and sort locally
    var filtered = processes.where((p) {
      if (_searchQuery.isEmpty) return true;
      final name = (p['name'] as String?)?.toLowerCase() ?? '';
      final pid = (p['pid'] as int?)?.toString() ?? '';
      return name.contains(_searchQuery.toLowerCase()) || pid.contains(_searchQuery);
    }).toList();

    filtered.sort((a, b) {
      final aVal = (a[_sortBy] as num?)?.toDouble() ?? 0;
      final bVal = (b[_sortBy] as num?)?.toDouble() ?? 0;
      return _sortDesc ? bVal.compareTo(aVal) : aVal.compareTo(bVal);
    });

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: Column(children: [
          Padding(
            padding: const EdgeInsets.all(20),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Text('Processes', style: DashTypography.headlineMedium.copyWith(
                color: DashColors.pureWhite, fontWeight: FontWeight.w700,
              )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
              const SizedBox(height: 16),
              _buildSearchBar(),
              const SizedBox(height: 12),
              _buildSortRow(),
            ]),
          ),
          Expanded(
            child: ListView.builder(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              itemCount: filtered.length,
              itemBuilder: (context, i) => _buildProcessRow(filtered[i] as Map<String, dynamic>),
            ),
          ),
        ]),
      ),
    ]);
  }

  Widget _buildSearchBar() {
    return GlassPanel(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: TextField(
        style: const TextStyle(color: DashColors.pureWhite, fontSize: 14),
        decoration: const InputDecoration(
          hintText: 'Search processes...',
          hintStyle: TextStyle(color: DashColors.textGray, fontSize: 14),
          border: InputBorder.none,
          icon: Icon(Icons.search, color: DashColors.textGray, size: 20),
        ),
        onChanged: (v) => setState(() => _searchQuery = v),
      ),
    );
  }

  Widget _buildSortRow() {
    final sorts = [
      ('CPU', 'cpu_percent'),
      ('Memory', 'memory_percent'),
      ('Name', 'name'),
      ('PID', 'pid'),
    ];
    return SingleChildScrollView(
      scrollDirection: Axis.horizontal,
      child: Row(children: sorts.map((s) {
        final active = _sortBy == s.$2;
        return Padding(
          padding: const EdgeInsets.only(right: 8),
          child: GestureDetector(
            onTap: () => setState(() {
              if (_sortBy == s.$2) {
                _sortDesc = !_sortDesc;
              } else {
                _sortBy = s.$2;
                _sortDesc = true;
              }
            }),
            child: Container(
              padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
              decoration: BoxDecoration(
                color: active ? DashColors.electricBlue.withValues(alpha: 0.2) : DashColors.glassFrost,
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: active ? DashColors.electricBlue.withValues(alpha: 0.5) : Colors.transparent),
              ),
              child: Row(mainAxisSize: MainAxisSize.min, children: [
                Text(s.$1, style: TextStyle(color: active ? DashColors.electricBlue : DashColors.textGray, fontSize: 12, fontWeight: FontWeight.w500)),
                if (active) ...[
                  const SizedBox(width: 4),
                  Icon(_sortDesc ? Icons.arrow_downward : Icons.arrow_upward, color: DashColors.electricBlue, size: 12),
                ],
              ]),
            ),
          ),
        );
      }).toList()),
    );
  }

  Widget _buildProcessRow(Map<String, dynamic> proc) {
    final cpu = (proc['cpu_percent'] as num?)?.toDouble() ?? 0;
    final mem = (proc['memory_mb'] as num?)?.toDouble() ?? 0;
    final name = proc['name']?.toString() ?? 'unknown';
    final pid = proc['pid'] as int? ?? 0;
    final status = proc['status']?.toString() ?? '';

    return GlassPanel(
      margin: const EdgeInsets.only(bottom: 8),
      padding: const EdgeInsets.all(12),
      child: Row(children: [
        Expanded(
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text(name, style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500), maxLines: 1, overflow: TextOverflow.ellipsis),
            const SizedBox(height: 2),
            Text('PID: $pid', style: const TextStyle(color: DashColors.textDim, fontSize: 10)),
          ]),
        ),
        const SizedBox(width: 12),
        Column(crossAxisAlignment: CrossAxisAlignment.end, children: [
          Text('${cpu.toStringAsFixed(1)}%', style: TextStyle(color: cpu > 50 ? DashColors.warningAmber : DashColors.electricBlue, fontSize: 12, fontWeight: FontWeight.w600)),
          Text('${mem.toStringAsFixed(0)} MB', style: const TextStyle(color: DashColors.textGray, fontSize: 10)),
        ]),
        const SizedBox(width: 8),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
          decoration: BoxDecoration(
            color: status == 'running' ? DashColors.energyGreen.withValues(alpha: 0.15) : DashColors.glassFrost,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Text(status, style: TextStyle(color: status == 'running' ? DashColors.energyGreen : DashColors.textGray, fontSize: 9, fontWeight: FontWeight.w500)),
        ),
      ]),
    ).animate().fadeIn(duration: 300.ms);
  }
}