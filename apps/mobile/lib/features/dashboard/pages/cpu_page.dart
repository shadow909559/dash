import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class CpuPage extends ConsumerWidget {
  const CpuPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    final cpu = snap?.cpu ?? {};

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('CPU Monitor', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 8),
            Text('Real-time CPU metrics from desktop',
              style: DashTypography.bodyLarge.copyWith(color: DashColors.textGray),
            ).animate().fadeIn(duration: 400.ms, delay: 200.ms),
            const SizedBox(height: 24),

            // Usage gauge
            _buildUsageGauge(snap),
            const SizedBox(height: 20),

            // Per-core usage
            _buildPerCoreUsage(cpu),
            const SizedBox(height: 20),

            // Details grid
            _buildDetailsGrid(cpu, snap),
            const SizedBox(height: 20),

            // Frequency info
            _buildFrequencyCard(cpu),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildUsageGauge(SystemSnapshot? snap) {
    final pct = snap?.cpuPercent ?? 0;
    final temp = snap?.cpuTemp;
    final freq = snap?.cpuFreq;
    final color = pct > 80 ? DashColors.errorRed : pct > 50 ? DashColors.warningAmber : DashColors.energyGreen;

    return GlassPanel(
      padding: const EdgeInsets.all(24),
      child: Column(children: [
        SizedBox(
          width: 160, height: 160,
          child: Stack(alignment: Alignment.center, children: [
            SizedBox(
              width: 160, height: 160,
              child: CircularProgressIndicator(
                value: pct / 100,
                strokeWidth: 12,
                backgroundColor: DashColors.glassFrost,
                valueColor: AlwaysStoppedAnimation<Color>(color),
              ),
            ),
            Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('${pct.toStringAsFixed(0)}%', style: TextStyle(
                color: color, fontSize: 36, fontWeight: FontWeight.w700,
              )),
              Text('CPU Usage', style: TextStyle(color: DashColors.textGray, fontSize: 12)),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          if (freq != null) _buildStat('Frequency', '${freq.toStringAsFixed(0)} MHz'),
          if (temp != null) _buildStat('Temperature', '${temp.toStringAsFixed(1)}°C'),
        ]),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildStat(String label, String value) {
    return Column(children: [
      Text(value, style: const TextStyle(color: DashColors.pureWhite, fontSize: 16, fontWeight: FontWeight.w600)),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
    ]);
  }

  Widget _buildPerCoreUsage(Map<String, dynamic> cpu) {
    final perCore = cpu['percent_per_core'] as List<dynamic>? ?? [];
    if (perCore.isEmpty) return const SizedBox.shrink();

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Per-Core Usage', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        ...List.generate(perCore.length, (i) {
          final corePct = (perCore[i] as num?)?.toDouble() ?? 0;
          final color = corePct > 80 ? DashColors.errorRed : corePct > 50 ? DashColors.warningAmber : DashColors.energyGreen;
          return Padding(
            padding: const EdgeInsets.only(bottom: 8),
            child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
              Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
                Text('Core $i', style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
                Text('${corePct.toStringAsFixed(0)}%', style: TextStyle(color: color, fontSize: 12, fontWeight: FontWeight.w600)),
              ]),
              const SizedBox(height: 4),
              ClipRRect(
                borderRadius: BorderRadius.circular(3),
                child: LinearProgressIndicator(
                  value: corePct / 100, minHeight: 6,
                  backgroundColor: DashColors.glassFrost,
                  valueColor: AlwaysStoppedAnimation<Color>(color),
                ),
              ),
            ]),
          );
        }),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _buildDetailsGrid(Map<String, dynamic> cpu, SystemSnapshot? snap) {
    final items = [
      ('Physical Cores', '${snap?.coresPhysical ?? '--'}'),
      ('Logical Cores', '${snap?.coresLogical ?? '--'}'),
      ('Brand', snap?.cpuBrand ?? '--'),
      ('Architecture', cpu['architecture']?.toString() ?? '--'),
      ('Voltage', cpu['voltage'] != null ? '${cpu['voltage']} V' : 'N/A'),
    ];

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('CPU Details', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        ...items.map((item) => Padding(
          padding: const EdgeInsets.only(bottom: 12),
          child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
            Text(item.$1, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
            Text(item.$2, style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500)),
          ]),
        )),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _buildFrequencyCard(Map<String, dynamic> cpu) {
    final current = cpu['frequency_current_mhz'];
    final maxFreq = cpu['frequency_max_mhz'];
    final minFreq = cpu['frequency_min_mhz'];

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Frequency', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        Row(children: [
          Expanded(child: _buildFreqItem('Current', current != null ? '${current.toStringAsFixed(0)} MHz' : '--', DashColors.electricBlue)),
          Expanded(child: _buildFreqItem('Max', maxFreq != null ? '${maxFreq.toStringAsFixed(0)} MHz' : '--', DashColors.purpleGlow)),
          Expanded(child: _buildFreqItem('Min', minFreq != null ? '${minFreq.toStringAsFixed(0)} MHz' : '--', DashColors.textGray)),
        ]),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 400.ms);
  }

  Widget _buildFreqItem(String label, String value, Color color) {
    return Column(children: [
      Text(value, style: TextStyle(color: color, fontSize: 14, fontWeight: FontWeight.w600)),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 11)),
    ]);
  }
}