import 'dart:async';
import 'dart:convert';

import 'package:flutter_riverpod/flutter_riverpod.dart';
import 'package:web_socket_channel/web_socket_channel.dart';

/// Real-time system data from the desktop backend.
class SystemSnapshot {
  final Map<String, dynamic> cpu;
  final Map<String, dynamic> ram;
  final List<Map<String, dynamic>> gpu;
  final Map<String, dynamic> storage;
  final Map<String, dynamic> network;
  final Map<String, dynamic> battery;
  final Map<String, dynamic> system;
  final List<Map<String, dynamic>> processes;
  final List<Map<String, dynamic>> applications;
  final Map<String, dynamic> services;
  final Map<String, dynamic> devices;
  final List<Map<String, dynamic>> windows;
  final Map<String, dynamic> files;
  final Map<String, dynamic> events;
  final Map<String, dynamic> performanceHistory;

  SystemSnapshot({
    required this.cpu,
    required this.ram,
    required this.gpu,
    required this.storage,
    required this.network,
    required this.battery,
    required this.system,
    required this.processes,
    this.applications = const [],
    this.services = const {},
    this.devices = const {},
    this.windows = const [],
    this.files = const {},
    this.events = const {},
    this.performanceHistory = const {},
  });

  factory SystemSnapshot.fromJson(Map<String, dynamic> json) {
    return SystemSnapshot(
      cpu: json['cpu'] as Map<String, dynamic>? ?? {},
      ram: json['ram'] as Map<String, dynamic>? ?? {},
      gpu: (json['gpu'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [],
      storage: json['storage'] as Map<String, dynamic>? ?? {},
      network: json['network'] as Map<String, dynamic>? ?? {},
      battery: json['battery'] as Map<String, dynamic>? ?? {},
      system: json['system'] as Map<String, dynamic>? ?? {},
      processes: (json['processes'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [],
      applications: (json['applications'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [],
      services: json['services'] as Map<String, dynamic>? ?? {},
      devices: json['devices'] as Map<String, dynamic>? ?? {},
      windows: (json['windows'] as List<dynamic>?)
              ?.map((e) => e as Map<String, dynamic>)
              .toList() ??
          [],
      files: json['files'] as Map<String, dynamic>? ?? {},
      events: json['events'] as Map<String, dynamic>? ?? {},
      performanceHistory:
          json['performance_history'] as Map<String, dynamic>? ?? {},
    );
  }

  // CPU getters
  double? get cpuPercent => cpu['percent']?.toDouble();
  double? get cpuTemp => cpu['temperature_celsius']?.toDouble();
  double? get cpuFreq => cpu['frequency_current_mhz']?.toDouble();
  double? get cpuVoltage => cpu['voltage']?.toDouble();
  int? get coresPhysical => cpu['cores_physical'] as int?;
  int? get coresLogical => cpu['cores_logical'] as int?;
  String? get cpuBrand => cpu['brand']?.toString();
  List<dynamic> get cpuPerCore => cpu['percent_per_core'] as List<dynamic>? ?? [];

  // RAM getters
  double? get ramPercent => ram['percent']?.toDouble();
  double? get ramUsedGb => ram['used_gb']?.toDouble();
  double? get ramTotalGb => ram['total_gb']?.toDouble();
  double? get ramFreeGb => ram['free_gb']?.toDouble();
  double? get ramCachedGb => ram['cached_gb']?.toDouble();
  double? get ramCommittedGb => ram['committed_gb']?.toDouble();
  double? get swapUsedGb => ram['swap_used_gb']?.toDouble();
  double? get swapTotalGb => ram['swap_total_gb']?.toDouble();
  double? get swapPercent => ram['swap_percent']?.toDouble();

  // GPU getters
  String? get gpuName => gpu.isNotEmpty ? gpu.first['name']?.toString() : null;
  double? get gpuUsage =>
      gpu.isNotEmpty ? gpu.first['usage_percent']?.toDouble() : null;
  double? get gpuTemp =>
      gpu.isNotEmpty ? gpu.first['temperature_celsius']?.toDouble() : null;
  double? get gpuVramUsed =>
      gpu.isNotEmpty ? gpu.first['vram_used_mb']?.toDouble() : null;
  double? get gpuVramTotal =>
      gpu.isNotEmpty ? gpu.first['vram_total_mb']?.toDouble() : null;
  double? get gpuPowerDraw =>
      gpu.isNotEmpty ? gpu.first['power_draw_watts']?.toDouble() : null;
  double? get gpuFanSpeed =>
      gpu.isNotEmpty ? gpu.first['fan_speed_percent']?.toDouble() : null;

  // Storage getters
  double? get storageTotalGb => storage['total_gb']?.toDouble();
  double? get storageUsedGb => storage['used_gb']?.toDouble();
  double? get storageFreeGb => storage['free_gb']?.toDouble();
  List<dynamic> get storageDrives => storage['drives'] as List<dynamic>? ?? [];

  // Network getters
  double? get downloadSpeedMbps => network['download_speed_mbps']?.toDouble();
  double? get uploadSpeedMbps => network['upload_speed_mbps']?.toDouble();
  double? get latencyMs => network['latency_ms']?.toDouble();
  String? get ipAddress => network['ip_address']?.toString();
  String? get gateway => network['gateway']?.toString();
  List<dynamic> get dnsServers => network['dns_servers'] as List<dynamic>? ?? [];
  String? get wifiName => network['wifi_name']?.toString();
  int? get signalStrength => network['signal_strength'] as int?;
  bool? get ethernetConnected => network['ethernet_connected'] as bool?;

  // Battery getters
  double? get batteryPercent => battery['percent']?.toDouble();
  bool? get batteryCharging => battery['charging'] as bool?;
  double? get batteryHealth => battery['health_percent']?.toDouble();
  double? get designCapacityWh => battery['design_capacity_wh']?.toDouble();
  double? get fullChargeCapacityWh =>
      battery['full_charge_capacity_wh']?.toDouble();
  String? get batteryManufacturer => battery['manufacturer']?.toString();
  String? get batteryStatus => battery['battery_status']?.toString();

  // System getters
  String? get os => system['os']?.toString();
  String? get osVersion => system['os_version']?.toString();
  String? get osBuild => system['os_build']?.toString();
  String? get hostname => system['hostname']?.toString();
  String? get username => system['username']?.toString();
  String? get uptime => system['uptime_formatted']?.toString();
  String? get architecture => system['architecture']?.toString();
  double? get bootTime => system['boot_time']?.toDouble();
}

/// System monitor state.
enum SystemMonitorStatus {
  disconnected,
  connecting,
  connected,
  error,
}

class SystemMonitorState {
  final SystemMonitorStatus status;
  final SystemSnapshot? snapshot;
  final String? error;

  const SystemMonitorState({
    this.status = SystemMonitorStatus.disconnected,
    this.snapshot,
    this.error,
  });

  SystemMonitorState copyWith({
    SystemMonitorStatus? status,
    SystemSnapshot? snapshot,
    String? error,
    bool clearError = false,
  }) {
    return SystemMonitorState(
      status: status ?? this.status,
      snapshot: snapshot ?? this.snapshot,
      error: clearError ? null : error ?? this.error,
    );
  }
}

/// Service that connects to the backend WebSocket and streams system metrics.
final systemMonitorProvider =
    StateNotifierProvider<SystemMonitorNotifier, SystemMonitorState>(
  (ref) => SystemMonitorNotifier(),
);

class SystemMonitorNotifier extends StateNotifier<SystemMonitorState> {
  SystemMonitorNotifier() : super(const SystemMonitorState());

  WebSocketChannel? _channel;
  StreamSubscription<dynamic>? _subscription;
  Timer? _reconnectTimer;
  int _reconnectAttempts = 0;
  static const int _maxReconnectAttempts = 100;
  String _lastUrl = '';

  /// Connect to the system monitoring WebSocket.
  Future<void> connect({String url = 'ws://localhost:8000/api/v1/ws/system'}) async {
    if (state.status == SystemMonitorStatus.connecting ||
        state.status == SystemMonitorStatus.connected) {
      return;
    }

    _lastUrl = url;
    state = state.copyWith(status: SystemMonitorStatus.connecting, clearError: true);

    try {
      final channel = WebSocketChannel.connect(Uri.parse(url));
      _channel = channel;
      state = state.copyWith(status: SystemMonitorStatus.connected);

      _subscription = channel.stream.listen(
        (message) {
          final msg = message?.toString() ?? '';
          _handleMessage(msg);
        },
        onError: (Object error) {
          state = state.copyWith(
            status: SystemMonitorStatus.error,
            error: error.toString(),
          );
          _scheduleReconnect();
        },
        onDone: () {
          state = state.copyWith(status: SystemMonitorStatus.disconnected);
          _scheduleReconnect();
        },
      );
    } catch (error) {
      state = state.copyWith(
        status: SystemMonitorStatus.error,
        error: error.toString(),
      );
      _scheduleReconnect();
    }
  }

  void _handleMessage(String raw) {
    Map<String, dynamic> json;
    try {
      final decoded = jsonDecode(raw);
      if (decoded is! Map<String, dynamic>) return;
      json = decoded;
    } catch (_) {
      return;
    }

    final type = json['type']?.toString() ?? '';

    // Handle ping/pong
    if (type == 'ping') {
      _send({'type': 'pong'});
      return;
    }
    if (type == 'pong') return;

    // Handle system data
    if (type == 'system' && json['data'] is Map<String, dynamic>) {
      final data = json['data'] as Map<String, dynamic>;
      final snapshot = SystemSnapshot.fromJson(data);
      state = state.copyWith(
        status: SystemMonitorStatus.connected,
        snapshot: snapshot,
      );
    }
  }

  void _send(Map<String, dynamic> data) {
    if (_channel != null && state.status == SystemMonitorStatus.connected) {
      try {
        _channel!.sink.add(jsonEncode(data));
      } catch (_) {}
    }
  }

  void _scheduleReconnect() {
    if (_reconnectAttempts >= _maxReconnectAttempts) return;

    _reconnectTimer?.cancel();
    _reconnectAttempts++;
    final delay = Duration(
      seconds: (_reconnectAttempts * 2).clamp(1, 60),
    );

    _reconnectTimer = Timer(delay, () {
      _reconnectTimer = null;
      if (state.status != SystemMonitorStatus.connected) {
        connect(url: _lastUrl);
      }
    });
  }

  Future<void> disconnect() async {
    _reconnectTimer?.cancel();
    _reconnectTimer = null;
    _reconnectAttempts = 0;
    await _subscription?.cancel();
    await _channel?.sink.close();
    _subscription = null;
    _channel = null;
    state = const SystemMonitorState(status: SystemMonitorStatus.disconnected);
  }

  @override
  void dispose() {
    _reconnectTimer?.cancel();
    _subscription?.cancel();
    _channel?.sink.close();
    super.dispose();
  }
}