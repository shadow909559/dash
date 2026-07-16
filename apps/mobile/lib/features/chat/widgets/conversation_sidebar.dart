import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../models/conversation.dart';
import '../providers/conversation_provider.dart';

class ConversationSidebar extends ConsumerStatefulWidget {
  const ConversationSidebar({super.key});

  @override
  ConsumerState<ConversationSidebar> createState() =>
      _ConversationSidebarState();
}

class _ConversationSidebarState extends ConsumerState<ConversationSidebar> {
  final TextEditingController _searchController = TextEditingController();
  bool _isSearching = false;

  @override
  void dispose() {
    _searchController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final state = ref.watch(conversationListProvider);
    final activeId = ref.watch(activeConversationIdProvider);
    final theme = Theme.of(context);

    return Container(
      width: 320,
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          right: BorderSide(
            color: theme.colorScheme.outlineVariant,
            width: 1,
          ),
        ),
      ),
      child: Column(
        children: [
          _buildHeader(theme),
          _buildSearchBar(theme),
          if (state.isLoading)
            const Expanded(
              child: Center(child: CircularProgressIndicator()),
            )
          else if (state.errorMessage != null)
            _buildError(theme)
          else
            Expanded(
              child: _buildConversationList(state, activeId, theme),
            ),
        ],
      ),
    );
  }

  Widget _buildHeader(ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
      child: Row(
        children: [
          Icon(Icons.chat_bubble_outline,
              color: theme.colorScheme.primary, size: 24),
          const SizedBox(width: 12),
          Text(
            'Conversations',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.bold,
            ),
          ),
          const Spacer(),
          IconButton(
            icon: const Icon(Icons.add_circle_outline),
            tooltip: 'New chat',
            onPressed: () => _createNewConversation(),
            style: IconButton.styleFrom(
              foregroundColor: theme.colorScheme.primary,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildSearchBar(ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 4),
      child: TextField(
        controller: _searchController,
        onChanged: (value) {
          ref.read(conversationListProvider.notifier).search(value);
          setState(() => _isSearching = value.isNotEmpty);
        },
        decoration: InputDecoration(
          hintText: 'Search conversations...',
          prefixIcon: const Icon(Icons.search, size: 20),
          suffixIcon: _isSearching
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    ref.read(conversationListProvider.notifier).search('');
                    setState(() => _isSearching = false);
                  },
                )
              : null,
          filled: true,
          fillColor: theme.colorScheme.surfaceContainerHighest,
          border: OutlineInputBorder(
            borderRadius: BorderRadius.circular(12),
            borderSide: BorderSide.none,
          ),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          isDense: true,
        ),
        style: theme.textTheme.bodySmall,
      ),
    );
  }

  Widget _buildError(ThemeData theme) {
    return Expanded(
      child: Center(
        child: Padding(
          padding: const EdgeInsets.all(16),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.error_outline,
                  color: theme.colorScheme.error, size: 32),
              const SizedBox(height: 8),
              Text(
                'Failed to load conversations',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: theme.colorScheme.error,
                ),
              ),
              const SizedBox(height: 8),
              TextButton(
                onPressed: () =>
                    ref.read(conversationListProvider.notifier).load(),
                child: const Text('Retry'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildConversationList(
    ConversationListState state,
    String? activeId,
    ThemeData theme,
  ) {
    final conversations = _isSearching ? state.searchResults : state.conversations;

    if (conversations.isEmpty) {
      return Center(
        child: Padding(
          padding: const EdgeInsets.all(24),
          child: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              Icon(Icons.chat_bubble_outline,
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.3),
                  size: 48),
              const SizedBox(height: 12),
              Text(
                _isSearching ? 'No conversations found' : 'No conversations yet',
                style: theme.textTheme.bodyMedium?.copyWith(
                  color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
              if (!_isSearching) ...[
                const SizedBox(height: 8),
                Text(
                  'Start a new chat to begin',
                  style: theme.textTheme.bodySmall?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
                  ),
                ),
              ],
            ],
          ),
        ),
      );
    }

    // Separate pinned and active
    final pinned = conversations.where((c) => c.isPinned).toList();
    final active = conversations.where((c) => !c.isPinned).toList();

    return ListView(
      padding: const EdgeInsets.symmetric(vertical: 4),
      children: [
        if (pinned.isNotEmpty) ...[
          _buildSectionHeader('Pinned', theme),
          ...pinned.map((c) => _buildConversationTile(c, activeId, theme)),
          const Divider(height: 1),
        ],
        if (active.isNotEmpty) ...[
          _buildSectionHeader('Recent', theme),
          ...active.map((c) => _buildConversationTile(c, activeId, theme)),
        ],
      ],
    );
  }

  Widget _buildSectionHeader(String title, ThemeData theme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      child: Text(
        title,
        style: theme.textTheme.labelSmall?.copyWith(
          color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
          fontWeight: FontWeight.w600,
          letterSpacing: 0.5,
        ),
      ),
    );
  }

  Widget _buildConversationTile(
    Conversation conversation,
    String? activeId,
    ThemeData theme,
  ) {
    final isActive = conversation.id == activeId;

    return Material(
      color: isActive
          ? theme.colorScheme.primaryContainer.withValues(alpha: 0.5)
          : Colors.transparent,
      child: InkWell(
        onTap: () {
          ref.read(activeConversationIdProvider.notifier).state =
              conversation.id;
        },
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          child: Row(
            children: [
              // Pin icon
              if (conversation.isPinned)
                Padding(
                  padding: const EdgeInsets.only(right: 8),
                  child: Icon(Icons.push_pin,
                      size: 14,
                      color: theme.colorScheme.primary.withValues(alpha: 0.6)),
                ),
              // Content
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      conversation.displayTitle,
                      maxLines: 1,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodySmall?.copyWith(
                        fontWeight:
                            isActive ? FontWeight.w600 : FontWeight.normal,
                        color: isActive
                            ? theme.colorScheme.onPrimaryContainer
                            : theme.colorScheme.onSurface,
                      ),
                    ),
                    const SizedBox(height: 2),
                    Row(
                      children: [
                        Text(
                          conversation.timeAgo,
                          style: theme.textTheme.labelSmall?.copyWith(
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.4),
                            fontSize: 10,
                          ),
                        ),
                        if (conversation.messageCount > 0) ...[
                          const SizedBox(width: 8),
                          Text(
                            '${conversation.messageCount} msgs',
                            style: theme.textTheme.labelSmall?.copyWith(
                              color: theme.colorScheme.onSurface
                                  .withValues(alpha: 0.4),
                              fontSize: 10,
                            ),
                          ),
                        ],
                      ],
                    ),
                  ],
                ),
              ),
              // Actions
              PopupMenuButton<String>(
                icon: Icon(Icons.more_horiz,
                    size: 18,
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.5)),
                onSelected: (value) =>
                    _handleAction(value, conversation, theme),
                itemBuilder: (context) => [
                  const PopupMenuItem(
                    value: 'rename',
                    child: ListTile(
                      leading: Icon(Icons.edit_outlined, size: 18),
                      title: Text('Rename'),
                      dense: true,
                    ),
                  ),
                  PopupMenuItem(
                    value: conversation.isPinned ? 'unpin' : 'pin',
                    child: ListTile(
                      leading: Icon(
                        conversation.isPinned
                            ? Icons.push_pin_outlined
                            : Icons.push_pin,
                        size: 18,
                      ),
                      title: Text(conversation.isPinned ? 'Unpin' : 'Pin'),
                      dense: true,
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'archive',
                    child: ListTile(
                      leading: Icon(Icons.archive_outlined, size: 18),
                      title: Text('Archive'),
                      dense: true,
                    ),
                  ),
                  const PopupMenuItem(
                    value: 'delete',
                    child: ListTile(
                      leading: Icon(Icons.delete_outline, size: 18),
                      title: Text('Delete'),
                      dense: true,
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  void _createNewConversation() {
    ref.read(activeConversationIdProvider.notifier).state = null;
    ref.read(conversationListProvider.notifier).create();
  }

  void _handleAction(
    String action,
    Conversation conversation,
    ThemeData theme,
  ) {
    final notifier = ref.read(conversationListProvider.notifier);

    switch (action) {
      case 'rename':
        _showRenameDialog(conversation, theme);
        break;
      case 'pin':
      case 'unpin':
        notifier.togglePin(conversation.id);
        break;
      case 'archive':
        notifier.archive(conversation.id);
        break;
      case 'delete':
        _showDeleteConfirmation(conversation, theme);
        break;
    }
  }

  void _showRenameDialog(Conversation conversation, ThemeData theme) {
    final controller = TextEditingController(text: conversation.title);

    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Rename conversation'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Enter new name',
          ),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final newTitle = controller.text.trim();
              if (newTitle.isNotEmpty) {
                ref
                    .read(conversationListProvider.notifier)
                    .rename(conversation.id, newTitle);
              }
              Navigator.pop(context);
            },
            child: const Text('Rename'),
          ),
        ],
      ),
    );
  }

  void _showDeleteConfirmation(Conversation conversation, ThemeData theme) {
    showDialog(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Delete conversation?'),
        content: Text(
          'This will permanently delete "${conversation.displayTitle}" and all its messages.',
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Cancel'),
          ),
          FilledButton(
            style: FilledButton.styleFrom(
              backgroundColor: theme.colorScheme.error,
            ),
            onPressed: () {
              ref
                  .read(conversationListProvider.notifier)
                  .delete(conversation.id);
              Navigator.pop(context);
            },
            child: const Text('Delete'),
          ),
        ],
      ),
    );
  }
}