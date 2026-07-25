import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:shimmer/shimmer.dart';

import 'models/conversation.dart';
import 'providers/conversation_provider.dart';
import 'services/conversation_repository.dart';

class ConversationHistoryPage extends ConsumerStatefulWidget {
  const ConversationHistoryPage({super.key});

  @override
  ConsumerState<ConversationHistoryPage> createState() =>
      _ConversationHistoryPageState();
}

class _ConversationHistoryPageState extends ConsumerState<ConversationHistoryPage> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  bool _isSearching = false;
  bool _showArchived = false;
  bool _isLoadingMore = false;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      ref.read(conversationListProvider.notifier).load(includeArchived: _showArchived);
    });
    _scrollController.addListener(_onScroll);
  }

  @override
  void dispose() {
    _searchController.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    super.dispose();
  }

  void _onScroll() {
    if (!_scrollController.hasClients) return;
    final max = _scrollController.position.maxScrollExtent;
    final current = _scrollController.position.pixels;
    if (max - current < 200 && !_isLoadingMore) {
      // Infinite scroll can be implemented here when backend supports pagination
    }
  }

  Future<void> _refresh() async {
    await ref.read(conversationListProvider.notifier).load(includeArchived: _showArchived);
  }

  void _onSearchChanged(String value) {
    setState(() => _isSearching = value.isNotEmpty);
    ref.read(conversationListProvider.notifier).search(value);
  }

  void _toggleArchived() {
    setState(() {
      _showArchived = !_showArchived;
      _searchController.clear();
      _isSearching = false;
    });
    ref.read(conversationListProvider.notifier).load(includeArchived: _showArchived);
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(conversationListProvider);
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Scaffold(
      appBar: AppBar(
        title: Text(_showArchived ? 'Archived Chats' : 'Conversations'),
        actions: [
          IconButton(
            icon: Icon(_showArchived ? Icons.unarchive_outlined : Icons.archive_outlined),
            tooltip: _showArchived ? 'Show active' : 'Show archived',
            onPressed: _toggleArchived,
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _refresh,
        child: Column(
          children: [
            Padding(
              padding: const EdgeInsets.fromLTRB(16, 8, 16, 4),
              child: TextField(
                controller: _searchController,
                onChanged: _onSearchChanged,
                decoration: InputDecoration(
                  hintText: 'Search conversations...',
                  prefixIcon: const Icon(Icons.search, size: 20),
                  suffixIcon: _isSearching
                      ? IconButton(
                          icon: const Icon(Icons.clear, size: 18),
                          onPressed: () {
                            _searchController.clear();
                            _onSearchChanged('');
                          },
                        )
                      : null,
                  filled: true,
                  fillColor: colorScheme.surfaceContainerHighest,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(12),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
                  isDense: true,
                ),
                style: theme.textTheme.bodySmall,
              ),
            ),
            Expanded(child: _buildBody(state, theme, colorScheme)),
          ],
        ),
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: () async {
          final repo = ref.read(conversationRepositoryProvider);
          final newConv = await repo.create(title: 'New Chat ${DateTime.now().millisecondsSinceEpoch % 10000}');
          if (!mounted) return;
          ref.read(activeConversationIdProvider.notifier).state = newConv.id;
          if (mounted) Navigator.pop(context);
        },
        icon: const Icon(Icons.add_rounded),
        label: const Text('New Chat'),
      ),
    );
  }

  Widget _buildBody(ConversationListState state, ThemeData theme, ColorScheme colorScheme) {
    if (state.isLoading && state.conversations.isEmpty) {
      return _buildLoadingSkeleton(theme);
    }

    List<Conversation> conversations;
    if (_isSearching) {
      conversations = state.searchResults;
    } else if (state.searchQuery != null && state.searchQuery!.isNotEmpty) {
      conversations = state.searchResults;
    } else {
      conversations = state.conversations;
    }

    if (state.errorMessage != null && conversations.isEmpty) {
      return _buildErrorState(state.errorMessage!, theme);
    }

    if (conversations.isEmpty) {
      return _buildEmptyState(theme, _isSearching || (state.searchQuery != null && state.searchQuery!.isNotEmpty));
    }

    final pinned = conversations.where((c) => c.isPinned).toList();
    final active = conversations.where((c) => !c.isPinned).toList();

    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: (pinned.isNotEmpty ? 1 : 0) + (active.isNotEmpty ? 1 : 0) + active.length + pinned.length,
      itemBuilder: (context, index) {
        if (index < pinned.length) {
          final conv = pinned[index];
          return _buildConversationTile(conv, theme, colorScheme);
        }

        final currentPinIndex = pinned.length;

        if (index == currentPinIndex && pinned.isNotEmpty) {
          return Padding(
            padding: const EdgeInsets.only(left: 16, top: 12, bottom: 4),
            child: Text(
              'Recent',
              style: theme.textTheme.labelSmall?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.5),
                fontWeight: FontWeight.w600,
                letterSpacing: 0.5,
              ),
            ),
          );
        }

        final adjustedIndex = index - currentPinIndex - (pinned.isNotEmpty ? 1 : 0);

        if (adjustedIndex < active.length) {
          final conv = active[adjustedIndex];
          return _buildConversationTile(conv, theme, colorScheme);
        }

        return const SizedBox.shrink();
      },
    );
  }

  Widget _buildConversationTile(Conversation conv, ThemeData theme, ColorScheme colorScheme) {
    final subtitle = [
      if (conv.messageCount > 0) '${conv.messageCount} messages',
      if (conv.model != null) conv.model!,
    ].where((s) => s.isNotEmpty).join(' · ');

    return Dismissible(
      key: Key(conv.id),
      direction: DismissDirection.endToStart,
      background: Container(
        alignment: Alignment.centerRight,
        padding: const EdgeInsets.symmetric(horizontal: 20),
        color: colorScheme.errorContainer,
        child: Icon(Icons.delete_outline, color: colorScheme.onErrorContainer),
      ),
      confirmDismiss: (direction) async {
        final confirm = await showDialog<bool>(
          context: context,
          builder: (ctx) => AlertDialog(
            title: const Text('Delete conversation?'),
            content: Text('This will permanently delete "${conv.displayTitle}" and all its messages.'),
            actions: [
              TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
              FilledButton(
                style: FilledButton.styleFrom(backgroundColor: colorScheme.error),
                onPressed: () => Navigator.pop(ctx, true),
                child: const Text('Delete'),
              ),
            ],
          ),
        );
        return confirm ?? false;
      },
      onDismissed: (direction) async {
        final success = await ref.read(conversationListProvider.notifier).delete(conv.id);
        if (!success && mounted) {
          ScaffoldMessenger.of(context).showSnackBar(
            SnackBar(content: Text('Failed to delete "${conv.displayTitle}"')),
          );
        }
      },
      child: ListTile(
        leading: CircleAvatar(
          backgroundColor: conv.isPinned
              ? colorScheme.primaryContainer
              : colorScheme.surfaceContainerHighest,
          child: Icon(
            conv.isPinned ? Icons.push_pin : Icons.chat_bubble_outline,
            size: 18,
            color: conv.isPinned ? colorScheme.primary : colorScheme.onSurfaceVariant,
          ),
        ),
        title: Text(
          conv.displayTitle,
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: theme.textTheme.bodyMedium?.copyWith(
            fontWeight: conv.isPinned ? FontWeight.w600 : FontWeight.normal,
          ),
        ),
        subtitle: Text(
          subtitle.isEmpty ? conv.timeAgo : '$subtitle · ${conv.timeAgo}',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
          style: theme.textTheme.bodySmall?.copyWith(
            color: colorScheme.onSurfaceVariant,
          ),
        ),
        trailing: Icon(Icons.chevron_right, color: colorScheme.onSurfaceVariant),
        onTap: () async {
          ref.read(activeConversationIdProvider.notifier).state = conv.id;
          if (mounted) Navigator.pop(context);
        },
      ),
    );
  }

  Widget _buildLoadingSkeleton(ThemeData theme) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(vertical: 8),
      itemCount: 8,
      itemBuilder: (context, index) => Padding(
        padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 4),
        child: Shimmer.fromColors(
          baseColor: theme.colorScheme.surfaceContainerHighest.withValues(alpha: 0.5),
          highlightColor: theme.colorScheme.surfaceContainerHighest,
          child: Row(
            children: [
              Container(
                width: 40,
                height: 40,
                decoration: BoxDecoration(
                  color: theme.colorScheme.surfaceContainerHighest,
                  shape: BoxShape.circle,
                ),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Container(
                      width: double.infinity,
                      height: 14,
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                    const SizedBox(height: 6),
                    Container(
                      width: MediaQuery.of(context).size.width * 0.4,
                      height: 10,
                      decoration: BoxDecoration(
                        color: theme.colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(4),
                      ),
                    ),
                  ],
                ),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildErrorState(String error, ThemeData theme) {
    final colorScheme = theme.colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: colorScheme.errorContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.error_outline, size: 40, color: colorScheme.error),
            ),
            const SizedBox(height: 16),
            Text('Something went wrong', style: theme.textTheme.titleMedium?.copyWith(fontWeight: FontWeight.w600)),
            const SizedBox(height: 8),
            Text(error, textAlign: TextAlign.center, style: theme.textTheme.bodySmall?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
            const SizedBox(height: 16),
            FilledButton.tonal(onPressed: _refresh, child: const Text('Retry')),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme, bool isSearchResult) {
    final colorScheme = theme.colorScheme;
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(
                color: colorScheme.primaryContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(Icons.chat_bubble_outline_rounded, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text(
              isSearchResult ? 'No results found' : 'No conversations yet',
              style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold),
            ),
            const SizedBox(height: 8),
            Text(
              isSearchResult ? 'Try a different search term' : 'Start a new chat to begin your journey',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)),
            ),
          ],
        ),
      ),
    );
  }
}