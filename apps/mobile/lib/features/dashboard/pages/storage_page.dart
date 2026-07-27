import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class StoragePage extends ConsumerWidget {
  const StoragePage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    final drives = snap?.storageDrives ?? [];

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('Storage', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 24),
            _buildOverview(snap),
            const SizedBox(height: 20),
            ...drives.map((drive) => Padding(
              padding: const EdgeInsets.only(bottom: 12),
              child: _buildDriveCard(drive as Map<String, dynamic>),
            )),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildOverview(SystemSnapshot? snap) {
    final used = snap?.storageUsedGb ?? 0;
    final total = snap?.storageTotalGb ?? 0;
    final pct = total > 0 ? used / total : 0.0;

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Total Storage', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('${used.toStringAsFixed(0)} / ${total.toStringAsFixed(0)} GB',
            style: const TextStyle(color: DashColors.pureWhite, fontSize: 18, fontWeight: FontWeight.w600)),
          Text('${(pct * 100).toStringAsFixed(0)}%', style: TextStyle(color: pct > 0.8 ? DashColors.errorRed : DashColors.energyGreen, fontSize: 14)),
        ]),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: pct.clamp(0.0, 1.0), minHeight: 8,
            backgroundColor: DashColors.glassFrost,
            valueColor: AlwaysStoppedAnimation<Color>(pct > 0.8 ? DashColors.errorRed : DashColors.energyGreen),
          ),
        ),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildDriveCard(Map<String, dynamic> drive) {
    final pct = (drive['percent'] as num?)?.toDouble() ?? 0;
    final type = drive['drive_type']?.toString() ?? 'unknown';
    final health = drive['health'] as Map<String, dynamic>?;
    final isHealthy = health?['healthy'] as bool?;

    return GlassPanel(
      padding: const EdgeInsets.all(16),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        Row(children: [
          Icon(type == 'ssd' ? Icons.memory : Icons.storage, color: DashColors.electricBlue, size: 20),
          const SizedBox(width: 8),
          Expanded(child: Text(drive['mountpoint']?.toString() ?? '', style: const TextStyle(color: DashColors.pureWhite, fontSize: 14, fontWeight: FontWeight.w600))),
          if (health != null)
            Container(
              padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
              decoration: BoxDecoration(
                color: (isHealthy == true ? DashColors.energyGreen : DashColors.errorRed).withValues(alpha: 0.15),
                borderRadius: BorderRadius.circular(8),
              ),
              child: Text(isHealthy == true ? 'OK' : 'BAD', style: TextStyle(color: isHealthy == true ? DashColors.energyGreen : DashColors.errorRed, fontSize: 10, fontWeight: FontWeight.w600)),
            ),
        ]),
        const SizedBox(height: 8),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text('${drive['used_gb']} / ${drive['total_gb']} GB', style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
          Text('${pct.toStringAsFixed(0)}%', style: TextStyle(color: pct > 80 ? DashColors.errorRed : DashColors.textGray, fontSize: 12)),
        ]),
        const SizedBox(height: 6),
        ClipRRect(
          borderRadius: BorderRadius.circular(3),
          child: LinearProgressIndicator(
            value: pct / 100, minHeight: 4,
            backgroundColor: DashColors.glassFrost,
            valueColor: AlwaysStoppedAnimation<Color>(pct > 80 ? DashColors.errorRed : DashColors.electricBlue),
          ),
        ),
        const SizedBox(height: 4),
        Row(children: [
          Text(drive['fstype']?.toString() ?? '', style: const TextStyle(color: DashColors.textDim, fontSize: 10)),
          const SizedBox(width: 8),
          Text(type.toUpperCase(), style: const TextStyle(color: DashColors.textDim, fontSize: 10)),
        ]),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }
}