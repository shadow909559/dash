import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/dash_theme.dart';
import '../../core/widgets/glassmorphism.dart';
import '../../core/widgets/ai_core.dart';
import '../../core/widgets/animated_background.dart';
import 'system_monitor_service.dart';

// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
// PRIVATE UI COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class _StatusBadge extends StatelessWidget {
  final String label;
  final Color color;
  const _StatusBadge({required this.label, required this.color});
  @override
  Widget build(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.1),
        borderRadius: BorderRadius.circular(20),
        border: Border.all(color: color.withValues(alpha: 0.3)),
      ),
      child: Row(mainAxisSize: MainAxisSize.min, children: [
        Container(width: 6, height: 6, decoration: BoxDecoration(
          color: color, shape: BoxShape.circle,
          boxShadow: [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 4)],
        )),
        const SizedBox(width: 6),
        Text(label, style: TextStyle(color: color, fontSize: 11, fontWeight: FontWeight.w500)),
      ]),
    );
  }
}

class _QuickActionCard extends StatelessWidget {
  final IconData icon; final String label; final String description;
  final LinearGradient gradient; final VoidCallback onTap;
  const _QuickActionCard({
    required this.icon, required this.label, required this.description,
    required this.gradient, required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    return GlassCard(
      padding: const EdgeInsets.all(16),
      onTap: onTap,
      child: Column(crossAxisAlignment: CrossAxisAlignment.start, mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Container(
            width: 40, height: 40,
            decoration: BoxDecoration(
              gradient: gradient, borderRadius: BorderRadius.circular(12),
              boxShadow: [BoxShadow(color: gradient.colors.first.withValues(alpha: 0.3), blurRadius: 8)],
            ),
            child: Icon(icon, color: DashColors.pureWhite, size: 20),
          ),
          const SizedBox(height: 12),
          Text(label, style: const TextStyle(color: DashColors.pureWhite, fontSize: 15, fontWeight: FontWeight.w600)),
          const SizedBox(height: 2),
          Text(description, style: const TextStyle(color: DashColors.textGray, fontSize: 12)),
        ],
      ),
    );
  }
}

class _MetricRow extends StatelessWidget {
  final String label; final String value; final double progress; final Color color;
  const _MetricRow({required this.label, required this.value, required this.progress, required this.color});
  @override
  Widget build(BuildContext context) {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 13)),
        Text(value, style: TextStyle(color: color, fontSize: 13, fontWeight: FontWeight.w600)),
      ]),
      const SizedBox(height: 6),
      ClipRRect(
        borderRadius: BorderRadius.circular(4),
        child: LinearProgressIndicator(
          value: progress.clamp(0.0, 1.0), minHeight: 4,
          backgroundColor: DashColors.glassFrost,
          valueColor: AlwaysStoppedAnimation<Color>(color),
        ),
      ),
    ]);
  }
}

class _LiveMetricWidget extends ConsumerWidget {
  final String label;
  final String Function(SystemSnapshot? snap) valueBuilder;
  final double Function(SystemSnapshot? snap) progressBuilder;
  final Color color;

  const _LiveMetricWidget({
    required this.label,
    required this.valueBuilder,
    required this.progressBuilder,
    required this.color,
  });

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    return _MetricRow(
      label: label,
      value: valueBuilder(snap),
      progress: progressBuilder(snap),
      color: color,
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
// DASH AI COMMAND CENTER — DASHBOARD
// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class DashboardPage extends ConsumerStatefulWidget {
  const DashboardPage({super.key});
  @override
  ConsumerState<DashboardPage> createState() => _DashboardPageState();
}

class _DashboardPageState extends ConsumerState<DashboardPage> with SingleTickerProviderStateMixin {
  late AnimationController _glowController;

  @override
  void initState() {
    super.initState();
    _glowController = AnimationController(duration: const Duration(seconds: 4), vsync: this)..repeat(reverse: true);
    // Connect to system monitor on init
    Future.microtask(() {
      ref.read(systemMonitorProvider.notifier).connect();
    });
  }

  @override
  void dispose() {
    _glowController.dispose();
    ref.read(systemMonitorProvider.notifier).disconnect();
    super.dispose();
  }

  Color _pulseColor() {
    final t = _glowController.value;
    return Color.lerp(DashColors.electricBlue, DashColors.purpleGlow, t)!;
  }

  @override
  Widget build(BuildContext context) {
    return Stack(children: [
      const AnimatedBackground(type: BackgroundType.neuralGrid, opacity: 0.25),
      SafeArea(child: SingleChildScrollView(
        padding: const EdgeInsets.all(20),
        child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
          _buildHeader(),
          const SizedBox(height: 24),
          _buildAICoreStatus(),
          const SizedBox(height: 24),
          _buildQuickActions(),
          const SizedBox(height: 24),
          _buildSystemStatus(),
          const SizedBox(height: 24),
          _buildRecentActivity(),
        ]),
      )),
    ]);
  }

  Widget _buildHeader() {
    final state = ref.watch(systemMonitorProvider);
    final isLive = state.status == SystemMonitorStatus.connected;
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(children: [
        Expanded(
          child: Text('AI Command Center',
            style: DashTypography.headlineMedium.copyWith(color: DashColors.pureWhite, fontWeight: FontWeight.w700),
          ).animate().fadeIn(duration: 400.ms).slideX(begin: -20, end: 0, duration: 400.ms),
        ),
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
          decoration: BoxDecoration(
            color: (isLive ? DashColors.energyGreen : DashColors.warningAmber).withValues(alpha: 0.15),
            borderRadius: BorderRadius.circular(20),
            border: Border.all(color: (isLive ? DashColors.energyGreen : DashColors.warningAmber).withValues(alpha: 0.3)),
          ),
          child: Row(mainAxisSize: MainAxisSize.min, children: [
            Container(width: 6, height: 6, decoration: BoxDecoration(
              color: isLive ? DashColors.energyGreen : DashColors.warningAmber,
              shape: BoxShape.circle,
              boxShadow: [BoxShadow(color: (isLive ? DashColors.energyGreen : DashColors.warningAmber).withValues(alpha: 0.5), blurRadius: 4)],
            )),
            const SizedBox(width: 4),
            Text(isLive ? 'LIVE' : 'Connecting...',
              style: TextStyle(color: isLive ? DashColors.energyGreen : DashColors.warningAmber, fontSize: 10, fontWeight: FontWeight.w600),
            ),
          ]),
        ),
      ]),
      const SizedBox(height: 8),
      Text('Welcome back. Systems ${isLive ? "operational" : "connecting..."}.',
        style: DashTypography.bodyLarge.copyWith(color: DashColors.textGray),
      ).animate().fadeIn(duration: 400.ms, delay: 200.ms).slideX(begin: -20, end: 0, duration: 400.ms, delay: 200.ms),
    ]);
  }

  Widget _buildAICoreStatus() {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;
    final cpuPct = snap?.cpuPercent ?? 0;
    final ramPct = snap?.ramPercent ?? 0;
    final cpuTemp = snap?.cpuTemp;

    return GlassPanel(padding: const EdgeInsets.all(24), child: Row(children: [
      const AICoreWithStatus(state: AIState.idle, size: 80, statusText: 'AI CORE'),
      const SizedBox(width: 24),
      Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
        const Text('Neural Interface Active',
          style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600),
        ),
        const SizedBox(height: 4),
        Text(
          'CPU: ${cpuPct.toStringAsFixed(0)}% | RAM: ${ramPct.toStringAsFixed(0)}%${cpuTemp != null ? " | ${cpuTemp.toStringAsFixed(1)}°C" : ""}',
          style: const TextStyle(color: DashColors.textGray, fontSize: 12),
        ),
        const SizedBox(height: 12),
        Wrap(spacing: 8, runSpacing: 4, children: [
          _StatusBadge(
            label: state.status == SystemMonitorStatus.connected ? 'Online' : 'Connecting',
            color: state.status == SystemMonitorStatus.connected ? DashColors.energyGreen : DashColors.warningAmber,
          ),
          _StatusBadge(label: 'Real-time', color: DashColors.electricBlue),
          _StatusBadge(label: 'Secured', color: DashColors.purpleGlow),
        ]),
      ])),
    ]));
  }

  Widget _buildQuickActions() {
    return Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Text('Quick Actions',
        style: DashTypography.titleMedium.copyWith(color: DashColors.textGray, fontWeight: FontWeight.w600),
      ).animate().fadeIn(duration: 400.ms, delay: 400.ms),
      const SizedBox(height: 12),
      GridView.count(
        crossAxisCount: 2, shrinkWrap: true, physics: const NeverScrollableScrollPhysics(),
        crossAxisSpacing: 12, mainAxisSpacing: 12, childAspectRatio: 1.4,
        children: [
          _QuickActionCard(icon: Icons.chat_bubble_outlined, label: 'AI Chat', description: 'Talk with DASH',
            gradient: const LinearGradient(colors: [DashColors.electricBlue, DashColors.purpleGlow], begin: Alignment.topLeft, end: Alignment.bottomRight),
            onTap: () => context.go(AppRoutes.chat),
          ),
          _QuickActionCard(icon: Icons.memory_outlined, label: 'Memory', description: 'View stored memories',
            gradient: const LinearGradient(colors: [DashColors.energyGreen, DashColors.electricBlue], begin: Alignment.topLeft, end: Alignment.bottomRight),
            onTap: () => context.go(AppRoutes.memory),
          ),
          _QuickActionCard(icon: Icons.auto_awesome_outlined, label: 'Automation', description: 'Run automations',
            gradient: const LinearGradient(colors: [DashColors.warningAmber, DashColors.energyGreen], begin: Alignment.topLeft, end: Alignment.bottomRight),
            onTap: () => context.go(AppRoutes.automation),
          ),
          _QuickActionCard(icon: Icons.visibility_outlined, label: 'Vision', description: 'Visual analysis',
            gradient: const LinearGradient(colors: [DashColors.purpleGlow, DashColors.electricBlue], begin: Alignment.topLeft, end: Alignment.bottomRight),
            onTap: () => context.go(AppRoutes.vision),
          ),
        ],
      ),
    ]);
  }

  Widget _buildSystemStatus() {
    final state = ref.watch(systemMonitorProvider);
    final snap = state.snapshot;

    return GlassPanel(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      const Text('System Status',
        style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600),
      ),
      const SizedBox(height: 16),
      _LiveMetricWidget(
        label: 'CPU Usage',
        valueBuilder: (snap) {
          final pct = snap?.cpuPercent;
          return pct != null ? '${pct.toStringAsFixed(0)}%' : '--%';
        },
        progressBuilder: (snap) => (snap?.cpuPercent ?? 0) / 100,
        color: DashColors.energyGreen,
      ),
      const SizedBox(height: 12),
      _LiveMetricWidget(
        label: 'Memory',
        valueBuilder: (snap) {
          final used = snap?.ramUsedGb;
          final total = snap?.ramTotalGb;
          if (used != null && total != null) {
            return '${used.toStringAsFixed(1)} / ${total.toStringAsFixed(1)} GB';
          }
          return '-- / -- GB';
        },
        progressBuilder: (snap) => (snap?.ramPercent ?? 0) / 100,
        color: DashColors.electricBlue,
      ),
      const SizedBox(height: 12),
      _LiveMetricWidget(
        label: 'CPU Details',
        valueBuilder: (snap) {
          final freq = snap?.cpuFreq;
          final temp = snap?.cpuTemp;
          if (freq != null && temp != null) {
            return '${freq.toStringAsFixed(0)} MHz / ${temp.toStringAsFixed(1)}°C';
          } else if (freq != null) {
            return '${freq.toStringAsFixed(0)} MHz';
          }
          return snap?.cpu['brand']?.toString() ?? 'Active';
        },
        progressBuilder: (_) => 1.0,
        color: DashColors.purpleGlow,
      ),
      const SizedBox(height: 12),
      _LiveMetricWidget(
        label: 'Network',
        valueBuilder: (snap) {
          final down = snap?.downloadSpeedMbps;
          final up = snap?.uploadSpeedMbps;
          final ip = snap?.ipAddress;
          if (down != null && up != null) {
            return '⬇ ${down.toStringAsFixed(1)} ⬆ ${up.toStringAsFixed(1)} Mbps';
          }
          return ip ?? 'Connected';
        },
        progressBuilder: (_) => 0.85,
        color: DashColors.skyBlue,
      ),
      const SizedBox(height: 12),
      _LiveMetricWidget(
        label: 'Storage',
        valueBuilder: (snap) {
          final used = snap?.storageUsedGb;
          final total = snap?.storageTotalGb;
          if (used != null && total != null) {
            return '${used.toStringAsFixed(0)} / ${total.toStringAsFixed(0)} GB';
          }
          return '-- / -- GB';
        },
        progressBuilder: (snap) {
          final used = snap?.storageUsedGb ?? 0;
          final total = snap?.storageTotalGb ?? 1;
          return total > 0 ? (used / total).clamp(0.0, 1.0) : 0.0;
        },
        color: DashColors.energyGreen,
      ),
      if (snap?.gpu != null && snap!.gpu.isNotEmpty) ...[
        const SizedBox(height: 12),
        _LiveMetricWidget(
          label: 'GPU',
          valueBuilder: (snap) {
            final gpu = snap?.gpu.firstOrNull;
            if (gpu == null) return 'N/A';
            final name = gpu['name']?.toString() ?? 'GPU';
            final usage = gpu['usage_percent']?.toDouble();
            return usage != null ? '$name ${usage.toStringAsFixed(0)}%' : name;
          },
          progressBuilder: (snap) {
            final usage = snap?.gpu.firstOrNull?['usage_percent']?.toDouble() ?? 0;
            return usage / 100;
          },
          color: DashColors.purpleGlow,
        ),
      ],
      if (snap?.batteryPercent != null) ...[
        const SizedBox(height: 12),
        _LiveMetricWidget(
          label: 'Battery',
          valueBuilder: (snap) {
            final pct = snap?.batteryPercent;
            final charging = snap?.batteryCharging;
            if (pct == null) return 'N/A';
            final icon = charging == true ? '🔌' : '🔋';
            return '$icon ${pct.toStringAsFixed(0)}%';
          },
          progressBuilder: (snap) => (snap?.batteryPercent ?? 0) / 100,
          color: DashColors.energyGreen,
        ),
      ],
    ]));
  }

  Widget _buildRecentActivity() {
    return GlassPanel(padding: const EdgeInsets.all(20), child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
      Row(mainAxisAlignment: MainAxisAlignment.spaceBetween, children: [
        const Text('Quick Command',
          style: TextStyle(color: DashColors.softWhite, fontSize: 15, fontWeight: FontWeight.w600),
        ),
        TextButton(onPressed: () => context.go(AppRoutes.chat),
          child: const Text('Open Chat', style: TextStyle(color: DashColors.electricBlue, fontSize: 13)),
        ),
      ]),
      const SizedBox(height: 16),
      GlassInput(
        hintText: 'Type a command or ask DASH anything...',
        prefixIcon: const Icon(Icons.terminal, color: DashColors.textGray, size: 18),
        suffixIcon: Container(
          margin: const EdgeInsets.all(4),
          decoration: BoxDecoration(
            gradient: const LinearGradient(colors: [DashColors.electricBlue, DashColors.purpleGlow]),
            borderRadius: BorderRadius.circular(10),
          ),
          child: IconButton(
            icon: const Icon(Icons.arrow_upward, color: DashColors.pureWhite, size: 16),
            onPressed: () => context.go(AppRoutes.chat),
          ),
        ),
        onSubmitted: (_) => context.go(AppRoutes.chat),
      ),
    ]));
  }
}

