import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class BatteryPage extends ConsumerWidget {
  const BatteryPage({super.key});

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
            Text('Battery', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 24),
            _buildBatteryGauge(snap),
            const SizedBox(height: 20),
            _buildDetails(snap),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildBatteryGauge(SystemSnapshot? snap) {
    final pct = snap?.batteryPercent ?? 0;
    final charging = snap?.batteryCharging ?? false;
    final health = snap?.batteryHealth;
    final color = pct > 20 ? DashColors.energyGreen : DashColors.errorRed;

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
              Text(charging ? 'Charging' : 'Discharging', style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
            ]),
          ]),
        ),
        const SizedBox(height: 16),
        if (health != null)
          Text('Health: ${health.toStringAsFixed(0)}%', style: const TextStyle(color: DashColors.pureWhite, fontSize: 14)),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildDetails(SystemSnapshot? snap) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Battery Details', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('Status', snap?.batteryStatus ?? '--'),
        _buildRow('Manufacturer', snap?.batteryManufacturer ?? '--'),
        _buildRow('Design Capacity', snap?.designCapacityWh != null ? '${snap!.designCapacityWh!.toStringAsFixed(0)} Wh' : '--'),
        _buildRow('Full Charge', snap?.fullChargeCapacityWh != null ? '${snap!.fullChargeCapacityWh!.toStringAsFixed(0)} Wh' : '--'),
        _buildRow('Health', snap?.batteryHealth != null ? '${snap!.batteryHealth!.toStringAsFixed(0)}%' : '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
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