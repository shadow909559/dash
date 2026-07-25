import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/constants.dart';
import '../../core/services/websocket_service.dart';
import 'dart:convert';

class DesktopPage extends ConsumerStatefulWidget {
  const DesktopPage({super.key});

  @override
  ConsumerState<DesktopPage> createState() => _DesktopPageState();
}

class _DesktopPageState extends ConsumerState<DesktopPage> {
  final List<String> _logMessages = [];
  final TextEditingController _clipboardController = TextEditingController();
  final TextEditingController _commandController = TextEditingController();
  bool _isChannelOpen = false;

  @override
  void initState() {
    super.initState();
    _connectWebSocket();
  }

  Future<void> _connectWebSocket() async {
    try {
      final wsService = ref.read(webSocketServiceProvider.notifier);
      await wsService.connect(url: defaultWebSocketUrl);
      if (mounted) {
        setState(() {
          _isChannelOpen = ref.read(webSocketServiceProvider).status == WebSocketStatus.connected;
        });
      }
    } catch (e) {
      _addLog('Connection failed: $e');
    }
  }

  void _addLog(String message) {
    setState(() {
      _logMessages.insert(0, '${_timestamp()}: $message');
      if (_logMessages.length > 100) _logMessages.removeLast();
    });
  }

  String _timestamp() {
    final now = DateTime.now();
    return '${now.hour.toString().padLeft(2, '0')}:${now.minute.toString().padLeft(2, '0')}:${now.second.toString().padLeft(2, '0')}';
  }

  void _sendClipboard() {
    final text = _clipboardController.text.trim();
    if (text.isEmpty || !_isChannelOpen) return;
    final payload = {'type': 'desktop.clipboard.set', 'text': text};
    _send(payload);
    _addLog('Clipboard set: ${text.length} chars');
    _clipboardController.clear();
  }

  void _sendCommand() {
    final text = _commandController.text.trim();
    if (text.isEmpty || !_isChannelOpen) return;
    final payload = {'type': 'desktop.command.execute', 'command': text};
    _send(payload);
    _addLog('Command sent: $text');
    _commandController.clear();
  }

  void _send(Map<String, dynamic> payload) {
    try {
      ref.read(webSocketServiceProvider.notifier).send(jsonEncode(payload));
    } catch (e) {
      _addLog('Send failed: $e');
    }
  }

  void _requestScreenshot() {
    _send({'type': 'desktop.screenshot.request'});
    _addLog('Requested screenshot');
  }

  void _requestProcessList() {
    _send({'type': 'desktop.processes.list'});
    _addLog('Requested process list');
  }

  void _requestFileList() {
    _send({'type': 'desktop.files.list', 'path': '.'});
    _addLog('Requested file list');
  }

  @override
  Widget build(BuildContext context) {
    final socketState = ref.watch(webSocketServiceProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Scaffold(
      appBar: AppBar(
        title: const Text('Desktop Control'),
        actions: [
          IconButton(
            icon: Icon(_isChannelOpen ? Icons.link : Icons.link_off),
            onPressed: _isChannelOpen ? null : _connectWebSocket,
            tooltip: _isChannelOpen ? 'Connected' : 'Connect',
          ),
        ],
      ),
      body: RefreshIndicator(
        onRefresh: _connectWebSocket,
        child: ListView(
          padding: const EdgeInsets.all(16),
          children: [
            _ConnectionCard(
              isConnected: _isChannelOpen,
              status: socketState.status.toString().split('.').last,
              errorMessage: socketState.errorMessage,
            ),
            const SizedBox(height: 16),

            _buildSectionHeader('Clipboard', theme, colorScheme),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _clipboardController,
                            decoration: const InputDecoration(
                              labelText: 'Send text to PC clipboard',
                              hintText: 'Paste text here...',
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: _isChannelOpen ? _sendClipboard : null,
                          icon: const Icon(Icons.send, size: 18),
                          label: const Text('Send'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Row(
                      children: [
                        FilledButton.tonalIcon(
                          onPressed: _isChannelOpen
                              ? () {
                                  _send({'type': 'desktop.clipboard.get'});
                                  _addLog('Requested clipboard');
                                }
                              : null,
                          icon: const Icon(Icons.content_paste, size: 18),
                          label: const Text('Read from PC'),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.tonalIcon(
                          onPressed: _isChannelOpen
                              ? _requestScreenshot
                              : null,
                          icon: const Icon(Icons.camera_alt, size: 18),
                          label: const Text('Screenshot'),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            _buildSectionHeader('Processes', theme, colorScheme),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: _isChannelOpen ? _requestProcessList : null,
                      icon: const Icon(Icons.list_alt, size: 18),
                      label: const Text('List Running Processes'),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Process list will appear here via WebSocket',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.5),
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            _buildSectionHeader('Files', theme, colorScheme),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    FilledButton.tonalIcon(
                      onPressed: _isChannelOpen ? _requestFileList : null,
                      icon: const Icon(Icons.folder_open, size: 18),
                      label: const Text('Open File Browser'),
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'File browser will appear here via WebSocket',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.5),
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            _buildSectionHeader('Commands', theme, colorScheme),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: TextField(
                            controller: _commandController,
                            decoration: const InputDecoration(
                              labelText: 'Approved command',
                              hintText: 'type a command...',
                            ),
                          ),
                        ),
                        const SizedBox(width: 8),
                        FilledButton.icon(
                          onPressed: _isChannelOpen ? _sendCommand : null,
                          icon: const Icon(Icons.terminal, size: 18),
                          label: const Text('Run'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Container(
                      padding: const EdgeInsets.all(8),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: Text(
                        'Command output will appear here via WebSocket',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.5),
                        ),
                        textAlign: TextAlign.center,
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),

            _buildSectionHeader('Event Log', theme, colorScheme),
            Card(
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      children: [
                        Expanded(
                          child: Text(
                            'WebSocket events',
                            style: theme.textTheme.titleSmall?.copyWith(
                              fontWeight: FontWeight.w600,
                            ),
                          ),
                        ),
                        TextButton.icon(
                          onPressed: () {
                            setState(() => _logMessages.clear());
                          },
                          icon: const Icon(Icons.clear, size: 16),
                          label: const Text('Clear'),
                        ),
                      ],
                    ),
                    const SizedBox(height: 8),
                    Container(
                      width: double.infinity,
                      constraints: const BoxConstraints(maxHeight: 200),
                      decoration: BoxDecoration(
                        color: colorScheme.surfaceContainerHighest,
                        borderRadius: BorderRadius.circular(8),
                      ),
                      child: _logMessages.isEmpty
                          ? Padding(
                              padding: const EdgeInsets.all(12),
                              child: Text(
                                'No events yet',
                                style: theme.textTheme.bodySmall?.copyWith(
                                  color: colorScheme.onSurface.withValues(alpha: 0.5),
                                ),
                              ),
                            )
                          : ListView.builder(
                              shrinkWrap: true,
                              itemCount: _logMessages.length,
                              itemBuilder: (context, index) {
                                return Padding(
                                  padding: const EdgeInsets.symmetric(
                                      horizontal: 8, vertical: 2),
                                  child: Text(
                                    _logMessages[index],
                                    style: theme.textTheme.bodySmall,
                                  ),
                                );
                              },
                            ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 24),
          ],
        ),
      ),
    );
  }

  @override
  void dispose() {
    _clipboardController.dispose();
    _commandController.dispose();
    super.dispose();
  }
}

class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({
    required this.isConnected,
    required this.status,
    this.errorMessage,
  });

  final bool isConnected;
  final String status;
  final String? errorMessage;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Card(
      color: isConnected
          ? colorScheme.primaryContainer.withValues(alpha: 0.3)
          : colorScheme.errorContainer.withValues(alpha: 0.2),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Row(
          children: [
            Container(
              width: 12,
              height: 12,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isConnected ? Colors.green : Colors.red,
              ),
            ),
            const SizedBox(width: 12),
            Expanded(
              child: Column(
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text(
                    isConnected ? 'Connected' : 'Disconnected',
                    style: theme.textTheme.titleSmall?.copyWith(
                      fontWeight: FontWeight.w600,
                    ),
                  ),
                  Text(
                    'Status: $status',
                    style: theme.textTheme.bodySmall?.copyWith(
                      color: colorScheme.onSurface.withValues(alpha: 0.6),
                    ),
                  ),
                  if (errorMessage != null)
                    Text(
                      errorMessage!,
                      style: theme.textTheme.bodySmall?.copyWith(
                        color: colorScheme.error,
                      ),
                    ),
                ],
              ),
            ),
          ],
        ),
      ),
    );
  }
}

Widget _buildSectionHeader(String title, ThemeData theme, ColorScheme colorScheme) {
  return Padding(
    padding: const EdgeInsets.only(bottom: 6, left: 4),
    child: Text(
      title,
      style: theme.textTheme.labelLarge?.copyWith(
        fontWeight: FontWeight.w600,
        color: colorScheme.onSurface.withValues(alpha: 0.7),
        letterSpacing: 0.5,
      ),
    ),
  );
}
