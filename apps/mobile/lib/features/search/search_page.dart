import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:intl/intl.dart';

import '../../../core/routing/app_routes.dart';
import '../search/providers/search_provider.dart';
import '../plugins/models/plugin.dart';

class SearchPage extends ConsumerStatefulWidget {
  const SearchPage({super.key});

  @override
  ConsumerState<SearchPage> createState() => _SearchPageState();
}

class _SearchPageState extends ConsumerState<SearchPage> {
  final TextEditingController _controller = TextEditingController();

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final searchState = ref.watch(searchProvider);
    final notifier = ref.read(searchProvider.notifier);

    final shouldShowResults = searchState.query.isNotEmpty;
    final isSearching = searchState.isSearching;

    return Scaffold(
      appBar: AppBar(
        automaticallyImplyLeading: false,
        titleSpacing: 0,
        title: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
          child: TextField(
            controller: _controller,
            autofocus: true,
            onChanged: notifier.setQuery,
            decoration: InputDecoration(
              hintText: 'Search conversations, memory, tasks...',
              prefixIcon: const Icon(Icons.search, size: 20),
              suffixIcon: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  if (_controller.text.isNotEmpty)
                    IconButton(
                      onPressed: () {
                        _controller.clear();
                        notifier.setQuery('');
                      },
                      icon: const Icon(Icons.close, size: 18),
                    ),
                  if (_controller.text.isEmpty)
                    IconButton(
                      onPressed: () => context.pop(),
                      icon: const Icon(Icons.arrow_back, size: 18),
                    ),
                ],
              ),
              filled: true,
              fillColor: colorScheme.surfaceContainerHighest,
              border: OutlineInputBorder(borderRadius: BorderRadius.circular(10), borderSide: BorderSide.none),
              contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
              isDense: true,
            ),
          ),
        ),
      ),
      body: shouldShowResults ? _buildResults(searchState, theme, colorScheme, notifier, isSearching) : _buildRecent(theme, colorScheme, notifier, searchState),
    );
  }

  Widget _buildResults(
    SearchState state,
    ThemeData theme,
    ColorScheme colorScheme,
    SearchNotifier notifier,
    bool isSearching,
  ) {
    final tabs = SearchTab.values;
    final selectedIndex = tabs.indexOf(state.selectedTab);

    return Column(
      children: [
        _TabBar(selectedIndex: selectedIndex, onTap: (index) => notifier.selectTab(tabs[index])),
        Expanded(child: _buildTabBody(state, theme, colorScheme, isSearching, notifier: notifier)),
      ],
    );
  }

  Widget _buildTabBody(SearchState state, ThemeData theme, ColorScheme colorScheme, bool isSearching, {SearchNotifier? notifier}) {
    if (isSearching) {
      return Center(
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(width: 24, height: 24, child: CircularProgressIndicator(strokeWidth: 2)),
            const SizedBox(height: 16),
            Text('Searching...', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      );
    }

    final filtered = state.filteredResults;

    if (filtered.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(32),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.search_off_rounded, size: 48, color: colorScheme.onSurface.withValues(alpha: 0.3)),
              const SizedBox(height: 16),
              Text('No results found', style: theme.textTheme.bodyLarge?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
              Text('Try a different search term', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.4))),
            ],
          ),
        ),
      );
    }

    return RefreshIndicator(
      onRefresh: () async {
        notifier?.setQuery(state.query);
      },
      child: ListView.separated(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
        itemCount: filtered.length,
        separatorBuilder: (_, __) => const SizedBox(height: 8),
        itemBuilder: (context, index) {
          final item = filtered[index];
          return _ResultCard(item: item, theme: theme, colorScheme: colorScheme);
        },
      ),
    );
  }

  Widget _buildRecent(
    ThemeData theme,
    ColorScheme colorScheme,
    SearchNotifier notifier,
    SearchState state,
  ) {
    final recent = state.recentSearches;

    return Column(
      children: [
        Padding(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 16),
          child: Row(
            children: [
              Text('Recent', style: theme.textTheme.titleSmall?.copyWith(fontWeight: FontWeight.w600, color: colorScheme.onSurface.withValues(alpha: 0.7))),
              const Spacer(),
              if (recent.isNotEmpty)
                TextButton.icon(
                  onPressed: notifier.clearRecentSearches,
                  icon: Icon(Icons.delete_outline, size: 14, color: colorScheme.error),
                  label: Text('Clear', style: TextStyle(color: colorScheme.error)),
                ),
            ],
          ),
        ),
        Expanded(
          child: recent.isEmpty
              ? Center(child: Text('No recent searches', style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.5))))
              : ListView.builder(
                  padding: const EdgeInsets.symmetric(horizontal: 16),
                  itemCount: recent.length,
                  itemBuilder: (context, index) {
                    final query = recent[index];
                    return ListTile(
                      contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                      leading: Icon(Icons.history_outlined, size: 18, color: colorScheme.onSurface.withValues(alpha: 0.5)),
                      title: Text(query, style: theme.textTheme.bodyMedium),
                      trailing: IconButton(
                        onPressed: () {
                          _controller.text = query;
                          notifier.setQuery(query);
                        },
                        icon: Icon(Icons.arrow_upward_rounded, size: 16, color: colorScheme.primary),
                        tooltip: 'Search again',
                      ),
                      onTap: () {
                        _controller.text = query;
                        notifier.setQuery(query);
                      },
                    );
                  },
                ),
        ),
      ],
    );
  }
}

class _TabBar extends StatelessWidget {
  final int selectedIndex;
  final ValueChanged<int> onTap;

  const _TabBar({required this.selectedIndex, required this.onTap});

  static const _labels = ['All', 'Chats', 'Memory', 'Tasks', 'Files'];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(bottom: BorderSide(color: theme.colorScheme.outlineVariant, width: 0.5)),
      ),
      child: SingleChildScrollView(
        scrollDirection: Axis.horizontal,
        child: Row(
          children: List.generate(_labels.length, (index) {
            final isSelected = index == selectedIndex;
            return InkWell(
              onTap: () => onTap(index),
              child: AnimatedContainer(
                duration: const Duration(milliseconds: 200),
                padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
                decoration: isSelected
                    ? BoxDecoration(border: Border(bottom: BorderSide(color: theme.colorScheme.primary, width: 2)))
                    : null,
                child: Text(
                  _labels[index],
                  style: (theme.textTheme.labelLarge ?? theme.textTheme.bodyMedium)?.copyWith(
                    fontWeight: isSelected ? FontWeight.w600 : FontWeight.w500,
                    color: isSelected ? theme.colorScheme.primary : theme.colorScheme.onSurface.withValues(alpha: 0.6),
                  ),
                ),
              ),
            );
          }),
        ),
      ),
    );
  }
}

class _ResultCard extends StatelessWidget {
  final SearchResultItem item;
  final ThemeData theme;
  final ColorScheme colorScheme;

  const _ResultCard({
    required this.item,
    required this.theme,
    required this.colorScheme,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      child: InkWell(
        borderRadius: BorderRadius.circular(10),
        onTap: () {},
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                padding: const EdgeInsets.all(8),
                decoration: BoxDecoration(
                  color: _categoryColor.withValues(alpha: 0.12),
                  borderRadius: BorderRadius.circular(8),
                ),
                child: Icon(_categoryIcon, size: 18, color: _categoryColor),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(item.title, style: theme.textTheme.bodyMedium?.copyWith(fontWeight: FontWeight.w500), maxLines: 1, overflow: TextOverflow.ellipsis),
                        ),
                        Container(
                          padding: const EdgeInsets.symmetric(horizontal: 6, vertical: 2),
                          decoration: BoxDecoration(
                            color: colorScheme.primaryContainer.withValues(alpha: 0.4),
                            borderRadius: BorderRadius.circular(6),
                          ),
                          child: Text(item.category, style: theme.textTheme.labelSmall),
                        ),
                      ],
                    ),
                    const SizedBox(height: 4),
                    Text(item.snippet, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)), maxLines: 2, overflow: TextOverflow.ellipsis),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  IconData get _categoryIcon {
    switch (item.category) {
      case 'conversation':
        return Icons.chat_bubble_outline;
      case 'memory':
        return Icons.memory;
      case 'task':
        return Icons.task_alt;
      case 'file':
        return Icons.description_outlined;
      default:
        return Icons.search;
    }
  }

  Color get _categoryColor {
    switch (item.category) {
      case 'conversation':
        return theme.colorScheme.primary;
      case 'memory':
        return theme.colorScheme.tertiary;
      case 'task':
        return theme.colorScheme.secondary;
      case 'file':
        return Colors.grey;
      default:
        return theme.colorScheme.outline;
    }
  }
}
