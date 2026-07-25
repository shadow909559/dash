/// Shared constants for the DASH mobile app.
library;

const String appName = 'DASH';
const String appVersion = '1.0.0';
const String defaultBackendUrl = 'http://localhost:8000';
const String defaultWebSocketUrl = 'ws://localhost:8000/api/v1/ws';
const String apiPrefix = '/api/v1';

// Auth
const String healthPath = '$apiPrefix/health';
const String authLoginPath = '$apiPrefix/auth/login';
const String authRegisterPath = '$apiPrefix/auth/register';
const String authRefreshPath = '$apiPrefix/auth/refresh';
const String authMePath = '$apiPrefix/auth/me';
const String authLogoutPath = '$apiPrefix/auth/logout';

// Conversations
const String conversationsPath = '$apiPrefix/conversations';
const String conversationMessagesPath = '$apiPrefix/conversations';

// Memory
const String memoryPath = '$apiPrefix/memory';

// RAG
const String ragPath = '$apiPrefix/rag';

// Automation
const String automationPath = '$apiPrefix/automation';

// Personal
const String personalPath = '$apiPrefix/personal';

// Sync
const String syncPath = '$apiPrefix/sync';

// WebSocket
const String websocketPath = '$apiPrefix/ws';

// Voice
const String voicePath = '$apiPrefix/voice';

// Vision
const String visionPath = '$apiPrefix/vision';

// Plugins
const String pluginsPath = '$apiPrefix/plugins';

// Desktop
const String desktopPath = '$apiPrefix/desktop';

// Goals / Executive
const String goalsPath = '$apiPrefix/goals';

// Notifications
const String notificationsPath = '$apiPrefix/notifications';

// Search
const String searchPath = '$apiPrefix/search';

// Cache keys
const String cacheConversationsKey = 'cached_conversations';
const String cacheMemoriesKey = 'cached_memories';
const String cacheSettingsKey = 'cached_settings';
const String cacheTasksKey = 'cached_tasks';