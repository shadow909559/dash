import 'package:flutter/material.dart';
import 'package:go_router/go_router.dart';
import 'package:flutter_animate/flutter_animate.dart';

import '../../core/routing/app_routes.dart';
import '../../core/theme/dash_theme.dart';
import '../../core/widgets/glassmorphism.dart';
import '../../core/widgets/ai_core.dart';

// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
// PRIVATE UI COMPONENTS
// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class _SidebarDivider extends StatelessWidget {
  const _SidebarDivider();
  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Container(
        height: 0.5, color: Colors.white.withValues(alpha: 0.08),
      ),
    );
  }
}

class _StatusDot extends StatelessWidget {
  final Color color; final String label;
  const _StatusDot({required this.color, required this.label});
  @override
  Widget build(BuildContext context) {
    return Row(mainAxisSize: MainAxisSize.min, children: [
      Container(width: 6, height: 6, decoration: BoxDecoration(
        color: color, shape: BoxShape.circle,
        boxShadow: [BoxShadow(color: color.withValues(alpha: 0.5), blurRadius: 4)],
      )),
      const SizedBox(width: 6),
      Text(label, style: const TextStyle(color: DashColors.textGray, fontSize: 11)),
    ]);
  }
}

class _NavItem extends StatelessWidget {
  final IconData icon; final IconData selectedIcon; final String label;
  final bool selected; final bool expanded; final VoidCallback onTap;
  const _NavItem({
    required this.icon, required this.selectedIcon, required this.label,
    required this.selected, required this.expanded, required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    final color = selected ? DashColors.electricBlue : DashColors.textGray;
    return Material(
      color: Colors.transparent,
      child: InkWell(
        onTap: onTap, borderRadius: BorderRadius.circular(10),
        child: Container(
          margin: EdgeInsets.symmetric(horizontal: expanded ? 8 : 4, vertical: 2),
          padding: EdgeInsets.symmetric(horizontal: expanded ? 12 : 8, vertical: 10),
          decoration: BoxDecoration(
            color: selected ? DashColors.electricBlue.withValues(alpha: 0.1) : Colors.transparent,
            borderRadius: BorderRadius.circular(10),
            border: selected ? Border.all(color: DashColors.electricBlue.withValues(alpha: 0.2), width: 0.5) : null,
          ),
          child: Row(children: [
            Icon(selected ? selectedIcon : icon, size: 20, color: color),
            if (expanded) ...[
              const SizedBox(width: 12),
              Expanded(child: Text(label, style: TextStyle(
                color: selected ? DashColors.electricBlue : DashColors.softWhite,
                fontSize: 13, fontWeight: selected ? FontWeight.w600 : FontWeight.normal,
              ))),
              if (selected)
                Container(width: 6, height: 6, decoration: BoxDecoration(
                  color: DashColors.electricBlue, shape: BoxShape.circle,
                  boxShadow: [BoxShadow(color: DashColors.electricBlue.withValues(alpha: 0.5), blurRadius: 4)],
                )),
            ],
          ]),
        ),
      ),
    );
  }
}

class _MobileNavItem extends StatelessWidget {
  final IconData icon; final IconData selectedIcon; final String label;
  final bool selected; final VoidCallback onTap;
  const _MobileNavItem({
    required this.icon, required this.selectedIcon, required this.label,
    required this.selected, required this.onTap,
  });
  @override
  Widget build(BuildContext context) {
    final color = selected ? DashColors.electricBlue : DashColors.textGray;
    return GestureDetector(
      onTap: onTap,
      child: AnimatedContainer(
        duration: const Duration(milliseconds: 200),
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 6),
        decoration: BoxDecoration(
          color: selected ? DashColors.electricBlue.withValues(alpha: 0.1) : Colors.transparent,
          borderRadius: BorderRadius.circular(12),
        ),
        child: Column(mainAxisSize: MainAxisSize.min, children: [
          Icon(selected ? selectedIcon : icon, size: 22, color: color),
          const SizedBox(height: 2),
          Text(label, style: TextStyle(color: color, fontSize: 10, fontWeight: selected ? FontWeight.w600 : FontWeight.normal)),
        ]),
      ),
    );
  }
}

// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════
// DASH AI OS — PREMIUM APP SHELL
// ══════════════════════════════════════════════════════════════════════════════════════════════════════════════════════

class AppShell extends StatefulWidget {
  final String location;
  final Widget child;
  const AppShell({required this.location, required this.child, super.key});
  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> with SingleTickerProviderStateMixin {
  late AnimationController _sidebarController;
  bool _isSidebarExpanded = true;
  bool _isMobile = false;

  @override
  void initState() {
    super.initState();
    _sidebarController = AnimationController(duration: const Duration(milliseconds: 300), vsync: this);
    _sidebarController.value = 1.0;
  }

  @override
  void dispose() {
    _sidebarController.dispose();
    super.dispose();
  }

  int get _selectedIndex {
    final p = widget.location;
    if (p.startsWith(AppRoutes.chat)) return 1;
    if (p.startsWith(AppRoutes.memory)) return 2;
    if (p.startsWith(AppRoutes.workspace)) return 3;
    if (p.startsWith(AppRoutes.projects)) return 4;
    if (p.startsWith(AppRoutes.notifications)) return 5;
    if (p.startsWith(AppRoutes.settings)) return 6;
    if (p.startsWith(AppRoutes.planner)) return 7;
    if (p.startsWith(AppRoutes.automation)) return 8;
    if (p.startsWith(AppRoutes.desktop)) return 9;
    if (p.startsWith(AppRoutes.voice)) return 10;
    if (p.startsWith(AppRoutes.vision)) return 11;
    if (p.startsWith(AppRoutes.files)) return 12;
    if (p.startsWith(AppRoutes.plugins)) return 13;
    if (p.startsWith(AppRoutes.search)) return 14;
    if (p.startsWith(AppRoutes.profile)) return 15;
    if (p.startsWith(AppRoutes.help)) return 16;
    return 0;
  }

  @override
  Widget build(BuildContext context) {
    _isMobile = MediaQuery.of(context).size.width < 600;
    if (_isMobile) return _buildMobileLayout(context);
    return _buildDesktopLayout(context);
  }

  Widget _buildMobileLayout(BuildContext context) {
    return Scaffold(
      backgroundColor: Colors.transparent,
      body: Stack(children: [
        SafeArea(child: widget.child),
        Positioned(left: 0, right: 0, bottom: 0, child: _buildMobileNavBar(context)),
      ]),
    );
  }

  Widget _buildMobileNavBar(BuildContext context) {
    return Container(
      padding: EdgeInsets.only(left: 8, right: 8, top: 8, bottom: MediaQuery.of(context).padding.bottom + 8),
      decoration: BoxDecoration(
        color: DashColors.carbonBlack.withValues(alpha: 0.9),
        border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.08), width: 0.5)),
      ),
      child: Row(mainAxisAlignment: MainAxisAlignment.spaceAround, children: [
        _MobileNavItem(icon: Icons.dashboard_outlined, selectedIcon: Icons.dashboard, label: 'Home', selected: _selectedIndex == 0, onTap: () => context.go(AppRoutes.dashboard)),
        _MobileNavItem(icon: Icons.chat_bubble_outline, selectedIcon: Icons.chat_bubble, label: 'Chat', selected: _selectedIndex == 1, onTap: () => context.go(AppRoutes.chat)),
        _MobileNavItem(icon: Icons.memory_outlined, selectedIcon: Icons.memory, label: 'Memory', selected: _selectedIndex == 2, onTap: () => context.go(AppRoutes.memory)),
        _MobileNavItem(icon: Icons.settings_outlined, selectedIcon: Icons.settings, label: 'Settings', selected: _selectedIndex == 6, onTap: () => context.go(AppRoutes.settings)),
      ]),
    );
  }

  Widget _buildDesktopLayout(BuildContext context) {
    return Scaffold(
      backgroundColor: DashColors.carbonBlack,
      body: SafeArea(child: Row(children: [
        _buildSidebar(context),
        Expanded(child: Column(children: [
          _buildStatusBar(context),
          Expanded(child: widget.child),
        ])),
      ])),
    );
  }

  Widget _buildSidebar(BuildContext context) {
    final w = _isSidebarExpanded ? 240.0 : 72.0;
    return Container(
      width: w,
      decoration: BoxDecoration(
        color: DashColors.glassFrost.withValues(alpha: 0.05),
        border: Border(right: BorderSide(color: Colors.white.withValues(alpha: 0.08), width: 0.5)),
      ),
      child: Column(children: [
        _buildBrandSection(context),
        Expanded(child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(vertical: 8),
          child: Column(children: [
            _NavItem(icon: Icons.dashboard_outlined, selectedIcon: Icons.dashboard, label: 'Dashboard', selected: _selectedIndex == 0, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.dashboard)),
            _NavItem(icon: Icons.chat_bubble_outline, selectedIcon: Icons.chat_bubble, label: 'Chat', selected: _selectedIndex == 1, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.chat)),
            _NavItem(icon: Icons.memory_outlined, selectedIcon: Icons.memory, label: 'Memory', selected: _selectedIndex == 2, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.memory)),
            _NavItem(icon: Icons.workspaces_outlined, selectedIcon: Icons.workspaces, label: 'Workspace', selected: _selectedIndex == 3, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.workspace)),
            _NavItem(icon: Icons.folder_outlined, selectedIcon: Icons.folder, label: 'Projects', selected: _selectedIndex == 4, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.projects)),
            _NavItem(icon: Icons.notifications_outlined, selectedIcon: Icons.notifications, label: 'Notifications', selected: _selectedIndex == 5, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.notifications)),
            const _SidebarDivider(),
            _NavItem(icon: Icons.auto_awesome_outlined, selectedIcon: Icons.auto_awesome, label: 'Automation', selected: _selectedIndex == 8, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.automation)),
            _NavItem(icon: Icons.desktop_windows_outlined, selectedIcon: Icons.desktop_windows, label: 'Desktop', selected: _selectedIndex == 9, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.desktop)),
            _NavItem(icon: Icons.mic_outlined, selectedIcon: Icons.mic, label: 'Voice', selected: _selectedIndex == 10, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.voice)),
            _NavItem(icon: Icons.visibility_outlined, selectedIcon: Icons.visibility, label: 'Vision', selected: _selectedIndex == 11, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.vision)),
            _NavItem(icon: Icons.folder_outlined, selectedIcon: Icons.folder, label: 'Files', selected: _selectedIndex == 12, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.files)),
            _NavItem(icon: Icons.extension_outlined, selectedIcon: Icons.extension, label: 'Plugins', selected: _selectedIndex == 13, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.plugins)),
            const _SidebarDivider(),
            _NavItem(icon: Icons.calendar_month_outlined, selectedIcon: Icons.calendar_month, label: 'Planner', selected: _selectedIndex == 7, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.planner)),
            _NavItem(icon: Icons.search_outlined, selectedIcon: Icons.search, label: 'Search', selected: _selectedIndex == 14, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.search)),
            _NavItem(icon: Icons.person_outlined, selectedIcon: Icons.person, label: 'Profile', selected: _selectedIndex == 15, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.profile)),
            _NavItem(icon: Icons.help_outlined, selectedIcon: Icons.help, label: 'Help', selected: _selectedIndex == 16, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.help)),
          ]),
        )),
        _buildSidebarBottom(context),
      ]),
    );
  }

  Widget _buildBrandSection(BuildContext context) {
    return Container(
      padding: EdgeInsets.symmetric(horizontal: _isSidebarExpanded ? 16 : 8, vertical: 16),
      child: Row(children: [
        const MiniAICore(state: AIState.idle, size: 36),
        if (_isSidebarExpanded) ...[
          const SizedBox(width: 12),
          Expanded(child: Column(crossAxisAlignment: CrossAxisAlignment.start, children: [
            Text('DASH', style: DashTypography.titleMedium.copyWith(color: DashColors.pureWhite, fontWeight: FontWeight.w800, letterSpacing: 2)),
            Text('AI OS', style: DashTypography.labelSmall.copyWith(color: DashColors.electricBlue, letterSpacing: 1.5)),
          ])),
        ],
        GestureDetector(
          onTap: () => setState(() => _isSidebarExpanded = !_isSidebarExpanded),
          child: Container(
            padding: const EdgeInsets.all(4),
            decoration: BoxDecoration(color: DashColors.glassFrost.withValues(alpha: 0.1), borderRadius: BorderRadius.circular(6)),
            child: Icon(_isSidebarExpanded ? Icons.chevron_left : Icons.chevron_right, size: 16, color: DashColors.textGray),
          ),
        ),
      ]),
    );
  }

  Widget _buildSidebarBottom(BuildContext context) {
    return Container(
      padding: EdgeInsets.all(_isSidebarExpanded ? 16 : 8),
      decoration: BoxDecoration(border: Border(top: BorderSide(color: Colors.white.withValues(alpha: 0.08), width: 0.5))),
      child: Column(children: [
        _NavItem(icon: Icons.settings_outlined, selectedIcon: Icons.settings, label: 'Settings', selected: _selectedIndex == 6, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.settings)),
        const SizedBox(height: 4),
        _NavItem(icon: Icons.info_outline, selectedIcon: Icons.info, label: 'About', selected: false, expanded: _isSidebarExpanded, onTap: () => context.go(AppRoutes.about)),
      ]),
    );
  }

  Widget _buildStatusBar(BuildContext context) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 8),
      decoration: BoxDecoration(
        color: DashColors.glassFrost.withValues(alpha: 0.03),
        border: Border(bottom: BorderSide(color: Colors.white.withValues(alpha: 0.05), width: 0.5)),
      ),
      child: Row(children: [
        Text(_getPageTitle(), style: DashTypography.titleSmall.copyWith(color: DashColors.softWhite, fontWeight: FontWeight.w600)),
        const Spacer(),
        const _StatusDot(color: DashColors.energyGreen, label: 'System Online'),
        const SizedBox(width: 16),
        const _StatusDot(color: DashColors.electricBlue, label: 'AI Ready'),
      ]),
    );
  }

  String _getPageTitle() {
    switch (_selectedIndex) {
      case 0: return 'Dashboard'; case 1: return 'Chat'; case 2: return 'Memory'; case 3: return 'Workspace';
      case 4: return 'Projects'; case 5: return 'Notifications'; case 6: return 'Settings'; case 7: return 'Planner';
      case 8: return 'Automation'; case 9: return 'Desktop Control'; case 10: return 'Voice'; case 11: return 'Vision';
      case 12: return 'Files'; case 13: return 'Plugins'; case 14: return 'Search'; case 15: return 'Profile'; case 16: return 'Help';
      default: return 'Dashboard';
    }
  }
}
