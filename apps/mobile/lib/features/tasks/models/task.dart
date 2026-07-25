class Task {
  final String id;
  final String goalId;
  final String name;
  final String? description;
  final String status;
  final int attempt;
  final Map<String, dynamic>? metadata;
  final DateTime createdAt;
  final DateTime updatedAt;

  const Task({
    required this.id,
    required this.goalId,
    required this.name,
    this.description,
    required this.status,
    this.attempt = 0,
    this.metadata,
    required this.createdAt,
    required this.updatedAt,
  });

  factory Task.fromJson(Map<String, dynamic> json) {
    return Task(
      id: json['id'] as String? ?? '',
      goalId: json['goal_id'] as String? ?? '',
      name: json['name'] as String? ?? 'Untitled Task',
      description: json['description'] as String?,
      status: json['status'] as String? ?? 'pending',
      attempt: (json['attempt'] as int?) ?? 0,
      metadata: json['metadata'] as Map<String, dynamic>?,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ?? DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ?? DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'goal_id': goalId,
      'name': name,
      if (description != null) 'description': description,
      'status': status,
      'attempt': attempt,
      if (metadata != null) 'metadata': metadata,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  Task copyWith({
    String? id,
    String? goalId,
    String? name,
    String? description,
    String? status,
    int? attempt,
    Map<String, dynamic>? metadata,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Task(
      id: id ?? this.id,
      goalId: goalId ?? this.goalId,
      name: name ?? this.name,
      description: description ?? this.description,
      status: status ?? this.status,
      attempt: attempt ?? this.attempt,
      metadata: metadata ?? this.metadata,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}
