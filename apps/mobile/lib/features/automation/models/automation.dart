class Automation {
  const Automation({
    required this.id,
    required this.name,
    this.description,
    required this.triggerType,
    this.schedule,
    required this.toolName,
    required this.toolArguments,
    required this.enabled,
    required this.createdAt,
    required this.updatedAt,
  });

  final String id;
  final String name;
  final String? description;
  final String triggerType;
  final Map<String, dynamic>? schedule;
  final String toolName;
  final List<dynamic> toolArguments;
  final bool enabled;
  final DateTime createdAt;
  final DateTime updatedAt;

  factory Automation.fromJson(Map<String, dynamic> json) {
    return Automation(
      id: json['id'] as String,
      name: json['name'] as String,
      description: json['description'] as String?,
      triggerType: json['trigger_type'] as String,
      schedule: json['schedule'] as Map<String, dynamic>?,
      toolName: json['tool_name'] as String,
      toolArguments: (json['tool_arguments'] as List<dynamic>? ?? [])
          .map((e) => e is Map<String, dynamic> ? Map<String, dynamic>.from(e) : e)
          .toList(),
      enabled: json['enabled'] as bool? ?? true,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
      updatedAt: DateTime.tryParse(json['updated_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'name': name,
      if (description != null) 'description': description,
      'trigger_type': triggerType,
      if (schedule != null) 'schedule': schedule,
      'tool_name': toolName,
      'tool_arguments': toolArguments,
      'enabled': enabled,
      'created_at': createdAt.toIso8601String(),
      'updated_at': updatedAt.toIso8601String(),
    };
  }

  Automation copyWith({
    String? id,
    String? name,
    String? description,
    String? triggerType,
    Map<String, dynamic>? schedule,
    String? toolName,
    List<dynamic>? toolArguments,
    bool? enabled,
    DateTime? createdAt,
    DateTime? updatedAt,
  }) {
    return Automation(
      id: id ?? this.id,
      name: name ?? this.name,
      description: description ?? this.description,
      triggerType: triggerType ?? this.triggerType,
      schedule: schedule ?? this.schedule,
      toolName: toolName ?? this.toolName,
      toolArguments: toolArguments ?? this.toolArguments,
      enabled: enabled ?? this.enabled,
      createdAt: createdAt ?? this.createdAt,
      updatedAt: updatedAt ?? this.updatedAt,
    );
  }
}

class AutomationHistory {
  const AutomationHistory({
    required this.id,
    required this.automationId,
    required this.status,
    this.summary,
    this.output,
    this.error,
    required this.startedAt,
    this.finishedAt,
    this.durationMs,
    required this.createdAt,
  });

  final String id;
  final String automationId;
  final String status;
  final String? summary;
  final String? output;
  final String? error;
  final DateTime startedAt;
  final DateTime? finishedAt;
  final int? durationMs;
  final DateTime createdAt;

  factory AutomationHistory.fromJson(Map<String, dynamic> json) {
    return AutomationHistory(
      id: json['id'] as String,
      automationId: json['automation_id'] as String,
      status: json['status'] as String,
      summary: json['summary'] as String?,
      output: json['output'] as String?,
      error: json['error'] as String?,
      startedAt: DateTime.tryParse(json['started_at'] as String? ?? '') ??
          DateTime.now(),
      finishedAt: json['finished_at'] != null
          ? DateTime.tryParse(json['finished_at'] as String)
          : null,
      durationMs: json['duration_ms'] as int?,
      createdAt: DateTime.tryParse(json['created_at'] as String? ?? '') ??
          DateTime.now(),
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
      'automation_id': automationId,
      'status': status,
      if (summary != null) 'summary': summary,
      if (output != null) 'output': output,
      if (error != null) 'error': error,
      'started_at': startedAt.toIso8601String(),
      if (finishedAt != null) 'finished_at': finishedAt!.toIso8601String(),
      if (durationMs != null) 'duration_ms': durationMs,
      'created_at': createdAt.toIso8601String(),
    };
  }
}
