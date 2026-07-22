# DASH Flutter — Setup Guide

## Prerequisites

- Flutter SDK >= 3.5.0
- Dart SDK >= 3.5.0
- Android Studio / Xcode (for emulators)
- A running DASH backend (FastAPI)

## Getting Started

```bash
# Navigate to the Flutter app
cd apps/mobile

# Install dependencies
flutter pub get

# Run on connected device or emulator
flutter run

# Run on web
flutter run -d chrome

# Run on Windows desktop
flutter run -d windows
```

## Configuration

Edit `lib/core/constants.dart` to configure:

- `defaultBackendUrl` — Backend API URL (default: `http://localhost:8000`)
- `defaultWebSocketUrl` — WebSocket URL (default: `ws://localhost:8000`)

For production, these should be environment-specific or configurable at runtime.

## Backend Setup

The Flutter app requires a running DASH backend. See `/apps/backend/README.md` for backend setup instructions.

## Troubleshooting

- **"flutter pub get" fails** — Check your Flutter SDK version
- **Connection refused** — Ensure the backend is running
- **WebSocket disconnect** — Check network, enable auto-reconnect
- **Build errors** — Run `flutter clean && flutter pub get`
