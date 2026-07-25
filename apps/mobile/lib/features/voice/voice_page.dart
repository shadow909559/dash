import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/websocket_service.dart';
import 'dart:convert';

class VoicePage extends ConsumerStatefulWidget {
  const VoicePage({super.key});

  @override
  ConsumerState<VoicePage> createState() => _VoicePageState();
}

class _VoicePageState extends ConsumerState<VoicePage> {
  bool _isListening = false;
  final List<String> _transcript = [];
  final TextEditingController _ttsController = TextEditingController();
  double _volume = 0.5;

  @override
  Widget build(BuildContext context) {
    final socketState = ref.watch(webSocketServiceProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final isConnected = socketState.status == WebSocketStatus.connected;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Voice'),
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _ConnectionStatusCard(isConnected: isConnected),
          const SizedBox(height: 24),

          Center(
            child: Column(
              children: [
                Text(
                  _isListening ? 'Listening...' : 'Push to talk',
                  style: theme.textTheme.titleLarge?.copyWith(
                    fontWeight: FontWeight.w600,
                    color: _isListening ? colorScheme.primary : null,
                  ),
                ),
                const SizedBox(height: 24),
                GestureDetector(
                  onTapDown: (_) {
                    if (!isConnected) return;
                    setState(() => _isListening = true);
                    _sendVoiceStart();
                  },
                  onTapUp: (_) {
                    setState(() => _isListening = false);
                    _sendVoiceStop();
                  },
                  onTapCancel: () {
                    setState(() => _isListening = false);
                    _sendVoiceStop();
                  },
                  child: AnimatedContainer(
                    duration: const Duration(milliseconds: 200),
                    width: 180,
                    height: 180,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: _isListening
                          ? colorScheme.primaryContainer
                          : colorScheme.surfaceContainerHighest,
                      boxShadow: _isListening
                          ? [
                              BoxShadow(
                                color: colorScheme.primary.withValues(alpha: 0.3),
                                blurRadius: 24,
                                spreadRadius: 8,
                              )
                            ]
                          : null,
                    ),
                    child: Icon(
                      Icons.mic,
                      size: 80,
                      color: _isListening
                          ? colorScheme.primary
                          : colorScheme.onSurface.withValues(alpha: 0.4),
                    ),
                  ),
                ),
                const SizedBox(height: 24),
                if (_isListening)
                  Row(
                    mainAxisAlignment: MainAxisAlignment.center,
                    children: List.generate(5, (index) {
                      return AnimatedContainer(
                        duration: const Duration(milliseconds: 300),
                        margin: const EdgeInsets.symmetric(horizontal: 3),
                        width: 6,
                        height: (index + 1) * 8.0 + 10,
                        decoration: BoxDecoration(
                          color: colorScheme.primary,
                          borderRadius: BorderRadius.circular(3),
                        ),
                      );
                    }),
                  ),
              ],
            ),
          ),
          const SizedBox(height: 32),

          _buildSectionHeader('Transcript', theme, colorScheme),
          Card(
            child: Container(
              constraints: const BoxConstraints(maxHeight: 200),
              padding: const EdgeInsets.all(12),
              child: _transcript.isEmpty
                  ? Text(
                      'Transcript will appear here',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.5),
                      ),
                    )
                  : ListView.builder(
                      reverse: true,
                      itemCount: _transcript.length,
                      itemBuilder: (context, index) {
                        return Padding(
                          padding: const EdgeInsets.symmetric(vertical: 2),
                          child: Text(_transcript[index]),
                        );
                      },
                    ),
            ),
          ),
          const SizedBox(height: 24),

          _buildSectionHeader('Text to Speech', theme, colorScheme),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: TextField(
                          controller: _ttsController,
                          decoration: const InputDecoration(
                            labelText: 'Text to speak',
                            hintText: 'Enter text...',
                          ),
                        ),
                      ),
                      const SizedBox(width: 8),
                      FilledButton.icon(
                        onPressed: isConnected
                            ? () {
                                final text = _ttsController.text.trim();
                                if (text.isEmpty) return;
                                _sendTts(text);
                              }
                            : null,
                        icon: const Icon(Icons.volume_up, size: 18),
                        label: const Text('Speak'),
                      ),
                    ],
                  ),
                  const SizedBox(height: 12),
                  Row(
                    children: [
                      Icon(Icons.volume_down,
                          size: 18, color: colorScheme.onSurface.withValues(alpha: 0.6)),
                      Expanded(
                        child: Slider(
                          value: _volume,
                          onChanged: (v) => setState(() => _volume = v),
                        ),
                      ),
                      Icon(Icons.volume_up,
                          size: 18, color: colorScheme.onSurface.withValues(alpha: 0.6)),
                    ],
                  ),
                ],
              ),
            ),
          ),
          const SizedBox(height: 24),

          _buildSectionHeader('Settings', theme, colorScheme),
          Card(
            child: Column(
              children: [
                SwitchListTile(
                  title: const Text('Voice Activation'),
                  subtitle: const Text('Enable wake word detection'),
                  value: false,
                  onChanged: (v) {
                    if (!isConnected) return;
                    _send({'type': 'voice.wakeword.set', 'enabled': v});
                  },
                ),
                const Divider(height: 1, indent: 16, endIndent: 16),
                SwitchListTile(
                  title: const Text('Noise Cancellation'),
                  subtitle: const Text('Reduce background noise'),
                  value: true,
                  onChanged: (v) {
                    if (!isConnected) return;
                    _send({'type': 'voice.noise.cancel', 'enabled': v});
                  },
                ),
              ],
            ),
          ),
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  void _sendVoiceStart() {
    _send({'type': 'voice.stt.start', 'language': 'en'});
  }

  void _sendVoiceStop() {
    _send({'type': 'voice.stt.stop'});
  }

  void _sendTts(String text) {
    _send({'type': 'voice.tts', 'text': text, 'volume': _volume});
  }

  void _send(Map<String, dynamic> payload) {
    try {
      ref.read(webSocketServiceProvider.notifier).send(jsonEncode(payload));
    } catch (e) {
      // ignore
    }
  }
}

class _ConnectionStatusCard extends StatelessWidget {
  const _ConnectionStatusCard({required this.isConnected});

  final bool isConnected;

  @override
  Widget build(BuildContext context) {
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);

    return Card(
      color: isConnected
          ? colorScheme.primaryContainer.withValues(alpha: 0.3)
          : colorScheme.errorContainer.withValues(alpha: 0.2),
      child: Padding(
        padding: const EdgeInsets.all(12),
        child: Row(
          children: [
            Container(
              width: 10,
              height: 10,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                color: isConnected ? Colors.green : Colors.red,
              ),
            ),
            const SizedBox(width: 12),
            Icon(
              isConnected ? Icons.mic : Icons.mic_off,
              color: isConnected ? colorScheme.primary : colorScheme.error,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                isConnected
                    ? 'Voice services ready via WebSocket'
                    : 'Voice requires WebSocket connection',
                style: theme.textTheme.bodyMedium,
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
