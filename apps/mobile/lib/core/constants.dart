/// Shared constants for the DASH mobile app.
library;

const String appName = 'DASH';
const String appVersion = '0.1.0';
const String defaultBackendUrl = 'http://localhost:8000';
const String apiPrefix = '/api/v1';
const String healthPath = '$apiPrefix/health';
const String websocketPath = '$apiPrefix/ws';
const String defaultWebSocketUrl = 'ws://localhost:8000$websocketPath';
