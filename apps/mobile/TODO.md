# DASH Desktop + Automation Complete Repair

## Status: ✅ ALL FIXES APPLIED

### Registration Form (Primary Bug)
- [x] **`GlassInput` never calls `field.didChange()`** — Wired `TextField.onChanged` to `field.didChange(value)`
- [x] **`login_page.dart` Form missing `autovalidateMode`** — Added `autovalidateMode: AutovalidateMode.onUserInteraction`
- [x] **`register_page.dart` Form missing `autovalidateMode`** — Added `autovalidateMode: AutovalidateMode.onUserInteraction`
- [x] Print statement added on successful form validation in both pages

### Infrastructure Bugs
- [x] **WebSocket URL wrong** — Changed to `ws://localhost:8000/api/v1/ws`
- [x] **ChatService Riverpod violation** — `_ws.connect()` deferred via `Future.microtask`
- [x] **Automation backend routes double-prefixed** — All routes changed from `/automation/...` to `/`
- [x] **Automation schema `tool_arguments` type mismatch** — Changed from `dict[str, Any]` to `list[str] | None`
- [x] **Automation schema `schedule` field** — Made nullable (`str | None`)

### Files Modified
1. `apps/mobile/lib/core/constants.dart` — Fixed WebSocket URL
2. `apps/mobile/lib/core/widgets/glassmorphism.dart` — Fixed `GlassInput` validator notification
3. `apps/mobile/lib/features/auth/login_page.dart` — Added `autovalidateMode` and print
4. `apps/mobile/lib/features/auth/register_page.dart` — Added `autovalidateMode` and print
5. `apps/mobile/lib/features/chat/providers/chat_provider.dart` — Fixed Riverpod violation
6. `apps/backend/dash_backend/automation/router.py` — Fixed route prefixes
7. `apps/backend/dash_backend/automation/schemas.py` — Fixed type definitions
8. `apps/backend/dash_backend/automation/service.py` — Made schedule optional
