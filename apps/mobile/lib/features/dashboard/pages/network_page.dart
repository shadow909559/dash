import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../../core/theme/dash_theme.dart';
import '../../../core/widgets/glassmorphism.dart';
import '../../../core/widgets/animated_background.dart';
import '../system_monitor_service.dart';

class NetworkPage extends ConsumerWidget {
  const NetworkPage({super.key});

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
            Text('Network', style: DashTypography.headlineMedium.copyWith(
              color: DashColors.pureWhite, fontWeight: FontWeight.w700,
            )).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0),
            const SizedBox(height: 24),
            _buildSpeedCards(snap),
            const SizedBox(height: 20),
            _buildConnectionInfo(snap),
            const SizedBox(height: 20),
            _buildDetails(snap),
          ]),
        ),
      ),
    ]);
  }

  Widget _buildSpeedCards(SystemSnapshot? snap) {
    return Row(children: [
      Expanded(child: _buildSpeedCard('Download', snap?.downloadSpeedMbps ?? 0, Icons.arrow_downward, DashColors.energyGreen)),
      const SizedBox(width: 12),
      Expanded(child: _buildSpeedCard('Upload', snap?.uploadSpeedMbps ?? 0, Icons.arrow_upward, DashColors.electricBlue)),
    ]).animate().fadeIn(duration: 500.ms);
  }

  Widget _buildSpeedCard(String label, double speed, IconData icon, Color color) {
    return GlassPanel(
      padding: const EdgeInsets.all(16),
      child: Column(children: [
        Icon(icon, color: color, size: 24),
        const SizedBox(height: 8),
        Text('${speed.toStringAsFixed(1)}', style: TextStyle(color: color, fontSize: 24, fontWeight: FontWeight.w700)),
        Text('Mbps', style: const TextStyle(color: DashColors.textGray, fontSize: 11)),
        const SizedBox(height: 4),
        Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
      ]),
    );
  }

  Widget _buildConnectionInfo(SystemSnapshot? snap) {
    final latency = snap?.latencyMs;
    final wifiName = snap?.wifiName;
    final signal = snap?.signalStrength;
    final ethernet = snap?.ethernetConnected;

    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Connection', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('Latency', latency != null ? '${latency.toStringAsFixed(0)} ms' : '--'),
        _buildRow('WiFi', wifiName ?? '--'),
        if (signal != null) _buildRow('Signal', '$signal%'),
        _buildRow('Ethernet', ethernet == true ? 'Connected' : ethernet == false ? 'Disconnected' : '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 200.ms);
  }

  Widget _buildDetails(SystemSnapshot? snap) {
    return GlassPanel(
      padding: const EdgeInsets.all(20),
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Network Details', style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600)),
        const SizedBox(height: 16),
        _buildRow('IP Address', snap?.ipAddress ?? '--'),
        _buildRow('Gateway', snap?.gateway ?? '--'),
        _buildRow('DNS', snap?.dnsServers.isNotEmpty == true ? snap!.dnsServers.join(', ') : '--'),
        _buildRow('Hostname', snap?.hostname ?? '--'),
      ]),
    ).animate().fadeIn(duration: 500.ms, delay: 300.ms);
  }

  Widget _buildRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
        Flexible(child: Text(value, style: const TextStyle(color: DashColors.pureWhite, fontSize: 13, fontWeight: FontWeight.w500), textAlign: TextAlign.right)),
      ]),
    );
  }
}