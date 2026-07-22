import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

/// Project model.
class Project {
  final String id;
  final String name;
  final String description;
  final String type;
  final DateTime createdAt;
  final int fileCount;

  const Project({
    required this.id,
    required this.name,
    this.description = '',
    this.type = 'generic',
    required this.createdAt,
    this.fileCount = 0,
  });

  factory Project.fromJson(Map<String, dynamic> json) {
    return Project(
      id: json['id'] as String? ?? '',
      name: json['name'] as String? ?? 'Untitled',
      description: json['description'] as String? ?? '',
      type: json['type'] as String? ?? 'generic',
      createdAt: DateTime.parse(
        json['created_at'] as String? ?? DateTime.now().toIso8601String(),
      ),
      fileCount: json['file_count'] as int? ?? 0,
    );
  }

  Map<String, dynamic> toJson() => {
        'id': id,
        'name': name,
        'description': description,
        'type': type,
        'created_at': createdAt.toIso8601String(),
        'file_count': fileCount,
      };
}

/// Project manager page.
class ProjectManagerPage extends ConsumerStatefulWidget {
  const ProjectManagerPage({super.key});

  @override
  ConsumerState<ProjectManagerPage> createState() => _ProjectManagerPageState();
}

class _ProjectManagerPageState extends ConsumerState<ProjectManagerPage> {
  final List<Project> _projects = [];

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;

    return Column(
      children: [
        // Header
        Container(
          padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 12),
          child: Row(
            children: [
              Icon(Icons.folder_outlined, color: colorScheme.primary, size: 24),
              const SizedBox(width: 12),
              Text(
                'Projects',
                style: theme.textTheme.titleMedium?.copyWith(
                  fontWeight: FontWeight.bold,
                ),
              ),
              const Spacer(),
              FilledButton.tonalIcon(
                onPressed: () => _showCreateDialog(),
                icon: const Icon(Icons.add, size: 18),
                label: const Text('New'),
              ),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _projects.isEmpty
              ? _buildEmptyState(theme, colorScheme)
              : ListView.builder(
                  padding: const EdgeInsets.all(12),
                  itemCount: _projects.length,
                  itemBuilder: (context, index) => _buildProjectCard(
                    _projects[index],
                    theme,
                  ),
                ),
        ),
      ],
    );
  }

  Widget _buildEmptyState(ThemeData theme, ColorScheme colorScheme) {
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
              child: Icon(Icons.folder_open, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text(
              'No projects yet',
              style: theme.textTheme.titleLarge?.copyWith(
                fontWeight: FontWeight.bold,
              ),
            ),
            const SizedBox(height: 8),
            Text(
              'Create a project to organize your work',
              style: theme.textTheme.bodyMedium?.copyWith(
                color: colorScheme.onSurface.withValues(alpha: 0.6),
              ),
            ),
            const SizedBox(height: 24),
            FilledButton.tonalIcon(
              onPressed: () => _showCreateDialog(),
              icon: const Icon(Icons.add),
              label: const Text('Create Project'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildProjectCard(Project project, ThemeData theme) {
    final colorScheme = theme.colorScheme;
    return Card(
      margin: const EdgeInsets.only(bottom: 8),
      child: ListTile(
        leading: Container(
          padding: const EdgeInsets.all(8),
          decoration: BoxDecoration(
            color: colorScheme.primaryContainer,
            borderRadius: BorderRadius.circular(8),
          ),
          child: Icon(Icons.folder, color: colorScheme.onPrimaryContainer),
        ),
        title: Text(project.name, style: const TextStyle(fontWeight: FontWeight.w600)),
        subtitle: Text(
          project.description.isNotEmpty
              ? project.description
              : '${project.type} project',
          maxLines: 1,
          overflow: TextOverflow.ellipsis,
        ),
        trailing: Text('${project.fileCount} files'),
      ),
    );
  }

  void _showCreateDialog() {
    final nameController = TextEditingController();
    final descController = TextEditingController();

    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Create Project'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: nameController,
              decoration: const InputDecoration(
                labelText: 'Project name',
                hintText: 'My awesome project',
              ),
              autofocus: true,
            ),
            const SizedBox(height: 12),
            TextField(
              controller: descController,
              decoration: const InputDecoration(
                labelText: 'Description (optional)',
                hintText: 'Brief description',
              ),
              maxLines: 2,
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancel'),
          ),
          FilledButton(
            onPressed: () {
              final name = nameController.text.trim();
              if (name.isNotEmpty) {
                setState(() {
                  _projects.add(Project(
                    id: DateTime.now().millisecondsSinceEpoch.toString(),
                    name: name,
                    description: descController.text.trim(),
                    createdAt: DateTime.now(),
                  ));
                });
              }
              Navigator.pop(ctx);
            },
            child: const Text('Create'),
          ),
        ],
      ),
    );
  }
}

