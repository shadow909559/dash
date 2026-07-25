import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import './providers/help_provider.dart';

class HelpPage extends ConsumerWidget {
  const HelpPage({super.key});

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final state = ref.watch(helpProvider);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Help & Support'),
      ),
      body: RefreshIndicator(
        onRefresh: () async => ref.read(helpProvider.notifier).loadFaqs(),
        child: ListView(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          children: [
            if (state.isLoading)
              _buildLoadingSkeleton(theme, colorScheme)
            else
              ...state.faqs.map(
                (faq) => Padding(
                  padding: const EdgeInsets.only(bottom: 12),
                  child: _FaqCard(faq: faq, theme: theme, colorScheme: colorScheme),
                ),
              ),
            const SizedBox(height: 24),
            _buildSectionTitle('Contact Support', theme, colorScheme),
            const SizedBox(height: 8),
            _ContactCard(theme: theme, colorScheme: colorScheme),
            const SizedBox(height: 24),
            _buildSectionTitle('Documentation', theme, colorScheme),
            const SizedBox(height: 8),
            _DocCard(theme: theme, colorScheme: colorScheme),
            const SizedBox(height: 24),
            _buildSectionTitle('About DASH', theme, colorScheme),
            const SizedBox(height: 8),
            _AboutCard(theme: theme, colorScheme: colorScheme),
            const SizedBox(height: 24),
            _buildSectionTitle('Troubleshooting', theme, colorScheme),
            const SizedBox(height: 8),
            _TroubleshootingCard(theme: theme, colorScheme: colorScheme),
            const SizedBox(height: 32),
          ],
        ),
      ),
    );
  }

  Widget _buildSectionTitle(String title, ThemeData theme, ColorScheme colorScheme) {
    return Text(
      title,
      style: theme.textTheme.titleSmall?.copyWith(
        fontWeight: FontWeight.w600,
        color: colorScheme.onSurface.withValues(alpha: 0.7),
      ),
    );
  }

  Widget _buildLoadingSkeleton(ThemeData theme, ColorScheme colorScheme) {
    return ListView.builder(
      shrinkWrap: true,
      physics: const NeverScrollableScrollPhysics(),
      padding: EdgeInsets.zero,
      itemCount: 4,
      itemBuilder: (_, __) => Padding(
        padding: const EdgeInsets.only(bottom: 12),
        child: Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Container(height: 14, width: 180, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                const SizedBox(height: 12),
                Container(height: 10, width: double.infinity, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
                const SizedBox(height: 6),
                Container(height: 10, width: 260, decoration: BoxDecoration(color: theme.colorScheme.surfaceContainerHighest, borderRadius: BorderRadius.circular(4))),
              ],
            ),
          ),
        ),
      ),
    );
  }
}

class _FaqCard extends StatefulWidget {
  final HelpFaq faq;
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _FaqCard({
    required this.faq,
    required this.theme,
    required this.colorScheme,
  });

  @override
  State<_FaqCard> createState() => _FaqCardState();
}

class _FaqCardState extends State<_FaqCard> {
  bool _isExpanded = false;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: () => setState(() => _isExpanded = !_isExpanded),
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Row(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Icon(Icons.help_outline, size: 20, color: colorScheme.primary),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(widget.faq.question, style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600)),
                  ),
                  Icon(_isExpanded ? Icons.expand_less : Icons.expand_more, size: 20, color: colorScheme.onSurface.withValues(alpha: 0.5)),
                ],
              ),
              if (_isExpanded) ...[
                const SizedBox(height: 10),
                Text(widget.faq.answer, style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.8), height: 1.5)),
              ],
            ],
          ),
        ),
      ),
    );
  }
}

class _ContactCard extends StatelessWidget {
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _ContactCard({required this.theme, required this.colorScheme});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          ListTile(
            leading: Icon(Icons.email_outlined, color: colorScheme.primary),
            title: const Text('Email Support'),
            subtitle: const Text('support@dash.ai'),
            trailing: const Icon(Icons.chevron_right, size: 18),
            onTap: () {},
          ),
          const Divider(height: 1, indent: 56, endIndent: 16),
          ListTile(
            leading: Icon(Icons.chat_outlined, color: colorScheme.tertiary),
            title: const Text('Community Forum'),
            subtitle: const Text('Discussions and Q&A'),
            trailing: const Icon(Icons.chevron_right, size: 18),
            onTap: () {},
          ),
          const Divider(height: 1, indent: 56, endIndent: 16),
          ListTile(
            leading: Icon(Icons.bug_report_outlined, color: Colors.red),
            title: const Text('Report a Bug'),
            subtitle: const Text('Submit issues and feedback'),
            trailing: const Icon(Icons.chevron_right, size: 18),
            onTap: () {},
          ),
        ],
      ),
    );
  }
}

class _DocCard extends StatelessWidget {
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _DocCard({required this.theme, required this.colorScheme});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Column(
        children: [
          ListTile(
            leading: Icon(Icons.menu_book_outlined, color: colorScheme.secondary),
            title: const Text('Getting Started Guide'),
            trailing: const Icon(Icons.open_in_new, size: 18),
          ),
          const Divider(height: 1, indent: 56, endIndent: 16),
          ListTile(
            leading: Icon(Icons.help_center_outlined, color: colorScheme.tertiary),
            title: const Text('API Reference'),
            trailing: const Icon(Icons.open_in_new, size: 18),
          ),
          const Divider(height: 1, indent: 56, endIndent: 16),
          ListTile(
            leading: Icon(Icons.video_library_outlined, color: Colors.purple),
            title: const Text('Video Tutorials'),
            trailing: const Icon(Icons.open_in_new, size: 18),
          ),
        ],
      ),
    );
  }
}

class _AboutCard extends StatelessWidget {
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _AboutCard({required this.theme, required this.colorScheme});

  @override
  Widget build(BuildContext context) {
    return Card(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Icon(Icons.auto_awesome, size: 28, color: colorScheme.primary),
            const SizedBox(width: 16),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('DASH', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.bold)),
                  Text('AI Operating System', style: theme.textTheme.bodySmall),
                  const SizedBox(height: 4),
                  Text('Version 1.0.0 (Build 1)', style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _TroubleshootingCard extends StatelessWidget {
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _TroubleshootingCard({required this.theme, required this.colorScheme});

  @override
  Widget build(BuildContext context) {
    final tips = [
      {
        'title': 'Not connecting?',
        'body': 'Ensure the backend server is running and the URL is correct in Settings.',
        'icon': Icons.wifi_off_rounded,
      },
      {
        'title': 'Slow responses?',
        'body': 'Try switching to a faster model in model settings or reduce context size.',
        'icon': Icons.speed_rounded,
      },
      {
        'title': 'App crashing?',
        'body': 'Clear app data in your device settings and restart.',
        'icon': Icons.emergency_rounded,
      },
      {
        'title': 'Search not finding?',
        'body': 'Make sure you have indexed conversations and memories. Try refreshing the search index.',
        'icon': Icons.search_off_rounded,
      },
    ];

    return Card(
      child: Column(
        children: tips.map((tip) {
          return ListTile(
            contentPadding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
            leading: Icon(tip['icon'] as IconData, size: 20, color: colorScheme.tertiary),
            title: Text(tip['title'] as String, style: theme.textTheme.bodySmall?.copyWith(fontWeight: FontWeight.w600)),
            subtitle: Text(tip['body'] as String, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.7))),
          );
        }).toList(),
      ),
    );
  }
}
