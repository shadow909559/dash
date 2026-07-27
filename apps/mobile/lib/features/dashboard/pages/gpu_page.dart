import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class GpuPage extends ConsumerWidget {
  const GpuPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    final gpuList = snap?.gpu ?? [];
    final gpu = gpuList.isNotEmpty ? gpuList.first : <String, dynamic>{};

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('GPU Monitor', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 8),
            Text(gpu['name']?.toString() ?? 'No GPU detected',
              style: DashTypography.bodyLarge.copyWith(color: DashColors.textGray),
            ).animate().fadeIn(duration: 400.ms, delay: 200.ms),
            const SizedBox(height: 24),
            _buildUsageGauge(gpu, snap),
            const SizedBox(height: 20),
            _buildVramCard(gpu),
            const SizedBox(height: 20),
            _buildDetailsGrid(gpu),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildUsageGauge(Map<String, dynamic> gpu, SystemSnapshot? snap) {
    final usage = snap?.gpuUsage ?? 0;
    final temp = snap?.gpuTemp;
    final color = usage > 80 ? DashColors.errorRed : usage > 50 ? DashColors.warningAmber : DashColors.purpleGlow;

    return GlassPanel(
      padding: const EdgeInsets.all(24),
      child: Column(children: [
        SizedBox(
          width: 160, height: 160,
          child: Stack(alignment: Alignment.center, children: [
            CircularProgressIndicator(
              value: usage / 100,
              strokeWidth: 12,
              backgroundColor: DashColors.glassFrost,
              valueColor: AlwaysStoppedAnimation<Color>(color),
            ),
            Column(mainAxisAlignment: MainAxisAlignment.center, children: [
              Text('${usage.toStringAsFixed(0)}%', style: TextStyle(
                color: color, fontSize: 36, fontWeight: FontWeight.w700,
              )),
              const Text('GPU Usage', style: TextStyle(color: DashColors.textGray, fontSize: 12)),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        Row(mainAxisAlignment: MainAxisAlignment.spaceEvenly, children: [
          if (temp != null) _buildStat('Temperature', '${temp.toStringAsFixed(1)}°C'),
          if (gpu['power_draw_watts'] != null)
            _buildStat('Power', '${gpu['power_draw_watts']} W'),
          if (gpu['fan_speed_percent'] != null)
            _buildStat('Fan', '${gpu['fan_speed_percent']}%'),
        ]),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildStat(String label, String value) {
    return Column(children: [
      Text(value, style: const TextStyle(color: DashColors.pureWhite, fontSize: 14, fontWeight: FontWeight.w600)),
      const SizedBox(height: 4),
      Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 11)),
    ]);
  }

  Widget _buildVramCard(Map<String, dynamic> gpu) {
    final vramUsed = gpu['vram_used_mb']?.toDouble();
    final vramTotal = gpu['vram_total_mb']?.toDouble();
    if (vramUsed == null || vramTotal == null || vramTotal == 0) return const SizedBox.shrink();

    final pct = vramUsed / vramTotal;
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('VRAM', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 12),
        Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
          Text(
            '${(vramUsed / 1024).toStringAsFixed(1)} / ${(vramTotal / 1024).toStringAsFixed(1)} GB',
            style: const TextStyle(color: DashColors.pureWhite, fontSize: 16, fontWeight: FontWeight.w600),
          ),
          Text(
            '${(pct * 100).toStringAsFixed(0)}%',
            style: TextStyle(color: pct > 0.8 ? DashColors.errorRed : DashColors.electricBlue, fontSize: 14),
          ),
        ]),
        const SizedBox(height: 8),
        ClipRRect(
          borderRadius: BorderRadius.circular(4),
          child: LinearProgressIndicator(
            value: pct.clamp(0.0, 1.0), minHeight: 6,
            backgroundColor: DashColors.glassFrost,
            valueColor: AlwaysStoppedAnimation<Color>(pct > 0.8 ? DashColors.errorRed : DashColors.electricBlue),
          ),
        ),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _buildDetailsGrid(Map<String, dynamic> gpu) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('GPU Details', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildDetailRow('Driver', gpu['driver_version']?.toString() ?? '--'),
        _buildDetailRow('VRAM Total', gpu['vram_total_mb'] != null ? '${(gpu['vram_total_mb'] as num / 1024).toStringAsFixed(1)} GB' : '--'),
        _buildDetailRow('Memory', gpu['memory_total_mb'] != null ? '${(gpu['memory_total_mb'] as num / 1024).toStringAsFixed(1)} GB' : '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _buildDetailRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
        Text(value, style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500)),
      ]),
    );
  }
}