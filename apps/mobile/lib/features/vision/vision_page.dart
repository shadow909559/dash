import 'dart:io';

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:image_picker/image_picker.dart';

import '../../core/services/websocket_service.dart';
import 'dart:convert';

enum VisionTab { camera, gallery, results }

class VisionPage extends ConsumerStatefulWidget {
  const VisionPage({super.key});

  @override
  ConsumerState<VisionPage> createState() => _VisionPageState();
}

class _VisionPageState extends ConsumerState<VisionPage> {
  final ImagePicker _picker = ImagePicker();
  File? _selectedImage;
  final List<Map<String, dynamic>> _results = [];
  bool _isAnalyzing = false;

  @override
  Widget build(BuildContext context) {
    final socketState = ref.watch(webSocketServiceProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final isConnected = socketState.status == WebSocketStatus.connected;

    return DefaultTabController(
      length: 3,
      child: Scaffold(
        appBar: AppBar(
          title: const Text('Vision'),
          bottom: const TabBar(
            tabs: [
              Tab(text: 'Camera'),
              Tab(text: 'Gallery'),
              Tab(text: 'Results'),
            ],
          ),
        ),
        body: TabBarView(
          physics: const NeverScrollableScrollPhysics(),
          children: [
            _buildCameraTab(theme, colorScheme, isConnected),
            _buildGalleryTab(theme, colorScheme, isConnected),
            _buildResultsTab(theme, colorScheme),
          ],
        ),
        floatingActionButton: _isAnalyzing
            ? null
            : _selectedImage != null
                ? FloatingActionButton.extended(
                    onPressed: isConnected ? _analyzeImage : null,
                    icon: const Icon(Icons.auto_awesome),
                    label: const Text('Analyze'),
                  )
                : null,
      ),
    );
  }

  Widget _buildCameraTab(
      ThemeData theme, ColorScheme colorScheme, bool isConnected) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _ConnectionStatusCard(isConnected: isConnected),
        const SizedBox(height: 24),
        _buildSectionHeader('Camera Capture', theme, colorScheme),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                if (_selectedImage != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.file(
                      _selectedImage!,
                      width: double.infinity,
                      height: 240,
                      fit: BoxFit.cover,
                    ),
                  )
                else
                  Container(
                    height: 180,
                    decoration: BoxDecoration(
                      color: colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.camera_alt_outlined,
                              size: 48,
                              color: colorScheme.onSurface.withValues(alpha: 0.3)),
                          const SizedBox(height: 8),
                          Text(
                            'No image selected',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _isAnalyzing
                            ? null
                            : () => _pickImage(ImageSource.camera),
                        icon: const Icon(Icons.camera_alt, size: 18),
                        label: const Text('Take Photo'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _selectedImage != null
                            ? () => setState(() => _selectedImage = null)
                            : null,
                        icon: const Icon(Icons.clear, size: 18),
                        label: const Text('Clear'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildGalleryTab(
      ThemeData theme, ColorScheme colorScheme, bool isConnected) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _ConnectionStatusCard(isConnected: isConnected),
        const SizedBox(height: 24),
        _buildSectionHeader('Gallery Picker', theme, colorScheme),
        Card(
          child: Padding(
            padding: const EdgeInsets.all(16),
            child: Column(
              children: [
                if (_selectedImage != null)
                  ClipRRect(
                    borderRadius: BorderRadius.circular(12),
                    child: Image.file(
                      _selectedImage!,
                      width: double.infinity,
                      height: 240,
                      fit: BoxFit.cover,
                    ),
                  )
                else
                  Container(
                    height: 180,
                    decoration: BoxDecoration(
                      color: colorScheme.surfaceContainerHighest,
                      borderRadius: BorderRadius.circular(12),
                    ),
                    child: Center(
                      child: Column(
                        mainAxisAlignment: MainAxisAlignment.center,
                        children: [
                          Icon(Icons.photo_library_outlined,
                              size: 48,
                              color: colorScheme.onSurface.withValues(alpha: 0.3)),
                          const SizedBox(height: 8),
                          Text(
                            'No image selected',
                            style: theme.textTheme.bodyMedium?.copyWith(
                              color: colorScheme.onSurface.withValues(alpha: 0.5),
                            ),
                          ),
                        ],
                      ),
                    ),
                  ),
                const SizedBox(height: 12),
                Row(
                  children: [
                    Expanded(
                      child: FilledButton.icon(
                        onPressed: _isAnalyzing
                            ? null
                            : () => _pickImage(ImageSource.gallery),
                        icon: const Icon(Icons.photo_library, size: 18),
                        label: const Text('Pick Image'),
                      ),
                    ),
                    const SizedBox(width: 8),
                    Expanded(
                      child: OutlinedButton.icon(
                        onPressed: _selectedImage != null
                            ? () => setState(() => _selectedImage = null)
                            : null,
                        icon: const Icon(Icons.clear, size: 18),
                        label: const Text('Clear'),
                      ),
                    ),
                  ],
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 24),
      ],
    );
  }

  Widget _buildResultsTab(ThemeData theme, ColorScheme colorScheme) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        _buildSectionHeader('Analysis Results', theme, colorScheme),
        if (_results.isEmpty)
          Card(
            child: Padding(
              padding: const EdgeInsets.all(24),
              child: Center(
                child: Column(
                  children: [
                    Icon(Icons.analytics_outlined,
                        size: 48,
                        color: colorScheme.onSurface.withValues(alpha: 0.3)),
                    const SizedBox(height: 8),
                    Text(
                      'No analysis yet',
                      style: theme.textTheme.bodyMedium?.copyWith(
                        color: colorScheme.onSurface.withValues(alpha: 0.5),
                      ),
                    ),
                  ],
                ),
              ),
            ),
          )
        else
          ...List.generate(_results.length, (index) {
            final result = _results[index];
            return Card(
              margin: const EdgeInsets.only(bottom: 8),
              child: Padding(
                padding: const EdgeInsets.all(12),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      result['label'] as String? ?? 'Result ${index + 1}',
                      style: theme.textTheme.titleSmall?.copyWith(
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                    const SizedBox(height: 4),
                    if (result['ocr'] != null)
                      Text('OCR: ${result['ocr']}'),
                    if (result['analysis'] != null)
                      Text('Analysis: ${result['analysis']}'),
                    if (result['confidence'] != null)
                      Text(
                        'Confidence: ${result['confidence']}',
                        style: theme.textTheme.bodySmall?.copyWith(
                          color: colorScheme.onSurface.withValues(alpha: 0.6),
                        ),
                      ),
                  ],
                ),
              ),
            );
          }),
      ],
    );
  }

  Future<void> _pickImage(ImageSource source) async {
    final picked = await _picker.pickImage(source: source);
    if (picked != null) {
      setState(() => _selectedImage = File(picked.path));
    }
  }

  Future<void> _analyzeImage() async {
    if (_selectedImage == null) return;
    setState(() => _isAnalyzing = true);

    try {
      final socket = ref.read(webSocketServiceProvider.notifier);
      final imageFile = _selectedImage!;
      final bytes = await imageFile.readAsBytes();

      socket.send(jsonEncode({
        'type': 'vision.analyze',
        'filename': imageFile.path.split('/').last,
        'content_type': 'image/jpeg',
        'data': bytes,
      }));

      setState(() {
        _results.add({
          'label': 'Analysis of ${imageFile.path.split('/').last}',
          'ocr': 'Processing...',
          'analysis': 'Awaiting WebSocket response',
          'confidence': 0.0,
        });
      });
    } catch (e) {
      if (mounted) {
        ScaffoldMessenger.of(context).showSnackBar(
          SnackBar(content: Text('Analysis failed: $e')),
        );
      }
    } finally {
      setState(() => _isAnalyzing = false);
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
              isConnected ? Icons.visibility : Icons.visibility_off,
              color: isConnected ? colorScheme.primary : colorScheme.error,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                isConnected
                    ? 'Vision services ready via WebSocket'
                    : 'Vision requires WebSocket connection',
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
