import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class RamPage extends ConsumerWidget {
  const RamPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('RAM Monitor', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 24),
            _buildUsageGauge(snap),
            const SizedBox(height: 20),
            _buildMemoryDetails(snap),
            const SizedBox(height: 20),
            _buildSwapInfo(snap),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildUsageGauge(SystemSnapshot? snap) {
    final pct = snap?.ramPercent ?? 0;
    final used = snap?.ramUsedGb ?? 0;
    final total = snap?.ramTotalGb ?? 0;
    final color = pct > 80 ? DashColors.errorRed : pct > 50 ? DashColors.warningAmber : DashColors.electricBlue;

    return GlassPanel(
      padding: const EdgeInsets.all(24),
      child: Column(children: [
        SizedBox(
          width: 160, height: 160,
          child: Stack(alignment: Alignment.center, children: [
            CircularProgressIndicator(
              value: pct / 100,
              strokeWidth: 12,
              backgroundColor: DashColors.glassFrost,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
            Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('${pct.toStringAsFixed(0)}%', style: TextStyle(color: color, fontSize: 36, fontWeight: FontWeight.w700)),
              const Text('RAM Usage', style: TextStyle(color: DashColors.textGray, fontSize: 12)),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        Text('${used.toStringAsFixed(1)} / ${total.toStringAsFixed(1)} GB',
          style: const TextStyle(color: DashColors.pureWhite, fontSize: 18, fontWeight: FontWeight.w600)),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildMemoryDetails(SystemSnapshot? snap) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Memory Details', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('Total', '${snap?.ramTotalGb?.toStringAsFixed(1) ?? '--'} GB'),
        _buildRow('Used', '${snap?.ramUsedGb?.toStringAsFixed(1) ?? '--'} GB'),
        _buildRow('Free', '${snap?.ramFreeGb?.toStringAsFixed(1) ?? '--'} GB'),
        _buildRow('Cached', '${snap?.ramCachedGb?.toStringAsFixed(1) ?? '--'} GB'),
        _buildRow('Committed', '${snap?.ramCommittedGb?.toStringAsFixed(1) ?? '--'} GB'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _buildSwapInfo(SystemSnapshot? snap) {
    final swapPct = snap?.swapPercent ?? 0;
    final swapUsed = snap?.swapUsedGb ?? 0;
    final swapTotal = snap?.swapTotalGb ?? 0;
    if (swapTotal == 0) return const SizedBox.shrink();

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Swap', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('${swapUsed.toStringAsFixed(1)} / ${swapTotal.toStringAsFixed(1)} GB',
            style: const TextStyle(color: DashColors.pureWhite, fontSize: 16, fontWeight: FontWeight.w600)),
          Text('${swapPct.toStringAsFixed(0)}%', style: TextStyle(color: swapPct > 50 ? DashColors.warningAmber : DashColors.textGray, fontSize: 14)),
        ]),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: swapPct / 100, minHeight: 6,
            backgroundColor: DashColors.glassFrost,
            valueColor: AlwaysStoppedAnimation<Color>(swapPct > 50 ? DashColors.warningAmber : DashColors.electricBlue),
          ),
        ),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
        Text(value, style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500)),
      ]),
    );
  }
}