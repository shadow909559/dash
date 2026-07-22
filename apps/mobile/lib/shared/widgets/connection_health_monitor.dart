import 'dart:async';
import 'dart:math' as math;

import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import '../../core/services/websocket_service.dart';
import '../../core/sync/sync_service.dart';
import '../../core/sync/sync_state.dart';

/// A widget that monitors and displays the connection health.
///
/// Shows a persistent bar at the top when offline/reconnecting,
/// and a compact indicator dot when connected.
class ConnectionHealthMonitor extends ConsumerStatefulWidget {
  const ConnectionHealthMonitor({super.key});

  @override
  ConsumerState<ConnectionHealthMonitor> createState() =>
      _ConnectionHealthMonitorState();
}

class _ConnectionHealthMonitorState
    extends ConsumerState<ConnectionHealthMonitor>
    with SingleTickerProviderStateMixin {
  late final AnimationController _animController;
  StreamSubscription<WebSocketStatus>? _statusSub;

  @override
  void initState() {
    super.initState();
    _animController = AnimationController(
      vsync: this,
      duration: const Duration(milliseconds: 1500),
    )..repeat();

    // Start listening for status changes after build
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _statusSub = ref.read(webSocketServiceProvider.notifier).statusStream
          .listen((_) {});
    });
  }

  @override
  void dispose() {
    _animController.dispose();
    _statusSub?.cancel();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final wsState = ref.watch(webSocketServiceProvider);
    final syncState = ref.watch(syncServiceProvider);

    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        // Status bar for non-connected states
        if (wsState.status != WebSocketStatus.connected)
          _buildStatusBar(context, wsState, syncState),

        // Compact indicator for connected state
        if (wsState.status == WebSocketStatus.connected)
          _buildConnectedIndicator(context, syncState),
      ],
    );
  }

  Widget _buildStatusBar(
    BuildContext context,
    WebSocketState wsState,
    SyncState syncState,
  ) {
    Color bgColor;
    String text;
    IconData icon;

    switch (wsState.status) {
      case WebSocketStatus.disconnected:
        bgColor = Colors.orange.shade800;
        text = 'Offline';
        icon = Icons.cloud_off;
        break;
      case WebSocketStatus.connecting:
        bgColor = Colors.blue.shade700;
        text = 'Connecting...';
        icon = Icons.cloud_upload;
        break;
      case WebSocketStatus.reconnecting:
        bgColor = Colors.blue.shade700;
        text = 'Reconnecting...';
        icon = Icons.sync;
        break;
      case WebSocketStatus.error:
        bgColor = Colors.red.shade700;
        text = wsState.errorMessage ?? 'Connection error';
        icon = Icons.error;
        break;
      case WebSocketStatus.connected:
        bgColor = Colors.green.shade700;
        text = 'Connected';
        icon = Icons.cloud_done;
        break;
    }

    // Show pending messages count
    if (syncState.pendingMessages > 0) {
      text += ' (${syncState.pendingMessages} pending)';
    }

    return Container(
      width: double.infinity,
      color: bgColor,
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 4,
        bottom: 4,
        left: 16,
        right: 16,
      ),
      child: Row(
        mainAxisSize: MainAxisSize.min,
        children: [
          if (wsState.status == WebSocketStatus.connecting ||
              wsState.status == WebSocketStatus.reconnecting)
            const SizedBox(
              width: 16,
              height: 16,
              child: CircularProgressIndicator(
                strokeWidth: 2,
                valueColor: AlwaysStoppedAnimation<Color>(Colors.white),
              ),
            )
          else
            Icon(icon, color: Colors.white, size: 16),
          const SizedBox(width: 8),
          Expanded(
            child: Text(
              text,
              style: const TextStyle(color: Colors.white, fontSize: 13),
              overflow: TextOverflow.ellipsis,
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildConnectedIndicator(
    BuildContext context,
    SyncState syncState,
  ) {
    final bool isSyncing =
        syncState.serviceStatus == SyncServiceStatus.syncing;

    return Container(
      padding: EdgeInsets.only(
        top: MediaQuery.of(context).padding.top + 2,
      ),
      child: Row(
        mainAxisAlignment: MainAxisAlignment.end,
        children: [
          Padding(
            padding: const EdgeInsets.only(right: 12),
            child: Tooltip(
              message: _buildSyncTooltip(syncState),
              child: AnimatedBuilder(
                animation: _animController,
                builder: (context, child) {
                  final pulseAlpha = isSyncing
                      ? 0.4 + 0.3 * math.sin(_animController.value * math.pi * 2)
                      : 0.4;

                  return Container(
                    width: 8,
                    height: 8,
                    decoration: BoxDecoration(
                      shape: BoxShape.circle,
                      color: isSyncing ? Colors.blue : Colors.green,
                      boxShadow: [
                        BoxShadow(
                          color: isSyncing
                              ? Colors.blue.withValues(alpha: pulseAlpha)
                              : Colors.green.withValues(alpha: pulseAlpha),
                          blurRadius: 4,
                          spreadRadius: 1,
                        ),
                      ],
                    ),
                  );
                },
              ),
            ),
          ),
        ],
      ),
    );
  }

  String _buildSyncTooltip(SyncState syncState) {
    final parts = <String>['Connected'];
    if (syncState.totalSyncedConversations > 0) {
      parts.add('${syncState.totalSyncedConversations} conversations synced');
    }
    if (syncState.totalSyncedMemories > 0) {
      parts.add('${syncState.totalSyncedMemories} memories synced');
    }
    if (syncState.totalConflicts > 0) {
      parts.add('${syncState.totalConflicts} conflicts resolved');
    }
    if (syncState.lastSyncTimestamp != null) {
      parts.add('Last sync: ${syncState.lastSyncTimestamp}');
    }
    return parts.join('\n');
  }
}