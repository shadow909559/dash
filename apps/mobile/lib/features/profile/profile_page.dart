import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shimmer/shimmer.dart';

import '../../core/theme/app_theme.dart';
import '../auth/providers/auth_provider.dart';
import '../auth/services/auth_service.dart';
import '../settings/settings_page.dart';

class ProfilePage extends ConsumerStatefulWidget {
  const ProfilePage({super.key});

  @override
  ConsumerState<ProfilePage> createState() => _ProfilePageState();
}

class _ProfilePageState extends ConsumerState<ProfilePage> {
  @override
  Widget build(BuildContext context) {
    final authState = ref.watch(authProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    if (authState.isLoading) {
      return Scaffold(
        appBar: AppBar(title: const Text('Profile')),
        body: _buildSkeleton(theme, colorScheme),
      );
    }

    final user = authState.user;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Profile'),
        actions: [
          IconButton(
            icon: const Icon(Icons.settings_outlined),
            tooltip: 'Settings',
            onPressed: () {
              Navigator.of(context).push(
                MaterialPageRoute(
                  builder: (context) => const SettingsPage(),
                ),
              );
            },
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          // Avatar and name section
          Center(
            child: Column(
              children: [
                CircleAvatar(
                  radius: 48,
                  backgroundColor: colorScheme.primaryContainer,
                  child: Icon(
                    Icons.person,
                    size: 48,
                    color: colorScheme.onPrimaryContainer,
                  ),
                ),
                const SizedBox(height: 16),
                Text(
                  user?.username ?? 'User',
                  style: theme.textTheme.headlineSmall?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
                const SizedBox(height: 4),
                Text(
                  user?.email ?? '',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
              ],
            ),
          ),
          const SizedBox(height: 32),

          // Account section
          Text(
            'Account',
            style: theme.textTheme.titleSmall?.copyWith(
              color: colorScheme.primary,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: Icon(Icons.person_outline, color: colorScheme.onSurfaceVariant),
                  title: const Text('Username'),
                  subtitle: Text(user?.username ?? 'Not set'),
                ),
                if (user?.email != null)
                  ListTile(
                    leading: Icon(Icons.email_outlined, color: colorScheme.onSurfaceVariant),
                    title: const Text('Email'),
                    subtitle: Text(user!.email!),
                  ),
                ListTile(
                  leading: Icon(Icons.calendar_today_outlined, color: colorScheme.onSurfaceVariant),
                  title: const Text('Member since'),
                  subtitle: Text(user?.createdAt != null
                      ? '${user!.createdAt!.month}/${user.createdAt!.day}/${user.createdAt!.year}'
                      : 'Unknown'),
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Preferences section
          Text(
            'Preferences',
            style: theme.textTheme.titleSmall?.copyWith(
              color: colorScheme.primary,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: Column(
              children: [
                ListTile(
                  leading: Icon(Icons.palette_outlined, color: colorScheme.onSurfaceVariant),
                  title: const Text('Theme'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'System',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
                    ],
                  ),
                  onTap: () {
                    Navigator.of(context).push(
                      MaterialPageRoute(
                        builder: (context) => const SettingsPage(),
                      ),
                    );
                  },
                ),
                const Divider(height: 1),
                ListTile(
                  leading: Icon(Icons.notifications_outlined, color: colorScheme.onSurfaceVariant),
                  title: const Text('Notifications'),
                  trailing: Row(
                    mainAxisSize: MainAxisSize.min,
                    children: [
                      Text(
                        'Enabled',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurfaceVariant,
                        ),
                      ),
                      const SizedBox(width: 4),
                      Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
                    ],
                  ),
                  onTap: () {},
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),

          // Danger zone
          Text(
            'Session',
            style: theme.textTheme.titleSmall?.copyWith(
              color: colorScheme.error,
              fontWeight: FontWeight.w600,
              letterSpacing: 0.5,
            ),
          ),
          const SizedBox(height: 8),
          Card(
            child: ListTile(
              leading: Icon(Icons.logout, color: colorScheme.error),
              title: Text('Log out', style: TextStyle(color: colorScheme.error)),
              onTap: () => _showLogoutDialog(context),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSkeleton(ThemeData theme, ColorScheme colorScheme) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Shimmer.fromColors(
          baseColor: colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          highlightColor: colorScheme.surfaceContainerHighest,
          child: Column(
            children: [
              const SizedBox(height: 24),
              Container(
                width: 96,
                height: 96,
                decoration: const BoxDecoration(shape: BoxShape.circle),
              ),
              const SizedBox(height: 16),
              Container(width: 150, height: 24),
              const SizedBox(height: 8),
              Container(width: 200, height: 14),
              const SizedBox(height: 32),
              Container(width: double.infinity, height: 120),
              const SizedBox(height: 24),
              Container(width: double.infinity, height: 120),
            ],
          ),
        ),
      ],
    );
  }

  void _showLogoutDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Log out'),
        content: const Text('Are you sure you want to log out?'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              Navigator.pop(ctx);
              ref.read(authProvider.notifier).logout();
            },
            child: const Text('Log out'),
          ),
        ],
      ),
    );
  }
}