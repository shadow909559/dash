import 'package:flutter/foundation.dart';

/// Status of the sync connection.
enum SyncStatus {
  disconnected,
  connecting,
  connected,
  syncing,
  error,
}

/// Status of the sync service.
enum SyncServiceStatus {
  idle,
  syncing,
  offline,
  error,
}

/// Sync session information.
@immutable
class SyncSession {
  final String sessionId;
  final String clientId;
  final int recoveryCount;
  final bool requiresFullSync;

  const SyncSession({
    required this.sessionId,
    required this.clientId,
    this.recoveryCount = 0,
    this.requiresFullSync = false,
  });

  SyncSession copyWith({
    String? sessionId,
    String? clientId,
    int? recoveryCount,
    bool? requiresFullSync,
  }) {
    return SyncSession(
      sessionId: sessionId ?? this.sessionId,
      clientId: clientId ?? this.clientId,
      recoveryCount: recoveryCount ?? this.recoveryCount,
      requiresFullSync: requiresFullSync ?? this.requiresFullSync,
    );
  }

  Map<String, dynamic> toJson() => {
        'session_id': sessionId,
        'client_id': clientId,
        'recovery_count': recoveryCount,
        'requires_full_sync': requiresFullSync,
      };

  factory SyncSession.fromJson(Map<String, dynamic> json) {
    return SyncSession(
      sessionId: json['session_id'] as String? ?? '',
      clientId: json['client_id'] as String? ?? '',
      recoveryCount: json['recovery_count'] as int? ?? 0,
      requiresFullSync: json['requires_full_sync'] as bool? ?? false,
    );
  }
}

/// Sync service state.
class SyncState {
  final SyncStatus status;
  final SyncServiceStatus serviceStatus;
  final SyncSession? session;
  final String? lastSyncTimestamp;
  final int pendingMessages;
  final int retryCount;
  final String? errorMessage;
  final int totalSyncedConversations;
  final int totalSyncedMemories;
  final int totalConflicts;

  const SyncState({
    this.status = SyncStatus.disconnected,
    this.serviceStatus = SyncServiceStatus.idle,
    this.session,
    this.lastSyncTimestamp,
    this.pendingMessages = 0,
    this.retryCount = 0,
    this.errorMessage,
    this.totalSyncedConversations = 0,
    this.totalSyncedMemories = 0,
    this.totalConflicts = 0,
  });

  SyncState copyWith({
    SyncStatus? status,
    SyncServiceStatus? serviceStatus,
    SyncSession? session,
    String? lastSyncTimestamp,
    int? pendingMessages,
    int? retryCount,
    String? errorMessage,
    int? totalSyncedConversations,
    int? totalSyncedMemories,
    int? totalConflicts,
    bool clearError = false,
  }) {
    return SyncState(
      status: status ?? this.status,
      serviceStatus: serviceStatus ?? this.serviceStatus,
      session: session ?? this.session,
      lastSyncTimestamp: lastSyncTimestamp ?? this.lastSyncTimestamp,
      pendingMessages: pendingMessages ?? this.pendingMessages,
      retryCount: retryCount ?? this.retryCount,
      errorMessage: clearError ? null : (errorMessage ?? this.errorMessage),
      totalSyncedConversations:
          totalSyncedConversations ?? this.totalSyncedConversations,
      totalSyncedMemories: totalSyncedMemories ?? this.totalSyncedMemories,
      totalConflicts: totalConflicts ?? this.totalConflicts,
    );
  }

  bool get isConnected =>
      status == SyncStatus.connected || status == SyncStatus.syncing;

  bool get isOffline => status == SyncStatus.disconnected;
}