import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/constants.dart';

class AboutPage extends ConsumerWidget {
  const AboutPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        // App icon and name
        Center(
          child: Column(
            children: [
              Container(
                padding: const EdgeInsets.all(20),
                decoration: BoxDecoration(
                  color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                  shape: BoxShape.circle,
                ),
                child: Icon(
                  Icons.auto_awesome,
                  size: 48,
                  color: colorScheme.primary,
                ),
              ),
              const SizedBox(height: 16),
              Text(
                appName,
                style: theme.textTheme.headlineMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const SizedBox(height: 4),
              Text(
                'AI Operating System',
                style: theme.textTheme.titleSmall?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.6),
                ),
              ),
              const SizedBox(height: 8),
              Container(
                padding: const EdgeInsets.symmetric(
                  horizontal: 12,
                  vertical: 4,
                ),
                decoration: BoxDecoration(
                  color: colorScheme.primaryContainer,
                  borderRadius: BorderRadius.circular(12),
                ),
                child: Text(
                  'v$appVersion',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: colorScheme.onPrimaryContainer,
                    fontWeight: FontWeight.w600,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),

        // About section
        Card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  'About',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Text(
                  'DASH is an AI Operating System that provides intelligent '
                  'assistance across your devices. It features natural language '
                  'understanding, memory management, task automation, and '
                  'seamless multi-platform support.',
                  style: theme.textTheme.bodyMedium?.copyWith(
                    color: colorScheme.onSurface.withValues(alpha: 0.7),
                    height: 1.5,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Build info
        const Card(
          child: Column(
            children: [
              _InfoTile(
                icon: Icons.tag,
                title: 'Version',
                subtitle: '$appVersion (build 1)',
              ),
              Divider(height: 1, indent: 16, endIndent: 16),
              _InfoTile(
                icon: Icons.language,
                title: 'Framework',
                subtitle: 'Flutter 3.44+',
              ),
              Divider(height: 1, indent: 16, endIndent: 16),
              _InfoTile(
                icon: Icons.code,
                title: 'Backend',
                subtitle: 'FastAPI (Python)',
              ),
              Divider(height: 1, indent: 16, endIndent: 16),
              _InfoTile(
                icon: Icons.storage,
                title: 'Database',
                subtitle: 'PostgreSQL',
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Links
        Card(
          child: Column(
            children: [
              ListTile(
                leading: Icon(Icons.code, color: colorScheme.primary),
                title: const Text('Source Code'),
                subtitle: const Text('GitHub repository'),
                trailing: const Icon(Icons.open_in_new, size: 18),
                onTap: () => _launchUrl('https://github.com/dash-ai/dash'),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(Icons.description, color: colorScheme.primary),
                title: const Text('Documentation'),
                subtitle: const Text('Full documentation site'),
                trailing: const Icon(Icons.open_in_new, size: 18),
                onTap: () => _launchUrl('https://dash-ai.dev/docs'),
              ),
              const Divider(height: 1, indent: 16, endIndent: 16),
              ListTile(
                leading: Icon(Icons.report_problem, color: colorScheme.primary),
                title: const Text('Report Issue'),
                subtitle: const Text('File a bug or feature request'),
                trailing: const Icon(Icons.open_in_new, size: 18),
                onTap: () =>
                    _launchUrl('https://github.com/dash-ai/dash/issues'),
              ),
            ],
          ),
        ),
        const SizedBox(height: 12),

        // Credits
        Card(
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
                child: Text(
                  'Credits',
                  style: theme.textTheme.titleMedium?.copyWith(
                    fontWeight: FontWeight.bold,
                  ),
                ),
              ),
              Padding(
                padding: const EdgeInsets.fromLTRB(16, 0, 16, 16),
                child: Text(
                  'Built with Flutter, FastAPI, PostgreSQL, Redis, '
                  'and many open-source contributions.\n\n'
                  'Licensed under MIT License.',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: colorScheme.onSurface.withValues(alpha: 0.6),
                    height: 1.5,
                  ),
                ),
              ),
            ],
          ),
        ),
        const SizedBox(height: 32),

        // Copyright
        Center(
          child: Text(
            '© ${DateTime.now().year} Dash AI',
            style: theme.textTheme.bodySmall?.copyWith(
              color: colorScheme.onSurface.withValues(alpha: 0.4),
            ),
          ),
        ),
        const SizedBox(height: 16),
      ],
    );
  }

  Future<void> _launchUrl(String url) async {
    final uri = Uri.parse(url);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri, mode: LaunchMode.externalApplication);
    }
  }
}

class _InfoTile extends StatelessWidget {
  const _InfoTile({
    required this.icon,
    required this.title,
    required this.subtitle,
  });

  final IconData icon;
  final String title;
  final String subtitle;

  @override
  Widget build(BuildContext context) {
    return ListTile(
      leading: Icon(icon, size: 20),
      title: Text(title, style: const TextStyle(fontSize: 14)),
      subtitle: Text(
        subtitle,
        style: TextStyle(
          fontSize: 12,
          color: Theme.of(context)
              .colorScheme
              .onSurface
              .withValues(alpha: 0.6),
        ),
      ),
      dense: true,
    );
  }
}

