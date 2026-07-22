# DASH AI Operating System — Architecture

## Overview

DASH is a multi-platform AI Operating System with a Flutter mobile frontend and a FastAPI Python backend. The architecture follows a clean separation of concerns with clear data flow patterns.

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Mobile (Flutter)                      │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌─────────┐ │
│  │   UI     │  │  State   │  │ Services │  │  Sync   │ │
│  │  Layer   │◄─┤  Layer   │◄─┤  (HTTP   │◄─┤  Layer  │ │
│  │(Widgets) │  │ (Riverpod)│  │ + WS)   │  │ (Offline)│ │
│  └──────────┘  └──────────┘  └──────────┘  └─────────┘ │
│                          │                              │
└──────────────────────────┼──────────────────────────────┘
                           │ HTTP REST + WebSocket
                           │ (JSON)
┌──────────────────────────┼──────────────────────────────┐
│                    Backend (FastAPI)                     │
│                          │                              │
│  ┌───────────────────────┴─────────────────────────┐    │
│  │                   API Layer                      │    │
│  │  ┌─────────┐ ┌──────────┐ ┌──────────────────┐ │    │
│  │  │  Auth   │ │  Chat    │ │  WebSocket       │ │    │
│  │  │ Routes  │ │  Routes  │ │  Manager         │ │    │
│  │  └────┬────┘ └────┬─────┘ └────────┬─────────┘ │    │
│  └───────┼───────────┼────────────────┼───────────┘    │
│          │           │                │                 │
│  ┌───────┴───────────┴────────────────┴───────────┐    │
│  │              Service Layer                      │    │
│  │  ┌────────┐ ┌────────┐ ┌──────┐ ┌───────────┐  │    │
│  │  │  Auth  │ │  Chat  │ │Memory│ │  Sync     │  │    │
│  │  │ Service│ │ Service│ │Service│ │  Service  │  │    │
│  │  └────┬───┘ └────┬───┘ └──┬───┘ └─────┬─────┘  │    │
│  └───────┼──────────┼────────┼────────────┼────────┘    │
│          │          │        │            │              │
│  ┌───────┴──────────┴────────┴────────────┴────────┐    │
│  │              Database Layer                      │    │
│  │          (SQLAlchemy + PostgreSQL)               │    │
│  └─────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────┘
```

## Frontend Architecture (Flutter)

### Folder Structure

```
lib/
├── main.dart                 # App entry point
├── app.dart                  # MaterialApp configuration
├── core/
│   ├── constants.dart        # Shared constants
│   ├── theme/
│   │   └── app_theme.dart    # Light/dark themes, ChatTheme extension
│   ├── routing/
│   │   ├── app_router.dart   # GoRouter config
│   │   └── app_routes.dart   # Route paths
│   ├── services/
│   │   └── websocket_service.dart  # WebSocket management
│   └── sync/
│       ├── sync_service.dart  # Background sync
│       ├── sync_state.dart    # Sync state model
│       └── offline_queue.dart # Offline message queue
├── features/
│   ├── auth/
│   │   ├── login_page.dart
│   │   ├── services/auth_service.dart
│   │   ├── providers/auth_provider.dart
│   │   └── models/
│   ├── chat/
│   │   ├── chat_page.dart
│   │   ├── widgets/conversation_sidebar.dart
│   │   ├── providers/ (chat_provider, conversation_provider)
│   │   ├── services/conversation_repository.dart
│   │   └── models/
│   ├── dashboard/
│   ├── memory/
│   ├── settings/
│   ├── about/
│   └── splash/
└── shared/
    └── widgets/
        ├── app_shell.dart
        └── connection_health_monitor.dart
```

### State Management

The app uses **Riverpod** for state management:

- **StateNotifierProvider** — Complex mutable state (auth, chat, sync services)
- **StateProvider** — Simple state (theme mode, active conversation ID)
- **Provider** — Singletons and services (WebSocketService, AuthService)
- **FutureProvider** — Async data fetching

### Data Flow

```
User Action → Widget → Riverpod Provider → Service (HTTP/WS) → Backend
                ↑                                    │
                └──────────── Response ──────────────┘
```

### Connectivity Handling

- WebSocket auto-reconnects with exponential backoff (max 50 attempts)
- Offline queue persists messages to SharedPreferences
- Background sync service manages state synchronization
- ConnectionHealthMonitor displays connection status

## Dependencies

- **flutter_riverpod** — State management
- **go_router** — Declarative routing with auth guards
- **web_socket_channel** — WebSocket client
- **http** — REST API client
- **shared_preferences** — Local persistence
- **flutter_markdown** — Markdown rendering for chat
- **url_launcher** — External link handling

## Security

- JWT tokens stored in SharedPreferences
- Token refresh with automatic expiry detection
- Authorization header masking in logs
- Input validation on all forms
- Confirmation dialogs for destructive actions
