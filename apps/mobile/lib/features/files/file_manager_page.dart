import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:file_picker/file_picker.dart';

import '../../core/services/websocket_service.dart';
import 'dart:convert';

enum FileViewMode { list, grid }

class FileManagerPage extends ConsumerStatefulWidget {
  const FileManagerPage({super.key});

  @override
  ConsumerState<FileManagerPage> createState() => _FileManagerPageState();
}

class _FileManagerPageState extends ConsumerState<FileManagerPage> {
  FileViewMode _viewMode = FileViewMode.list;
  final List<Map<String, dynamic>> _recentFiles = [];

  @override
  Widget build(BuildContext context) {
    final socketState = ref.watch(webSocketServiceProvider);
    final colorScheme = Theme.of(context).colorScheme;
    final theme = Theme.of(context);
    final isConnected = socketState.status == WebSocketStatus.connected;

    return Scaffold(
      appBar: AppBar(
        title: const Text('Files'),
        actions: [
          IconButton(
            icon: const Icon(Icons.upload_file),
            onPressed: _pickFile,
            tooltip: 'Upload',
          ),
          IconButton(
            icon: Icon(_viewMode == FileViewMode.list
                ? Icons.grid_view
                : Icons.list),
            onPressed: () {
              setState(
                  () => _viewMode = _viewMode == FileViewMode.list ? FileViewMode.grid : FileViewMode.list);
            },
            tooltip: 'Toggle view',
          ),
        ],
      ),
      body: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          _ConnectionCard(isConnected: isConnected),
          const SizedBox(height: 16),
          _buildSectionHeader('Recent Files', theme, colorScheme),
          const SizedBox(height: 8),
          if (_recentFiles.isEmpty)
            Card(
              child: Padding(
                padding: const EdgeInsets.all(24),
                child: Center(
                  child: Column(
                    children: [
                      Icon(Icons.folder_off_outlined,
                          size: 32,
                          color: colorScheme.onSurface.withValues(alpha: 0.3)),
                      const SizedBox(height: 8),
                      Text(
                        'No recent files',
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
            _viewMode == FileViewMode.list
                ? Card(
                    child: Column(
                      children: _recentFiles.map((file) {
                        return _FileTile(file: file, theme: theme, colorScheme: colorScheme);
                      }).toList(),
                    ),
                  )
                : GridView.count(
                    shrinkWrap: true,
                    physics: const NeverScrollableScrollPhysics(),
                    crossAxisCount: 2,
                    mainAxisSpacing: 8,
                    crossAxisSpacing: 8,
                    childAspectRatio: 1.2,
                    children: _recentFiles.map((file) {
                      return _FileGridCard(file: file, theme: theme, colorScheme: colorScheme);
                    }).toList(),
                  ),
          const SizedBox(height: 16),
          _buildSectionHeader('Local Browser', theme, colorScheme),
          const SizedBox(height: 8),
          Card(
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                children: [
                  Row(
                    children: [
                      Expanded(
                        child: FilledButton.tonalIcon(
                          onPressed: isConnected ? _requestFileList : null,
                          icon: const Icon(Icons.folder_open, size: 18),
                          label: const Text('Browse via WebSocket'),
                        ),
                      ),
                      const SizedBox(width: 8),
                      Expanded(
                        child: OutlinedButton.icon(
                          onPressed: _pickFile,
                          icon: const Icon(Icons.add, size: 18),
                          label: const Text('Upload File'),
                        ),
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
                      'File browser output will appear here via WebSocket',
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
          const SizedBox(height: 24),
        ],
      ),
    );
  }

  Future<void> _pickFile() async {
    final result = await FilePicker.platform.pickFiles();
    if (result == null) return;

    final file = result.files.single;
    final size = _formatSize(file.size);
    setState(() {
      _recentFiles.insert(0, {
        'name': file.name,
        'path': file.path ?? '',
        'size': size,
        'extension': file.extension ?? '',
        'type': file.size,
      });
    });

    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      SnackBar(content: Text('Selected: ${file.name}')),
    );
  }

  Future<void> _requestFileList() async {
    final socket = ref.read(webSocketServiceProvider.notifier);
    socket.send(jsonEncode({'type': 'files.list', 'path': '.'}));
  }

  String _formatSize(int bytes) {
    if (bytes >= 1024 * 1024) return '${(bytes / (1024 * 1024)).toStringAsFixed(1)} MB';
    if (bytes >= 1024) return '${(bytes / 1024).toStringAsFixed(1)} KB';
    return '$bytes B';
  }
}

class _ConnectionCard extends StatelessWidget {
  const _ConnectionCard({required this.isConnected});

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
              isConnected ? Icons.storage : Icons.storage_outlined,
              color: isConnected ? colorScheme.primary : colorScheme.error,
            ),
            const SizedBox(width: 8),
            Expanded(
              child: Text(
                isConnected
                    ? 'File services ready via WebSocket'
                    : 'File services require WebSocket connection',
                style: theme.textTheme.bodyMedium,
              ),
            ),
          ],
        ),
      ),
    );
  }
}

class _FileTile extends StatelessWidget {
  const _FileTile({required this.file, required this.theme, required this.colorScheme});

  final Map<String, dynamic> file;
  final ThemeData theme;
  final ColorScheme colorScheme;

  IconData get _icon {
    final ext = file['extension']?.toString().toLowerCase();
    if (ext == 'pdf') return Icons.picture_as_pdf;
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(ext)) return Icons.image;
    if (['mp3', 'wav', 'ogg', 'flac'].contains(ext)) return Icons.audiotrack;
    if (['mp4', 'mov', 'avi'].contains(ext)) return Icons.videocam;
    if (['zip', 'tar', 'gz', '7z'].contains(ext)) return Icons.folder_zip;
    if (['txt', 'md', 'json', 'yaml', 'yml'].contains(ext)) return Icons.description;
    return Icons.insert_drive_file;
  }

  @override
  Widget build(BuildContext context) {
    return InkWell(
      onTap: () {},
      child: ListTile(
        leading: Icon(_icon, color: colorScheme.primary),
        title: Text(file['name']?.toString() ?? 'Unknown file'),
        subtitle: Text('${file['size'] ?? ''}  ${file['path'] ?? ''}'),
        trailing: Icon(Icons.chevron_right, size: 18, color: colorScheme.onSurface.withValues(alpha: 0.4)),
      ),
    );
  }
}

class _FileGridCard extends StatelessWidget {
  const _FileGridCard({required this.file, required this.theme, required this.colorScheme});

  final Map<String, dynamic> file;
  final ThemeData theme;
  final ColorScheme colorScheme;

  @override
  Widget build(BuildContext context) {
    final ext = file['extension']?.toString().toLowerCase();
    IconData icon;
    if (ext == 'pdf') {
      icon = Icons.picture_as_pdf;
    } else if (['jpg', 'jpeg', 'png', 'gif', 'webp'].contains(ext)) {
      icon = Icons.image;
    } else if (['mp3', 'wav', 'ogg', 'flac'].contains(ext)) {
      icon = Icons.audiotrack;
    } else if (['mp4', 'mov', 'avi'].contains(ext)) {
      icon = Icons.videocam;
    } else if (['zip', 'tar', 'gz', '7z'].contains(ext)) {
      icon = Icons.folder_zip;
    } else if (['txt', 'md', 'json', 'yaml', 'yml'].contains(ext)) {
      icon = Icons.description;
    } else {
      icon = Icons.insert_drive_file;
    }

    return Card(
      child: InkWell(
        onTap: () {},
        child: Padding(
          padding: const EdgeInsets.all(12),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.center,
            children: [
              Icon(icon, size: 32, color: colorScheme.primary),
              const SizedBox(height: 8),
              Text(
                file['name']?.toString() ?? 'Unknown',
                maxLines: 1,
                overflow: TextOverflow.ellipsis,
                style: theme.textTheme.bodySmall,
              ),
              const SizedBox(height: 2),
              Text(
                file['size']?.toString() ?? '',
                style: theme.textTheme.bodySmall?.copyWith(
                  color: colorScheme.onSurface.withValues(alpha: 0.5),
                ),
              ),
            ],
          ),
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
