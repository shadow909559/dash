import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:flutter_markdown/flutter_markdown.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../core/services/websocket_service.dart';
import 'models/chat_message.dart';
import 'providers/chat_provider.dart';
import 'providers/conversation_provider.dart';
import 'widgets/conversation_sidebar.dart';

class ChatPage extends ConsumerStatefulWidget {
  const ChatPage({super.key});

  @override
  ConsumerState<ChatPage> createState() => _ChatPageState();
}

class _ChatPageState extends ConsumerState<ChatPage> {
  final TextEditingController _controller = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  final FocusNode _focusNode = FocusNode();
  bool _isSidebarOpen = true;

  @override
  void initState() {
    super.initState();
    // Listen for active conversation changes to load messages
    ref.listen<String?>(activeConversationIdProvider, (prev, next) {
      if (next != null) {
        ref.read(chatProvider.notifier).loadConversationMessages(next);
      } else {
        ref.read(chatProvider.notifier).clearMessages();
      }
    });
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    _focusNode.dispose();
    super.dispose();
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 100),
          curve: Curves.easeOut,
        );
      }
    });
  }

  void _sendMessage() {
    final message = _controller.text.trim();
    if (message.isEmpty) return;

    final activeId = ref.read(activeConversationIdProvider);
    ref.read(chatProvider.notifier).sendMessage(message,
        conversationId: activeId);
    _controller.clear();
    _focusNode.requestFocus();
    _scrollToBottom();
  }

  void _cancelStreaming() {
    ref.read(chatProvider.notifier).cancelStreaming();
  }

  void _regenerateLastMessage() {
    final chatService = ref.read(chatProvider.notifier);
    final state = ref.read(chatProvider);
    if (state.messages.isEmpty) return;

    String? lastUserContent;
    for (int i = state.messages.length - 1; i >= 0; i--) {
      if (state.messages[i].isUser) {
        lastUserContent = state.messages[i].content;
        break;
      }
    }
    if (lastUserContent != null) {
      final activeId = ref.read(activeConversationIdProvider);
      chatService.sendMessage(lastUserContent, conversationId: activeId);
    }
  }

  void _copyMessage(String content) {
    Clipboard.setData(ClipboardData(text: content));
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(
        content: Text('Copied to clipboard'),
        duration: Duration(seconds: 2),
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    final chatState = ref.watch(chatProvider);
    final socketState = ref.watch(webSocketServiceProvider);
    final activeId = ref.watch(activeConversationIdProvider);
    final theme = Theme.of(context);

    _scrollToBottom();

    return Row(
      children: [
        // Sidebar
        if (_isSidebarOpen)
          const ConversationSidebar(),

        // Main chat area
        Expanded(
          child: Column(
            children: [
              // Top bar with sidebar toggle and conversation title
              _buildTopBar(theme, activeId),
              // Connection bar
              _buildConnectionBar(chatState, socketState.status),
              // Messages
              Expanded(
                child: chatState.messages.isEmpty
                    ? _buildEmptyState(theme)
                    : _buildMessageList(chatState, theme),
              ),
              if (chatState.isTyping) _buildTypingIndicator(theme),
              _buildInputBar(
                  socketState.status, chatState.isStreaming, theme),
            ],
          ),
        ),
      ],
    );
  }

  Widget _buildTopBar(ThemeData theme, String? activeConversationId) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        border: Border(
          bottom: BorderSide(
            color: theme.colorScheme.outlineVariant,
            width: 0.5,
          ),
        ),
      ),
      child: Row(
        children: [
          IconButton(
            icon: Icon(_isSidebarOpen
                ? Icons.menu_open
                : Icons.menu),
            tooltip: 'Toggle sidebar',
            onPressed: () => setState(() => _isSidebarOpen = !_isSidebarOpen),
          ),
          if (activeConversationId != null)
            Expanded(
              child: Consumer(
                builder: (context, ref, child) {
                  final state = ref.watch(conversationListProvider);
                  final conversation = state.conversations
                      .where((c) => c.id == activeConversationId)
                      .firstOrNull;
                  return Text(
                    conversation?.displayTitle ?? 'Chat',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                    overflow: TextOverflow.ellipsis,
                  );
                },
              ),
            )
          else
            Expanded(
              child: Text(
                'New Chat',
                style: theme.textTheme.titleSmall?.copyWith(
                  fontWeight: FontWeight.w600,
                ),
              ),
            ),
          if (activeConversationId != null)
            IconButton(
              icon: const Icon(Icons.new_label_outlined, size: 20),
              tooltip: 'New chat',
              onPressed: () {
                ref.read(activeConversationIdProvider.notifier).state = null;
                ref.read(chatProvider.notifier).clearMessages();
                ref.read(conversationListProvider.notifier).create();
              },
            ),
        ],
      ),
    );
  }

  Widget _buildConnectionBar(ChatState chatState, WebSocketStatus status) {
    if (status == WebSocketStatus.connected && !chatState.isStreaming) {
      return const SizedBox.shrink();
    }

    if (status == WebSocketStatus.connected && chatState.isStreaming) {
      return Container(
        width: double.infinity,
        height: 2,
        color: Theme.of(context).colorScheme.primary,
        child: LinearProgressIndicator(
          backgroundColor: Colors.transparent,
          color: Theme.of(context).colorScheme.primary.withValues(alpha: 0.5),
        ),
      );
    }

    final theme = Theme.of(context);

    late String text;
    late Color color;
    late IconData icon;

    switch (status) {
      case WebSocketStatus.connecting:
        text = 'Connecting...';
        color = Colors.orange;
        icon = Icons.sync;
        break;
      case WebSocketStatus.disconnected:
        text = 'Disconnected';
        color = Colors.red;
        icon = Icons.cloud_off;
        break;
      case WebSocketStatus.error:
        text = chatState.errorMessage ?? 'Connection error';
        color = Colors.red;
        icon = Icons.error_outline;
        break;
      case WebSocketStatus.connected:
        return const SizedBox.shrink();
    }

    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 6),
      color: color.withValues(alpha: 0.1),
      child: Row(
        children: [
          Icon(icon, size: 16, color: color),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: theme.textTheme.bodySmall?.copyWith(color: color),
              overflow: TextOverflow.ellipsis,
            ),
          ),
          if (status != WebSocketStatus.connecting)
            TextButton.icon(
              onPressed: () => ref.read(chatProvider.notifier).reconnect(),
              icon: const Icon(Icons.refresh, size: 16),
              label: const Text('Retry'),
              style: TextButton.styleFrom(
                foregroundColor: color,
                padding: const EdgeInsets.symmetric(horizontal: 8),
                minimumSize: Size.zero,
                tapTargetSize: MaterialTapTargetSize.shrinkWrap,
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildEmptyState(ThemeData theme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            CircleAvatar(
              radius: 48,
              backgroundColor: theme.colorScheme.primaryContainer,
              child: Icon(
                Icons.smart_toy_outlined,
                size: 48,
                color: theme.colorScheme.onPrimaryContainer,
              ),
            ),
            const SizedBox(height: 24),
            Text(
              'Welcome to Dash AI',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 12),
            Text(
              'Your intelligent assistant is ready.\nAsk me anything!',
              textAlign: TextAlign.center,
              style: theme.textTheme.bodyMedium?.copyWith(
                color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildMessageList(ChatState chatState, ThemeData theme) {
    return ListView.builder(
      controller: _scrollController,
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: chatState.messages.length,
      itemBuilder: (context, index) {
        final message = chatState.messages[index];
        final isLastStreaming =
            index == chatState.messages.length - 1 && message.isStreaming;
        return _MessageBubble(
          message: message,
          isLast: index == chatState.messages.length - 1,
          isLastStreaming: isLastStreaming,
          onCopy: () => _copyMessage(message.content),
          onRegenerate: message.isAssistant && !message.isStreaming
              ? _regenerateLastMessage
              : null,
          onStop: isLastStreaming ? _cancelStreaming : null,
        );
      },
    );
  }

  Widget _buildTypingIndicator(ThemeData theme) {
    return Container(
      width: double.infinity,
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: Row(
        children: [
          CircleAvatar(
            radius: 14,
            backgroundColor: theme.colorScheme.secondaryContainer,
            child: Icon(
              Icons.smart_toy,
              size: 16,
              color: theme.colorScheme.onSecondaryContainer,
            ),
          ),
          const SizedBox(width: 8),
          const _AnimatedDots(),
          const SizedBox(width: 8),
          Text(
            'Assistant is thinking...',
            style: theme.textTheme.bodySmall?.copyWith(
              color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
              fontStyle: FontStyle.italic,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInputBar(
      WebSocketStatus status, bool isStreaming, ThemeData theme) {
    final canSend = status == WebSocketStatus.connected && !isStreaming;

    return Container(
      decoration: BoxDecoration(
        color: theme.colorScheme.surface,
        boxShadow: [
          BoxShadow(
            color: Colors.black.withValues(alpha: 0.05),
            blurRadius: 4,
            offset: const Offset(0, -1),
          ),
        ],
      ),
      padding: EdgeInsets.only(
        left: 12,
        right: 8,
        top: 8,
        bottom: MediaQuery.of(context).padding.bottom + 8,
      ),
      child: SafeArea(
        top: false,
        child: Row(
          crossAxisAlignment: CrossAxisAlignment.end,
          children: [
            if (isStreaming)
              IconButton(
                icon: const Icon(Icons.stop_circle_outlined),
                color: Colors.red,
                tooltip: 'Stop generating',
                onPressed: _cancelStreaming,
              ),
            Expanded(
              child: TextField(
                controller: _controller,
                focusNode: _focusNode,
                enabled: canSend,
                maxLines: 4,
                minLines: 1,
                textInputAction: TextInputAction.send,
                onSubmitted: canSend ? (_) => _sendMessage() : null,
                decoration: InputDecoration(
                  hintText: canSend
                      ? 'Type a message...'
                      : isStreaming
                          ? 'Waiting for response...'
                          : 'Connecting...',
                  filled: true,
                  fillColor: theme.colorScheme.surfaceContainerHighest,
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(24),
                    borderSide: BorderSide.none,
                  ),
                  contentPadding: const EdgeInsets.symmetric(
                    horizontal: 16,
                    vertical: 12,
                  ),
                ),
              ),
            ),
            const SizedBox(width: 8),
            AnimatedContainer(
              duration: const Duration(milliseconds: 200),
              child: IconButton.filled(
                tooltip: 'Send',
                onPressed: canSend ? _sendMessage : null,
                icon: const Icon(Icons.send),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

// ──────────────────────────────────────────────────
// Sub-widgets (unchanged from original)
// ──────────────────────────────────────────────────

class _AnimatedDots extends StatefulWidget {
  const _AnimatedDots();

  @override
  State<_AnimatedDots> createState() => _AnimatedDotsState();
}

class _AnimatedDotsState extends State<_AnimatedDots>
    with SingleTickerProviderStateMixin {
  late AnimationController _controller;

  @override
  void initState() {
    super.initState();
    _controller = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 600),
    )..repeat();
  }

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (index) {
        return Padding(
          padding: const EdgeInsets.symmetric(horizontal: 2),
          child: AnimatedBuilder(
            animation: _controller,
            builder: (context, child) {
              final delay = index * 0.2;
              final t = (_controller.value - delay).clamp(0.0, 1.0);
              final opacity =
                  0.3 + (0.7 * (1 - (t * 4 - 2).abs()).clamp(0.0, 1.0));
              return Container(
                width: 6,
                height: 6,
                decoration: BoxDecoration(
                  color: Theme.of(context)
                      .colorScheme
                      .onSurface
                      .withValues(alpha: opacity),
                  shape: BoxShape.circle,
                ),
              );
            },
          ),
        );
      }),
    );
  }
}

class _MessageBubble extends StatelessWidget {
  const _MessageBubble({
    required this.message,
    this.isLast = false,
    this.isLastStreaming = false,
    this.onCopy,
    this.onRegenerate,
    this.onStop,
  });

  final ChatMessage message;
  final bool isLast;
  final bool isLastStreaming;
  final VoidCallback? onCopy;
  final VoidCallback? onRegenerate;
  final VoidCallback? onStop;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final isUser = message.isUser;
    final isStreaming = message.isStreaming;
    final isError = message.status == MessageStatus.error;

    final alignment =
        isUser ? CrossAxisAlignment.end : CrossAxisAlignment.start;

    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 4),
      child: Column(
        crossAxisAlignment: alignment,
        children: [
          // Header with avatar
          Padding(
            padding: const EdgeInsets.only(left: 4, right: 4, bottom: 4),
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                if (!isUser)
                  CircleAvatar(
                    radius: 14,
                    backgroundColor: theme.colorScheme.secondaryContainer,
                    child: Icon(
                      Icons.smart_toy,
                      size: 16,
                      color: theme.colorScheme.onSecondaryContainer,
                    ),
                  ),
                if (!isUser) const SizedBox(width: 8),
                Text(
                  isUser ? 'You' : 'Dash AI',
                  style: theme.textTheme.labelMedium?.copyWith(
                    color: theme.colorScheme.onSurface.withValues(alpha: 0.6),
                    fontWeight: FontWeight.w600,
                  ),
                ),
                if (isUser) const SizedBox(width: 8),
                if (isUser)
                  CircleAvatar(
                    radius: 14,
                    backgroundColor: theme.colorScheme.primaryContainer,
                    child: Icon(
                      Icons.person,
                      size: 16,
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  ),
              ],
            ),
          ),
          // Bubble content
          Container(
            constraints: BoxConstraints(
              maxWidth: MediaQuery.of(context).size.width * 0.82,
            ),
            padding: const EdgeInsets.symmetric(horizontal: 14, vertical: 10),
            decoration: BoxDecoration(
              color: isError
                  ? theme.colorScheme.errorContainer
                  : isUser
                      ? theme.colorScheme.primaryContainer
                      : theme.colorScheme.surfaceContainerHighest,
              borderRadius: BorderRadius.only(
                topLeft: const Radius.circular(18),
                topRight: const Radius.circular(18),
                bottomLeft: Radius.circular(isUser ? 18 : 4),
                bottomRight: Radius.circular(isUser ? 4 : 18),
              ),
              border: isError
                  ? Border.all(
                      color: theme.colorScheme.error.withValues(alpha: 0.5))
                  : null,
            ),
            child: Column(
              crossAxisAlignment: isUser
                  ? CrossAxisAlignment.end
                  : CrossAxisAlignment.start,
              children: [
                if (isUser)
                  Text(
                    message.content,
                    style: theme.textTheme.bodyMedium?.copyWith(
                      color: theme.colorScheme.onPrimaryContainer,
                    ),
                  )
                else
                  _buildMarkdownContent(context, message.content, isStreaming),
                const SizedBox(height: 6),
                Row(
                  mainAxisSize: MainAxisSize.min,
                  children: [
                    if (isError)
                      Padding(
                        padding: const EdgeInsets.only(right: 6),
                        child: Icon(
                          Icons.error_outline,
                          size: 12,
                          color: theme.colorScheme.error,
                        ),
                      ),
                    Text(
                      _formatTime(message.timestamp),
                      style: theme.textTheme.labelSmall?.copyWith(
                        color: isUser
                            ? theme.colorScheme.onPrimaryContainer
                                .withValues(alpha: 0.6)
                            : theme.colorScheme.onSurface
                                .withValues(alpha: 0.5),
                        fontSize: 10,
                      ),
                    ),
                    if (isUser && message.status == MessageStatus.sending)
                      Padding(
                        padding: const EdgeInsets.only(left: 4),
                        child: SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.5,
                            color: theme.colorScheme.onPrimaryContainer
                                .withValues(alpha: 0.5),
                          ),
                        ),
                      ),
                    if (isStreaming)
                      Padding(
                        padding: const EdgeInsets.only(left: 6),
                        child: SizedBox(
                          width: 12,
                          height: 12,
                          child: CircularProgressIndicator(
                            strokeWidth: 1.5,
                            color: theme.colorScheme.onSurface
                                .withValues(alpha: 0.4),
                          ),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),
          if (!isUser &&
              !isStreaming &&
              message.status == MessageStatus.complete)
            Padding(
              padding: const EdgeInsets.only(left: 8, top: 4),
              child: Row(
                mainAxisSize: MainAxisSize.min,
                children: [
                  _ActionButton(
                    icon: Icons.copy_outlined,
                    tooltip: 'Copy',
                    onPressed: onCopy,
                  ),
                  const SizedBox(width: 4),
                  _ActionButton(
                    icon: Icons.refresh,
                    tooltip: 'Regenerate',
                    onPressed: onRegenerate,
                  ),
                ],
              ),
            ),
          if (!isUser && isLastStreaming)
            Padding(
              padding: const EdgeInsets.only(left: 8, top: 4),
              child: _ActionButton(
                icon: Icons.stop_circle_outlined,
                tooltip: 'Stop generating',
                color: Colors.red,
                onPressed: onStop,
              ),
            ),
        ],
      ),
    );
  }

  Widget _buildMarkdownContent(
      BuildContext context, String content, bool isStreaming) {
    final theme = Theme.of(context);

    if (isStreaming) {
      return Text(
        content,
        style: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurface,
          height: 1.5,
        ),
      );
    }

    return MarkdownBody(
      data: content,
      styleSheet: MarkdownStyleSheet(
        p: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.onSurface,
          height: 1.5,
        ),
        h1: theme.textTheme.titleLarge?.copyWith(
          fontWeight: FontWeight.bold,
          color: theme.colorScheme.onSurface,
        ),
        h2: theme.textTheme.titleMedium?.copyWith(
          fontWeight: FontWeight.bold,
          color: theme.colorScheme.onSurface,
        ),
        h3: theme.textTheme.titleSmall?.copyWith(
          fontWeight: FontWeight.bold,
          color: theme.colorScheme.onSurface,
        ),
        code: TextStyle(
          backgroundColor: theme.colorScheme.surfaceContainerHighest,
          fontFamily: 'monospace',
          fontSize: 12,
          color: theme.colorScheme.onSurface,
        ),
        codeblockDecoration: BoxDecoration(
          color: theme.colorScheme.surfaceContainerHighest,
          borderRadius: BorderRadius.circular(8),
          border: Border.all(
            color: theme.colorScheme.outlineVariant,
          ),
        ),
        blockquoteDecoration: BoxDecoration(
          border: Border(
            left: BorderSide(
              color: theme.colorScheme.primary,
              width: 3,
            ),
          ),
          color: theme.colorScheme.surfaceContainerHighest
              .withValues(alpha: 0.3),
        ),
        blockquotePadding:
            const EdgeInsets.only(left: 12, top: 4, bottom: 4),
        listBullet: TextStyle(
          color: theme.colorScheme.primary,
        ),
        horizontalRuleDecoration: BoxDecoration(
          border: Border(
            top: BorderSide(
              color: theme.colorScheme.outlineVariant,
            ),
          ),
        ),
        a: TextStyle(
          color: theme.colorScheme.primary,
          decoration: TextDecoration.underline,
        ),
        strong: theme.textTheme.bodyMedium?.copyWith(
          fontWeight: FontWeight.bold,
          color: theme.colorScheme.onSurface,
        ),
        em: theme.textTheme.bodyMedium?.copyWith(
          fontStyle: FontStyle.italic,
          color: theme.colorScheme.onSurface,
        ),
        del: theme.textTheme.bodyMedium?.copyWith(
          decoration: TextDecoration.lineThrough,
          color: theme.colorScheme.onSurface,
        ),
        checkbox: theme.textTheme.bodyMedium?.copyWith(
          color: theme.colorScheme.primary,
        ),
      ),
      onTapLink: (text, href, title) {
        if (href != null) {
          launchUrl(Uri.parse(href));
        }
      },
    );
  }

  String _formatTime(DateTime dt) {
    final hour = dt.hour.toString().padLeft(2, '0');
    final minute = dt.minute.toString().padLeft(2, '0');
    return '$hour:$minute';
  }
}

class _ActionButton extends StatelessWidget {
  const _ActionButton({
    required this.icon,
    required this.tooltip,
    this.onPressed,
    this.color,
  });

  final IconData icon;
  final String tooltip;
  final VoidCallback? onPressed;
  final Color? color;

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    return SizedBox(
      width: 28,
      height: 28,
      child: IconButton(
        icon: Icon(icon, size: 14),
        tooltip: tooltip,
        onPressed: onPressed,
        style: IconButton.styleFrom(
          foregroundColor:
              color ?? theme.colorScheme.onSurface.withValues(alpha: 0.5),
          padding: EdgeInsets.zero,
          visualDensity: VisualDensity.compact,
          minimumSize: Size.zero,
          tapTargetSize: MaterialTapTargetSize.shrinkWrap,
        ),
      ),
    );
  }
}