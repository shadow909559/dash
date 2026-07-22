# Testing Guide

## Test Suites

### Backend Tests

```bash
cd apps/backend

# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run specific test file
python -m pytest tests/test_auth.py

# Run with coverage
python -m pytest --cov=dash_backend
```

### Frontend Tests

```bash
cd apps/mobile

# Run all tests
flutter test

# Run with coverage
flutter test --coverage

# Run specific test file
flutter test test/auth_service_test.dart
```

## Test Categories

### Backend: 129 Tests

| Category | Tests | Description |
|----------|-------|-------------|
| Auth | 12 | JWT, PBKDF2, registration, login, refresh |
| Security | 35 | Path traversal, injection, rate limiting |
| Memory | 15 | CRUD, retrieval, summarization, pruning |
| Conversations | 8 | CRUD, messaging |
| Agents | 5 | Agent lifecycle |
| Skills | 6 | Skill routing |
| Sync | 5 | Offline queue, sync state |
| Health | 3 | Health endpoint |
| Filesystem | 4 | File operations |
| Automation | 2 | Automation persistence |
| Scheduler | 3 | Scheduled tasks |
| WebSocket | 4 | Connection, messaging |
| Vision | 7 | OCR, UI detection, image understanding |
| Voice | 22 | STT, TTS, VAD, wake word |
| Plugins | 12 | Manifest, permissions, sandbox, API |

### Frontend: 31 Tests

| Category | Tests | Description |
|----------|-------|-------------|
| Auth | 4 | User from JSON, token response |
| Chat | 10 | Messages, conversations, streaming |
| Workspace | 5 | Header, suggestions, quick actions |
| Projects | 4 | Create, render, cancel |
| Sync | 5 | Offline queue, sync state |
| Widget | 1 | Splash scaffold |
| Navigation | 2 | Responsive layout |

## Writing Tests

### Backend Test Pattern

```python
import pytest
from httpx import AsyncClient, ASGITransport
from dash_backend.main import app

@pytest.mark.asyncio
async def test_example():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/api/v1/health")
        assert response.status_code == 200
```

### Frontend Test Pattern

```dart
import 'package:flutter_test/flutter_test.dart';

void main() {
  testWidgets('description', (WidgetTester tester) async {
    await tester.pumpWidget(MyWidget());
    expect(find.text('Expected'), findsOneWidget);
  });
}
