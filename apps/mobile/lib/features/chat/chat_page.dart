import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/services/websocket_service.dart';
import '../../core/theme/app_theme.dart';
import 'models/chat_message.dart';
import 'providers/chat_provider.dart';
import 'providers/conversation_provider.dart';
import 'widgets/conversation_sidebar.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage>
    with AutomaticKeepAliveClientMixin {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();
  bool _isSidebarOpen = true;
  String? _lastLoadedConversationId;

  @override
  bool get wantKeepAlive => true;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _loadActiveConversation();
    });
    _scrollController.addListener(_onScroll);
  }

  void _onScroll() {
    // Placeholder for pull-to-load-more / infinite scroll
  }

  void _loadActiveConversation() {
    final activeId = ref.read(activeConversationIdProvider);
    if (activeId != null && activeId != _lastLoadedConversationId) {
      _lastLoadedConversationId = activeId;
      ref.read(chatProvider.notifier).loadConversationMessages(activeId);
    }
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.removeListener(_onScroll);
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom({bool force = false}) {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (!mounted) return;
      if (!_scrollController.hasClients) return;

      final max = _scrollController.position.maxScrollExtent;
      final current = _scrollController.position.pixels;
      final distanceToBottom = (max - current).abs();

      if (!force && distanceToBottom > 120) return;

      _scrollController.animateTo(
        max,
        duration: const Duration(milliseconds: 200),
        curve: Curves.easeOutCubic,
      );
    });
  }

  void _sendMessage() {
    final message = _controller.text.trim();
    if (message.isEmpty) return;

    final activeId = ref.read(activeConversationIdProvider);
    ref.read(chatProvider.notifier).sendMessage(
          message,
          conversationId: activeId,
        );
    _controller.clear();
    _focusNode.requestFocus();

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom(force: true);
    });
  }

  void _handleKeyEvent(KeyEvent event) {
    if (event is KeyDownEvent) {
      if (event.logicalKey == LogicalKeyboardKey.enter &&
          !(HardwareKeyboard.instance.isShiftPressed)) {
        _sendMessage();
      }
    }
  }

  @override
  Widget build(BuildContext context) {
    super.build(context);
    final screenWidth = MediaQuery.of(context).size.width;
    final isWideScreen = screenWidth >= 768;

    if (isWideScreen && !_isSidebarOpen) {
      WidgetsBinding.instance.addPostFrameCallback((_) {
        if (mounted) setState(() => _isSidebarOpen = true);
      });
    }

    return Row(
      children: [
        if (isWideScreen && _isSidebarOpen)
          SizedBox(
            width: 320,
            child: ConversationSidebar(
              onConversationSelected: () {
                if (screenWidth < 1024) {
                  setState(() => _isSidebarOpen = false);
                }
              },
            ),
          ),
        Expanded(
          child: Scaffold(
            appBar: _buildAppBar(context, isWideScreen),
            body: Column(
              children: [
                _buildConnectionBar(context),
                Expanded(child: _buildMessagesArea(context)),
                _buildTypingIndicator(context),
                _buildInputArea(context),
              ],
            ),
          ),
        ),
      ],
    );
  }

  PreferredSizeWidget _buildAppBar(BuildContext context, bool isWideScreen) {
    final theme = Theme.of(context);
    final activeId = ref.watch(activeConversationIdProvider);

    return AppBar(
      leading: isWideScreen
          ? null
          : IconButton(
              icon: const Icon(Icons.menu),
              onPressed: () => setState(() => _isSidebarOpen = !_isSidebarOpen),
            ),
      title: Row(
        children: [
          if (isWideScreen)
            IconButton(
              icon: Icon(
                _isSidebarOpen ? Icons.chevron_left : Icons.chevron_right,
              ),
              onPressed: () =>
                  setState(() => _isSidebarOpen = !_isSidebarOpen),
              tooltip: 'Toggle sidebar',
            ),
          const SizedBox(width: 4),
          Text(
            activeId != null ? 'Chat' : 'New Chat',
            style: theme.textTheme.titleMedium?.copyWith(
              fontWeight: FontWeight.w600,
            ),
          ),
        ],
      ),
      actions: [
        if (ref.watch(chatProvider).isStreaming)
          TextButton.icon(
            onPressed: () =>
                ref.read(chatProvider.notifier).cancelStreaming(),
            icon: const Icon(Icons.stop, size: 18),
            label: const Text('Stop'),
            style: TextButton.styleFrom(
              foregroundColor: theme.colorScheme.error,
            ),
          ),
        IconButton(
          icon: const Icon(Icons.delete_outline),
          tooltip: 'Clear chat',
          onPressed: () => _showClearChatDialog(context),
        ),
      ],
    );
  }

  Widget _buildConnectionBar(BuildContext context) {
    final wsState = ref.watch(webSocketServiceProvider);
    final chatState = ref.watch(chatProvider);

    if (wsState.status == WebSocketStatus.connected) {
      return const SizedBox.shrink();
    }

    Color barColor;
    String text;
    IconData icon;

    switch (wsState.status) {
      case WebSocketStatus.connecting:
        barColor = Colors.blue.shade700;
        text = 'Connecting...';
        icon = Icons.cloud_upload;
        break;
      case WebSocketStatus.reconnecting:
        barColor = Colors.orange.shade700;
        text = 'Reconnecting...';
        icon = Icons.sync;
        break;
      case WebSocketStatus.error:
        barColor = Colors.red.shade700;
        text = chatState.errorMessage ?? 'Connection error';
        icon = Icons.error;
        break;
      default:
        barColor = Colors.grey.shade700;
        text = 'Offline';
        icon = Icons.cloud_off;
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: barColor,
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (wsState.status == WebSocketStatus.connecting ||
              wsState.status == WebSocketStatus.reconnecting)
            const SizedBox(
              width: 14,
              height: 14,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            )
          else
            Icon(icon, color: Colors.white, size: 14),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Colors.white, fontSize: 12),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (wsState.status == WebSocketStatus.error)
            TextButton(
              onPressed: () =>
                  ref.read(webSocketServiceProvider.notifier).connect(),
              style: TextButton.styleFrom(
                foregroundColor: Colors.white,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
              child: const Text('Retry', style: TextStyle(fontSize: 12)),
            ),
        ],
      ),
    );
  }

  Widget _buildMessagesArea(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final theme = Theme.of(context);

    if (chatState.isTyping && chatState.messages.isEmpty) {
      return _buildLoadingState(theme);
    }

    if (chatState.errorMessage != null && chatState.messages.isEmpty) {
      return _buildErrorState(theme, chatState.errorMessage!);
    }

    if (chatState.messages.isEmpty) {
      return _buildEmptyState(theme);
    }

    WidgetsBinding.instance.addPostFrameCallback((_) {
      _scrollToBottom();
    });

    return GestureDetector(
      onTap: () => _focusNode.unfocus(),
      child: Stack(
        children: [
          ListView.builder(
            controller: _scrollController,
            padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
            itemCount: chatState.messages.length,
            itemBuilder: (context, index) {
              final message = chatState.messages[index];
              return _MessageBubble(
                message: message,
                isLast: index == chatState.messages.length - 1,
                onCopy: () {
                  Clipboard.setData(ClipboardData(text: message.content));
                  ScaffoldMessenger.of(context).showSnackBar(
                    const SnackBar(
                      content: Text('Message copied'),
                      duration: Duration(seconds: 1),
                    ),
                  );
                },
              );
            },
          ),
          Positioned(
            right: 12,
            bottom: 12,
            child: AnimatedOpacity(
              opacity: _scrollController.hasClients &&
                      _scrollController.position.pixels <
                          _scrollController.position.maxScrollExtent - 200
                  ? 1.0
                  : 0.0,
              duration: const Duration(milliseconds: 200),
              child: FloatingActionButton.small(
                onPressed: () => _scrollToBottom(force: true),
                heroTag: 'scrollToBottom',
                child: const Icon(Icons.arrow_downward, size: 18),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildLoadingState(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            const SizedBox(
              width: 32,
              height: 32,
              child: CircularProgressIndicator(strokeWidth: 3),
            ),
            const SizedBox(height: 16),
            Text(
              'Loading messages...',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.5),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildErrorState(ThemeData theme, String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: theme.colorScheme.errorContainer.withValues(alpha: 0.3),
                shape: BoxShape.circle,
              ),
              child: Icon(
                Icons.error_outline,
                size: 40,
                color: theme.colorScheme.error,
              ),
            ),
            const SizedBox(height: 16),
            Text(
              'Something went wrong',
              style: theme.textTheme.titleMedium?.copyWith(
                fontWeight: FontWeight.w600,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              error,
              textAlign: TextAlign.center,
              style: theme.textTheme.bodySmall?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: 16),
            FilledButton.tonal(
              onPressed: () => ref.read(chatProvider.notifier).reconnect(),
              child: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
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
              child: Icon(
                Icons.chat_bubble_outline,
                size: 48,
                color: colorScheme.primary,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Start a conversation',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Send a message to begin chatting with Dash AI',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildTypingIndicator(BuildContext context) {
    final chatState = ref.watch(chatProvider);

    if (!chatState.isStreaming && !chatState.isTyping) {
      return const SizedBox.shrink();
    }

    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          const _TypingDots(),
          const SizedBox(width: 8),
          Text(
            chatState.isStreaming ? 'Thinking...' : 'Typing...',
            style: Theme.of(context).textTheme.bodySmall?.copyWith(
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withValues(alpha: 0.5),
                ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputArea(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final chatState = ref.watch(chatProvider);

    return Container(
      padding: EdgeInsets.only(
        left: 16,
        right: 16,
        top: 8,
        bottom: MediaQuery.of(context).padding.bottom + 8,
      ),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          top: BorderSide(
            color: colorScheme.outlineVariant,
            width: 0.5,
          ),
        ),
      ),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.end,
        children: [
          Expanded(
            child: KeyboardListener(
              focusNode: FocusNode(),
              onKeyEvent: _handleKeyEvent,
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                maxLines: 6,
                minLines: 1,
                textInputAction: TextInputAction.newline,
                textCapitalization: TextCapitalization.sentences,
                decoration: InputDecoration(
                  hintText: 'Type a message...',
                  filled: true,
                  fillColor: colorScheme.surfaceContainerHighest,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
                style: theme.textTheme.bodyMedium,
              ),
            ),
          ),
          const SizedBox(width: 8),
          _buildSendButton(chatState, colorScheme),
        ],
      ),
    );
  }

  Widget _buildSendButton(ChatState chatState, ColorScheme colorScheme) {
    return AnimatedBuilder(
      animation: Listenable.merge([]),
      builder: (context, child) {
        final isStreaming = chatState.isStreaming;
        return IconButton(
          onPressed: isStreaming
              ? () => ref.read(chatProvider.notifier).cancelStreaming()
              : _sendMessage,
          icon: Icon(
            isStreaming ? Icons.stop : Icons.send_rounded,
            size: isStreaming ? 20 : 22,
          ),
          style: IconButton.styleFrom(
            backgroundColor: isStreaming
                ? colorScheme.errorContainer
                : colorScheme.primary,
            foregroundColor: isStreaming
                ? colorScheme.onErrorContainer
                : colorScheme.onPrimary,
            shape: RoundedRectangleBorder(
              borderRadius: BorderRadius.circular(12),
            ),
            padding: const EdgeInsets.all(12),
          ),
        );
      },
    );
  }

  void _showClearChatDialog(BuildContext context) {
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Clear chat'),
        content: const Text(
            'This will clear all messages in the current conversation.'),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              ref.read(chatProvider.notifier).clearMessages();
              Navigator.pop(ctx);
            },
            child: const Text('Clear'),
          ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Message Bubble Widget
// ─────────────────────────────────────────────────────────────────────

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    required this.isLast,
    required this.onCopy,
  });

  final ChatMessage message;
  final bool isLast;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final chatTheme = Theme.of(context).extension<ChatTheme>();
    final isUser = message.isUser;

    return Padding(
      padding: EdgeInsets.only(
        top: 4,
        bottom: isLast ? 4 : 2,
      ),
      child: Column(
        crossAxisAlignment:
            isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start,
        children: [
          Row(
            mainAxisAlignment:
                isUser ? MainAxisAlignment.end : MainAxisAlignment.start,
            crossAxisAlignment: CrossAxisAlignment.end,
            children: [
              if (!isUser) ...[
                _Avatar(
                  icon: Icons.auto_awesome,
                  color: chatTheme?.assistantAvatarColor ??
                      theme.colorScheme.secondaryContainer,
                  size: 28,
                ),
                const SizedBox(width: 8),
              ],
              Flexible(
                child: _BubbleContent(
                  message: message,
                  isUser: isUser,
                  chatTheme: chatTheme,
                  theme: theme,
                  onCopy: onCopy,
                ),
              ),
              if (isUser) ...[
                const SizedBox(width: 8),
                _Avatar(
                  icon: Icons.person,
                  color: chatTheme?.userAvatarColor ??
                      theme.colorScheme.primaryContainer,
                  size: 28,
                ),
              ],
            ],
          ),
          Padding(
            padding: EdgeInsets.only(
              left: isUser ? 0 : 36,
              right: isUser ? 36 : 0,
              top: 2,
            ),
            child: _buildTimestamp(context),
          ),
        ],
      ),
    );
  }

  Widget _buildTimestamp(BuildContext context) {
    final theme = Theme.of(context);
    final timeStr = _formatTime(message.timestamp);
    final statusStr = _statusString();

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          timeStr,
          style: theme.textTheme.labelSmall?.copyWith(
            fontSize: 10,
            color: theme.colorScheme.onSurface.withValues(alpha: 0.4),
          ),
        ),
        if (statusStr != null) ...[
          const SizedBox(width: 4),
          Icon(
            _statusIcon(),
            size: 12,
            color: _statusColor(theme),
          ),
          const SizedBox(width: 2),
          Text(
            statusStr,
            style: theme.textTheme.labelSmall?.copyWith(
              fontSize: 10,
              color: _statusColor(theme),
            ),
          ),
        ],
      ],
    );
  }

  String _formatTime(DateTime dt) {
    final now = DateTime.now();
    final diff = now.difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) {
      return '${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
    }
    return '${dt.month}/${dt.day} ${dt.hour.toString().padLeft(2, '0')}:${dt.minute.toString().padLeft(2, '0')}';
  }

  String? _statusString() {
    switch (message.status) {
      case MessageStatus.sending:
        return 'Sending...';
      case MessageStatus.pending:
        return 'Pending';
      case MessageStatus.streaming:
        return null;
      case MessageStatus.error:
        return 'Failed';
      default:
        return null;
    }
  }

  IconData _statusIcon() {
    switch (message.status) {
      case MessageStatus.sending:
      case MessageStatus.pending:
        return Icons.access_time;
      case MessageStatus.error:
        return Icons.error_outline;
      default:
        return Icons.check;
    }
  }

  Color _statusColor(ThemeData theme) {
    switch (message.status) {
      case MessageStatus.error:
        return theme.colorScheme.error;
      case MessageStatus.sending:
      case MessageStatus.pending:
        return theme.colorScheme.onSurface.withValues(alpha: 0.4);
      default:
        return Colors.green;
    }
  }
}

// ─────────────────────────────────────────────────────────────────────
// Bubble Content
// ─────────────────────────────────────────────────────────────────────

class _BubbleContent extends StatelessWidget {
  const _BubbleContent({
    required this.message,
    required this.isUser,
    required this.chatTheme,
    required this.theme,
    required this.onCopy,
  });

  final ChatMessage message;
  final bool isUser;
  final ChatTheme? chatTheme;
  final ThemeData theme;
  final VoidCallback onCopy;

  @override
  Widget build(BuildContext context) {
    final bgColor = isUser
        ? chatTheme?.userBubbleColor ?? theme.colorScheme.primaryContainer
        : chatTheme?.assistantBubbleColor ?? const Color(0xFFF0F4F8);
    final textColor = isUser
        ? chatTheme?.userBubbleTextColor ?? theme.colorScheme.onPrimaryContainer
        : chatTheme?.assistantBubbleTextColor ?? theme.colorScheme.onSurface;
    final shadowColor =
        chatTheme?.bubbleShadowColor ?? Colors.black.withValues(alpha: 0.06);

    return Container(
      constraints: BoxConstraints(
        maxWidth: MediaQuery.of(context).size.width * 0.75,
      ),
      padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
      decoration: BoxDecoration(
        color: bgColor,
        borderRadius: BorderRadius.only(
          topLeft: const Radius.circular(16),
          topRight: const Radius.circular(16),
          bottomLeft: Radius.circular(isUser ? 16 : 4),
          bottomRight: Radius.circular(isUser ? 4 : 16),
        ),
        boxShadow: [
          BoxShadow(
            color: shadowColor,
            blurRadius: 4,
            offset: const Offset(0, 2),
          ),
        ],
      ),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          if (message.isStreaming)
            _StreamingContent(
              content: message.content,
              textColor: textColor,
              cursorColor:
                  chatTheme?.streamingCursorColor ?? theme.colorScheme.primary,
            )
          else if (isUser)
            Text(
              message.content,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: textColor,
              ),
            )
          else
            MarkdownBody(
              data: message.content,
              styleSheet: MarkdownStyleSheet(
                p: theme.textTheme.bodyMedium?.copyWith(color: textColor),
                h1: theme.textTheme.titleLarge?.copyWith(color: textColor),
                h2: theme.textTheme.titleMedium?.copyWith(color: textColor),
                h3: theme.textTheme.titleSmall?.copyWith(color: textColor),
                code: TextStyle(
                  backgroundColor: chatTheme?.codeBlockBackground ??
                      const Color(0xFF1E1E2E),
                  color: const Color(0xFFE0E0E0),
                  fontSize: 13,
                ),
                codeblockDecoration: BoxDecoration(
                  color: chatTheme?.codeBlockBackground ??
                      const Color(0xFF1E1E2E),
                  borderRadius: BorderRadius.circular(8),
                ),
                blockquoteDecoration: BoxDecoration(
                  border: Border(
                    left: BorderSide(
                      color: theme.colorScheme.primary,
                      width: 3,
                    ),
                  ),
                ),
                listBullet: TextStyle(color: textColor),
              ),
              onTapLink: (text, href, title) {
                if (href != null) {
                  launchUrl(Uri.parse(href),
                      mode: LaunchMode.externalApplication);
                }
              },
            ),
          if (!message.isStreaming && message.status != MessageStatus.error)
            Align(
              alignment: Alignment.bottomRight,
              child: InkWell(
                onTap: onCopy,
                borderRadius: BorderRadius.circular(4),
                child: Padding(
                  padding: const EdgeInsets.only(top: 4),
                  child: Icon(
                    Icons.content_copy,
                    size: 14,
                    color: textColor.withValues(alpha: 0.4),
                  ),
                ),
              ),
            ),
        ],
      ),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Streaming Content with Cursor
// ─────────────────────────────────────────────────────────────────────

class _StreamingContent extends StatefulWidget {
  const _StreamingContent({
    required this.content,
    required this.textColor,
    required this.cursorColor,
  });

  final String content;
  final Color textColor;
  final Color cursorColor;

  @override
  State<_StreamingContent> createState() => _StreamingContentState();
}

class _StreamingContentState extends State<_StreamingContent>
    with SingleTickerProviderStateMixin {
  late final AnimationController _cursorController;

  @override
  void initState() {
    super.initState();
    _cursorController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat(reverse: true);
  }

  @override
  void dispose() {
    _cursorController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);

    return Row(
      mainAxisSize: MainAxisSize.min,
      crossAxisAlignment: CrossAxisAlignment.end,
      children: [
        Flexible(
          child: MarkdownBody(
            data: widget.content,
            styleSheet: MarkdownStyleSheet(
              p: theme.textTheme.bodyMedium?.copyWith(
                color: widget.textColor,
              ),
              code: const TextStyle(
                backgroundColor: Color(0xFF1E1E2E),
                color: Color(0xFFE0E0E0),
                fontSize: 13,
              ),
              codeblockDecoration: BoxDecoration(
                color: const Color(0xFF1E1E2E),
                borderRadius: BorderRadius.circular(8),
              ),
              listBullet: TextStyle(color: widget.textColor),
            ),
          ),
        ),
        FadeTransition(
          opacity: _cursorController,
          child: Container(
            width: 8,
            height: 16,
            margin: const EdgeInsets.only(bottom: 2),
            decoration: BoxDecoration(
              color: widget.cursorColor,
              borderRadius: BorderRadius.circular(2),
            ),
          ),
        ),
      ],
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Typing Dots Animation
// ─────────────────────────────────────────────────────────────────────

class _TypingDots extends StatefulWidget {
  const _TypingDots();

  @override
  State<_TypingDots> createState() => _TypingDotsState();
}

class _TypingDotsState extends State<_TypingDots>
    with SingleTickerProviderStateMixin {
  late final AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1200),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final color = theme.colorScheme.onSurface.withValues(alpha: 0.4);

    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return AnimatedBuilder(
          animation: _controller,
          builder: (context, child) {
            final delay = index * 0.15;
            final value =
                ((_controller.value - delay) % 1.0).clamp(0.0, 1.0);
            final scale = 0.5 + 0.5 * (1 - (value * 4 - 2).abs().clamp(0, 1));

            return Padding(
              padding: const EdgeInsets.symmetric(horizontal: 2),
              child: Transform.scale(
                scale: scale,
                child: Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    color: color,
                    shape: BoxShape.circle,
                  ),
                ),
              ),
            );
          },
        );
      }),
    );
  }
}

// ─────────────────────────────────────────────────────────────────────
// Avatar Widget
// ─────────────────────────────────────────────────────────────────────

class _Avatar extends StatelessWidget {
  const _Avatar({
    required this.icon,
    required this.color,
    required this.size,
  });

  final IconData icon;
  final Color color;
  final double size;

  @override
  Widget build(BuildContext context) {
    return Container(
      width: size,
      height: size,
      decoration: BoxDecoration(
        color: color.withValues(alpha: 0.3),
        shape: BoxShape.circle,
      ),
      child: Icon(
        icon,
        size: size * 0.6,
        color: color,
      ),
    );
  }
}

