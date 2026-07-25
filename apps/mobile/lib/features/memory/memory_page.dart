import 'dart:async';
import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:go_router/go_router.dart';
import 'package:shimmer/shimmer.dart';
import '../../../core/routing/app_routes.dart';
import './models/memory_item.dart';
import './memory_provider.dart';

const List<String> memoryCategoryOptions = [
  'general',
  'fact',
  'preference',
  'conversation',
  'knowledge',
  'task',
  'user',
];

const Map<String, IconData> memoryCategoryIcons = {
  'general': Icons.memory_outlined,
  'fact': Icons.check_circle_outlined,
  'preference': Icons.favorite_outlined,
  'conversation': Icons.chat_bubble_outlined,
  'knowledge': Icons.lightbulb_outlined,
  'task': Icons.task_alt_outlined,
  'user': Icons.person_outlined,
};

class MemoryPage extends ConsumerStatefulWidget {
  const MemoryPage({super.key});

  @override
  ConsumerState<MemoryPage> createState() => _MemoryPageState();
}

class _MemoryPageState extends ConsumerState<MemoryPage> {
  final TextEditingController _searchController = TextEditingController();
  final ScrollController _scrollController = ScrollController();
  Timer? _searchDebounce;

  @override
  void dispose() {
    _searchDebounce?.cancel();
    _searchController.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  void _onSearchChanged(String value) {
    _searchDebounce?.cancel();
    _searchDebounce = Timer(const Duration(milliseconds: 300), () {
      if (mounted) {
        ref.read(memoryProvider.notifier).setSearchQuery(value);
      }
    });
  }

  Future<void> _showCreateMemorySheet() async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (ctx) => _MemoryFormSheet(
        title: 'New Memory',
        onSubmit: (content, category, source, importance) {
          ref.read(memoryProvider.notifier).createMemory(
                content: content,
                category: category,
                source: source,
                importance: importance,
              );
          if (mounted) Navigator.pop(ctx);
        },
      ),
    );
  }

  Future<void> _showEditMemorySheet(MemoryItem memory) async {
    await showModalBottomSheet(
      context: context,
      isScrollControlled: true,
      useSafeArea: true,
      builder: (ctx) => _MemoryFormSheet(
        title: 'Edit Memory',
        initialContent: memory.content,
        initialCategory: memory.category,
        initialSource: memory.source,
        initialImportance: memory.importance ?? 1,
        onSubmit: (content, category, source, importance) {
          ref.read(memoryProvider.notifier).updateMemory(
                memory.id,
                content: content,
                category: category,
                source: source,
                importance: importance,
              );
          if (mounted) Navigator.pop(ctx);
        },
      ),
    );
  }

  Future<void> _confirmDelete(String id) async {
    final confirmed = await showDialog<bool>(
      context: context,
      builder: (ctx) => AlertDialog(
        icon: const Icon(Icons.delete_outline, color: Colors.red),
        title: const Text('Delete Memory'),
        content: const Text('This action cannot be undone.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
          FilledButton(
            onPressed: () => Navigator.pop(ctx, true),
            style: FilledButton.styleFrom(backgroundColor: Colors.red),
            child: const Text('Delete'),
          ),
        ],
      ),
    );
    if (confirmed == true && mounted) {
      await ref.read(memoryProvider.notifier).deleteMemory(id);
    }
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final memoryState = ref.watch(memoryProvider);
    final categories = memoryCategoryOptions;

    return Scaffold(
      body: Column(
        children: [
          _buildHeader(theme, colorScheme, memoryState),
          _buildCategoryFilters(memoryState, categories, colorScheme),
          _buildSearchBar(colorScheme),
          Expanded(child: _buildBody(memoryState, colorScheme)),
        ],
      ),
      floatingActionButton: FloatingActionButton.extended(
        onPressed: _showCreateMemorySheet,
        icon: const Icon(Icons.add),
        label: const Text('New Memory'),
      ),
    );
  }

  Widget _buildHeader(ThemeData theme, ColorScheme colorScheme, MemoryState state) {
    return Container(
      padding: const EdgeInsets.fromLTRB(16, 16, 16, 8),
      child: Row(
        children: [
          Icon(Icons.memory, color: colorScheme.primary, size: 24),
          const SizedBox(width: 12),
          Text('Memory', style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
          const Spacer(),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
            decoration: BoxDecoration(
              color: colorScheme.primaryContainer,
              borderRadius: BorderRadius.circular(12),
            ),
            child: Text(
              '${state.filteredItems.length}',
              style: theme.textTheme.labelSmall?.copyWith(
                color: colorScheme.onPrimaryContainer,
                fontWeight: FontWeight.w600,
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildCategoryFilters(MemoryState state, List<String> categories, ColorScheme colorScheme) {
    return SizedBox(
      height: 48,
      child: ListView.builder(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 12),
        itemCount: categories.length + 1,
        itemBuilder: (context, index) {
          if (index == 0) {
            final isSelected = state.selectedCategory == null;
            return Padding(
              padding: const EdgeInsets.only(right: 8),
              child: FilterChip(
                label: const Text('All'),
                selected: isSelected,
                onSelected: (_) => ref.read(memoryProvider.notifier).setSelectedCategory(null),
                selectedColor: colorScheme.primaryContainer,
                labelStyle: TextStyle(color: isSelected ? colorScheme.onPrimaryContainer : null),
              ),
            );
          }
          final cat = categories[index - 1];
          final selected = state.selectedCategory == cat;
          return Padding(
            padding: const EdgeInsets.only(right: 8),
            child: FilterChip(
              label: Row(
                children: [
                  Icon(memoryCategoryIcons[cat] ?? Icons.memory_outlined, size: 16),
                  const SizedBox(width: 4),
                  Text(cat),
                ],
              ),
              selected: selected,
              onSelected: (_) => ref.read(memoryProvider.notifier).setSelectedCategory(
                selected ? null : cat,
              ),
              selectedColor: colorScheme.secondaryContainer,
              labelStyle: TextStyle(color: selected ? colorScheme.onSecondaryContainer : null),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSearchBar(ColorScheme colorScheme) {
    return Padding(
      padding: const EdgeInsets.symmetric(horizontal: 16, vertical: 8),
      child: TextField(
        controller: _searchController,
        onChanged: _onSearchChanged,
        decoration: InputDecoration(
          hintText: 'Search memories...',
          prefixIcon: const Icon(Icons.search, size: 20),
          suffixIcon: _searchController.text.isNotEmpty
              ? IconButton(
                  icon: const Icon(Icons.clear, size: 18),
                  onPressed: () {
                    _searchController.clear();
                    ref.read(memoryProvider.notifier).setSearchQuery('');
                  },
                )
              : null,
          filled: true,
          fillColor: colorScheme.surfaceContainerHighest,
          border: OutlineInputBorder(borderRadius: BorderRadius.circular(12), borderSide: BorderSide.none),
          contentPadding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
          isDense: true,
        ),
      ),
    );
  }

  Widget _buildBody(MemoryState state, ColorScheme colorScheme) {
    if (state.isLoading) {
      return _buildShimmerList(colorScheme);
    }

    if (state.errorMessage != null && state.items.isEmpty) {
      return _buildErrorState(colorScheme, state.errorMessage!);
    }

    if (state.items.isEmpty) {
      return _buildEmptyState(colorScheme);
    }

    if (state.filteredItems.isEmpty) {
      return _buildNoResults(colorScheme);
    }

    return RefreshIndicator(
      onRefresh: () => ref.read(memoryProvider.notifier).refreshMemories(),
      child: ListView.builder(
        controller: _scrollController,
        padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
        itemCount: state.filteredItems.length,
        itemBuilder: (context, index) {
          final memory = state.filteredItems[index];
          return Dismissible(
            key: ValueKey(memory.id),
            direction: DismissDirection.horizontal,
            confirmDismiss: (direction) async {
              if (direction == DismissDirection.endToStart) {
                final confirmed = await showDialog<bool>(
                  context: context,
                  builder: (ctx) => AlertDialog(
                    icon: const Icon(Icons.delete_outline, color: Colors.red),
                    title: const Text('Delete Memory'),
                    content: const Text('This action cannot be undone.'),
                    actions: [
                      TextButton(onPressed: () => Navigator.pop(ctx, false), child: const Text('Cancel')),
                      FilledButton(
                        onPressed: () => Navigator.pop(ctx, true),
                        style: FilledButton.styleFrom(backgroundColor: Colors.red),
                        child: const Text('Delete'),
                      ),
                    ],
                  ),
                );
                return confirmed == true;
              }
              if (direction == DismissDirection.startToEnd) {
                _showEditMemorySheet(memory);
                return false;
              }
              return false;
            },
            onDismissed: (direction) {
              if (direction == DismissDirection.endToStart) {
                ref.read(memoryProvider.notifier).deleteMemory(memory.id);
              }
            },
            background: _buildSwipeBackground(colorScheme, Icons.edit_outlined, Alignment.centerLeft),
            secondaryBackground: _buildSwipeBackground(colorScheme, Icons.delete_outline, Alignment.centerRight, color: Colors.red),
            child: _MemoryCard(
              memory: memory,
              onTap: () => context.push(AppRoutes.memoryDetails, extra: memory),
              onEdit: () => _showEditMemorySheet(memory),
              onDelete: () => _confirmDelete(memory.id),
            ),
          );
        },
      ),
    );
  }

  Widget _buildSwipeBackground(ColorScheme colorScheme, IconData icon, Alignment alignment, {Color? color}) {
    return Container(
      alignment: alignment,
      padding: const EdgeInsets.symmetric(horizontal: 20),
      color: color ?? colorScheme.primaryContainer,
      child: Icon(icon, color: colorScheme.onPrimaryContainer),
    );
  }

  Widget _buildShimmerList(ColorScheme colorScheme) {
    return ListView.builder(
      padding: const EdgeInsets.symmetric(horizontal: 12, vertical: 8),
      itemCount: 6,
      itemBuilder: (context, index) {
        return Shimmer.fromColors(
          baseColor: colorScheme.surfaceContainerHighest,
          highlightColor: colorScheme.surfaceContainerLow,
          child: Card(
            margin: const EdgeInsets.only(bottom: 12),
            child: Padding(
              padding: const EdgeInsets.all(16),
              child: Row(
                children: [
                  Container(width: 40, height: 40, decoration: BoxDecoration(color: Colors.white, borderRadius: BorderRadius.circular(8))),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Container(height: 12, width: double.infinity, color: Colors.white),
                        const SizedBox(height: 8),
                        Container(height: 10, width: 120, color: Colors.white),
                      ],
                    ),
                  ),
                ],
              ),
            ),
          ),
        );
      },
    );
  }

  Widget _buildErrorState(ColorScheme colorScheme, String error) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.error_outline, size: 48, color: colorScheme.error),
            const SizedBox(height: 16),
            Text('Something went wrong', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(error, textAlign: TextAlign.center, style: Theme.of(context).textTheme.bodySmall),
            const SizedBox(height: 16),
            FilledButton.icon(
              onPressed: () => ref.read(memoryProvider.notifier).loadMemories(),
              icon: const Icon(Icons.refresh),
              label: const Text('Retry'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildEmptyState(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Container(
              padding: const EdgeInsets.all(24),
              decoration: BoxDecoration(color: colorScheme.primaryContainer.withValues(alpha: 0.3), shape: BoxShape.circle),
              child: Icon(Icons.memory, size: 48, color: colorScheme.primary),
            ),
            const SizedBox(height: 24),
            Text('No memories yet', style: Theme.of(context).textTheme.titleLarge?.copyWith(fontWeight: FontWeight.bold)),
            const SizedBox(height: 8),
            Text(
              'Memories help Dash remember important information about you.',
              textAlign: TextAlign.center,
              style: Theme.of(context).textTheme.bodyMedium?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6)),
            ),
            const SizedBox(height: 24),
            FilledButton.icon(
              onPressed: _showCreateMemorySheet,
              icon: const Icon(Icons.add),
              label: const Text('Create Memory'),
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildNoResults(ColorScheme colorScheme) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(32),
        child: Column(
          children: [
            Icon(Icons.search_off, size: 48, color: colorScheme.onSurface.withValues(alpha: 0.3)),
            const SizedBox(height: 16),
            Text('No memories match your search', style: Theme.of(context).textTheme.bodyLarge?.copyWith(color: colorScheme.onSurface.withValues(alpha: 0.6))),
          ],
        ),
      ),
    );
  }
}

class _MemoryCard extends StatelessWidget {
  const _MemoryCard({
    required this.memory,
    this.onTap,
    this.onEdit,
    this.onDelete,
  });

  final MemoryItem memory;
  final VoidCallback? onTap;
  final VoidCallback? onEdit;
  final VoidCallback? onDelete;

  Color _categoryColor(String category, ColorScheme colorScheme) {
    switch (category) {
      case 'general':
        return colorScheme.primary;
      case 'fact':
        return colorScheme.tertiary;
      case 'preference':
        return Colors.pink;
      case 'conversation':
        return colorScheme.secondary;
      case 'knowledge':
        return Colors.amber;
      case 'task':
        return Colors.green;
      case 'user':
        return colorScheme.primary;
      default:
        return colorScheme.outline;
    }
  }

  IconData _categoryIcon(String category) {
    return memoryCategoryIcons[category] ?? Icons.memory_outlined;
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final color = _categoryColor(memory.category, colorScheme);

    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      color: colorScheme.surfaceContainerHighest,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(12)),
      child: InkWell(
        borderRadius: BorderRadius.circular(12),
        onTap: onTap,
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Row(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Container(
                width: 44,
                height: 44,
                decoration: BoxDecoration(
                  color: color.withValues(alpha: 0.15),
                  borderRadius: BorderRadius.circular(10),
                ),
                child: Icon(_categoryIcon(memory.category), size: 22, color: color),
              ),
              const SizedBox(width: 12),
              Expanded(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      memory.content,
                      maxLines: 2,
                      overflow: TextOverflow.ellipsis,
                      style: theme.textTheme.bodyMedium,
                    ),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 6,
                      runSpacing: 4,
                      children: [
                        _buildCategoryChip(memory.category, color, theme),
                        if (memory.source != null && memory.source!.isNotEmpty)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                            decoration: BoxDecoration(
                              color: colorScheme.surfaceContainerHighest,
                              borderRadius: BorderRadius.circular(4),
                            ),
                            child: Row(
                              mainAxisSize: MainAxisSize.min,
                              children: [
                                Icon(Icons.source_outlined, size: 12, color: colorScheme.onSurfaceVariant),
                                const SizedBox(width: 2),
                                Text(memory.source!, style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.onSurfaceVariant, fontSize: 10)),
                              ],
                            ),
                          ),
                        Text(_formatTime(memory.createdAt), style: theme.textTheme.labelSmall?.copyWith(color: colorScheme.onSurfaceVariant, fontSize: 11)),
                      ],
                    ),
                  ],
                ),
              ),
              const SizedBox(width: 8),
              if (_buildImportanceIndicator(theme) != null)
                const SizedBox(width: 4),
              PopupMenuButton<String>(
                icon: Icon(Icons.more_horiz, size: 18, color: colorScheme.onSurfaceVariant),
                onSelected: (value) {
                  if (value == 'edit' && onEdit != null) onEdit!();
                  if (value == 'delete' && onDelete != null) onDelete!();
                },
                itemBuilder: (context) => [
                  const PopupMenuItem(value: 'edit', child: ListTile(title: Text('Edit'), dense: true, leading: Icon(Icons.edit_outlined, size: 18))),
                  const PopupMenuItem(value: 'delete', child: ListTile(title: Text('Delete'), dense: true, leading: Icon(Icons.delete_outline, size: 18))),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildCategoryChip(String category, Color color, ThemeData theme) {
    return Container(
      padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
      decoration: BoxDecoration(color: color.withValues(alpha: 0.12), borderRadius: BorderRadius.circular(6)),
      child: Text(category, style: theme.textTheme.labelSmall?.copyWith(color: color, fontWeight: FontWeight.w600, fontSize: 10)),
    );
  }

  Widget? _buildImportanceIndicator(ThemeData theme) {
    final imp = memory.importance;
    if (imp == null || imp <= 0) return null;
    final level = imp.clamp(1, 3);
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: List.generate(3, (i) {
        final filled = i < level;
        return Icon(Icons.star_rounded, size: 14, color: filled ? Colors.amber : theme.colorScheme.outline);
      }),
    );
  }

  String _formatTime(DateTime dt) {
    final diff = DateTime.now().difference(dt);
    if (diff.inMinutes < 1) return 'Just now';
    if (diff.inHours < 1) return '${diff.inMinutes}m ago';
    if (diff.inDays < 1) return '${diff.inHours}h ago';
    if (diff.inDays < 7) return '${diff.inDays}d ago';
    return '${dt.month}/${dt.day}/${dt.year}';
  }
}

class _MemoryFormSheet extends StatefulWidget {
  const _MemoryFormSheet({
    required this.title,
    required this.onSubmit,
    this.initialContent,
    this.initialCategory,
    this.initialSource,
    this.initialImportance = 1,
  });

  final String title;
  final String? initialContent;
  final String? initialCategory;
  final String? initialSource;
  final int initialImportance;
  final FutureOr<void> Function(String content, String? category, String? source, int importance) onSubmit;

  @override
  State<_MemoryFormSheet> createState() => _MemoryFormSheetState();
}

class _MemoryFormSheetState extends State<_MemoryFormSheet> {
  late final TextEditingController _contentController;
  late final TextEditingController _sourceController;
  String? _selectedCategory;
  int _importance = 1;

  @override
  void initState() {
    super.initState();
    _contentController = TextEditingController(text: widget.initialContent ?? '');
    _sourceController = TextEditingController(text: widget.initialSource ?? '');
    _selectedCategory = widget.initialCategory ?? (widget.initialContent == null ? null : 'general');
    _importance = widget.initialImportance;
  }

  @override
  void dispose() {
    _contentController.dispose();
    _sourceController.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final theme = Theme.of(context);
    final colorScheme = theme.colorScheme;
    final isEditing = widget.initialContent != null;

    return Padding(
      padding: EdgeInsets.only(bottom: MediaQuery.of(context).viewInsets.bottom),
      child: Container(
        constraints: BoxConstraints(maxWidth: 600, maxHeight: MediaQuery.of(context).size.height * 0.85),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Container(
              width: 40,
              height: 4,
              margin: const EdgeInsets.symmetric(vertical: 12),
              decoration: BoxDecoration(color: colorScheme.outlineVariant, borderRadius: BorderRadius.circular(2)),
            ),
            Padding(
              padding: const EdgeInsets.symmetric(horizontal: 20),
              child: Row(
                children: [
                  Text(widget.title, style: theme.textTheme.titleLarge?.copyWith(fontWeight: FontWeight.w600)),
                  const Spacer(),
                  IconButton(onPressed: () => Navigator.pop(context), icon: const Icon(Icons.close)),
                ],
              ),
            ),
            const SizedBox(height: 12),
            Flexible(
              child: SingleChildScrollView(
                padding: const EdgeInsets.symmetric(horizontal: 20),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    TextField(
                      controller: _contentController,
                      maxLines: 5,
                      decoration: const InputDecoration(
                        labelText: 'Content',
                        hintText: 'What would you like Dash to remember?',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('Category', style: theme.textTheme.labelLarge),
                    const SizedBox(height: 8),
                    Wrap(
                      spacing: 8,
                      runSpacing: 8,
                      children: memoryCategoryOptions.map((cat) {
                        final selected = _selectedCategory == cat;
                        return ChoiceChip(
                          label: Text(cat),
                          selected: selected,
                          onSelected: (selected) {
                            if (selected) {
                              setState(() => _selectedCategory = cat);
                            }
                          },
                        );
                      }).toList(),
                    ),
                    const SizedBox(height: 16),
                    TextField(
                      controller: _sourceController,
                      decoration: const InputDecoration(
                        labelText: 'Source (optional)',
                        hintText: 'e.g., user_input, conversation',
                        border: OutlineInputBorder(),
                      ),
                    ),
                    const SizedBox(height: 16),
                    Text('Importance', style: theme.textTheme.labelLarge),
                    Row(
                      children: List.generate(3, (i) {
                        final value = i + 1;
                        final selected = _importance == value;
                        return IconButton(
                          onPressed: () => setState(() => _importance = value),
                          icon: Icon(Icons.star_rounded, size: 28, color: selected ? Colors.amber : colorScheme.outline),
                        );
                      }),
                    ),
                  ],
                ),
              ),
            ),
            Padding(
              padding: const EdgeInsets.all(20),
              child: SizedBox(
                width: double.infinity,
                child: FilledButton(
                  onPressed: () {
                    final content = _contentController.text.trim();
                    if (content.isEmpty) return;
                    final cat = _selectedCategory;
                    final src = _sourceController.text.trim().isEmpty ? null : _sourceController.text.trim();
                    widget.onSubmit(content, cat, src, _importance);
                  },
                  child: Text(isEditing ? 'Save Changes' : 'Create Memory'),
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}
