import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class SystemInfoPage extends ConsumerWidget {
  const SystemInfoPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    final sys = snap?.system ?? {};

    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.2),
      SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20),
          child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('System', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 24),
            _buildOsInfo(sys),
            const SizedBox(height: 12),
            _buildSystemInfo(sys),
            const SizedBox(height: 12),
            _buildUptimeInfo(sys),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildOsInfo(Map<String, dynamic> sys) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Operating System', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('OS', sys['os']?.toString() ?? '--'),
        _buildRow('Version', sys['os_version']?.toString() ?? '--'),
        _buildRow('Build', sys['os_build']?.toString() ?? '--'),
        _buildRow('Architecture', sys['architecture']?.toString() ?? '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildSystemInfo(Map<String, dynamic> sys) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('System', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('Hostname', sys['hostname']?.toString() ?? '--'),
        _buildRow('Username', sys['username']?.toString() ?? '--'),
        _buildRow('Platform', sys['platform']?.toString() ?? '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _buildUptimeInfo(Map<String, dynamic> sys) {
    final bootTime = sys['boot_time'];
    String bootTimeStr = '--';
    if (bootTime != null) {
      final bootMs = (bootTime as num) * 1000;
      bootTimeStr = DateTime.fromMillisecondsSinceEpoch(bootMs.toInt()).toString().substring(0, 19);
    }

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Uptime', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('Uptime', sys['uptime_formatted']?.toString() ?? '--'),
        _buildRow('Boot Time', bootTimeStr),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.spaceBetween,
        children: [
          Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
          Flexible(
            child: Text(
              value,
              style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500),
              textAlign: TextAlign.right,
            ),
          ),
        ],
      ),
    );
  }
}