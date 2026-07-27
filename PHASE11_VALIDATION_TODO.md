# Phase 11 — DASH End-to-End Integration & Validation TODO

## STATUS: ✅ Implementation Complete — Run Validation

## STEP 1: Remove Dead Code
- [x] Identify orphaned `api/v1/` directory
- [x] Remove `api/v1/` directory (backed up)
- [x] Fix any imports referencing v1

## STEP 2: Create Missing REST API Routes
- [x] Create `api/routes/desktop_control.py` — volume, brightness, clipboard, mouse, keyboard, power, screenshot, lock, sleep, restart, shutdown
- [x] Create `api/routes/files_rest.py` — file search, preview, copy, move, rename, delete, recycle bin, browse, drives, special-folders
- [x] Create `api/routes/window_manager.py` — window list, focus, close, move, resize, snap, minimize, maximize, active window

## STEP 3: Register New Routes in `api/router.py`
- [x] Import and register desktop_control, files_rest, window_manager routers

## STEP 4: Verify Service Files Exist (All Already Implemented)
- [x] `services/media.py` — volume, mute, brightness, media keys
- [x] `services/clipboard.py` — read, write, clear clipboard
- [x] `services/mouse.py` — move, click, double-click, scroll, position
- [x] `services/keyboard.py` — type text, press key, hotkey
- [x] `services/power.py` — shutdown, restart, lock, sleep, hibernate, logoff, abort-shutdown
- [x] `services/notifications.py` — desktop notifications
- [x] `services/window.py` — list, focus, minimize, maximize, close windows
- [x] `services/files.py` — file system operations
- [x] `tools/window_management_tools.py` — _find_window, restore, move, resize, snap, detect active window, list monitors

## STEP 5: Tool Classes (All Already Implemented)
- [x] Power tools in `tools/power_tools.py`
- [x] Window management tools in `tools/window_management_tools.py`
- [x] File operation tools in `tools/file_tools.py`, `tools/explorer_tools.py`, `tools/folder_tools.py`
- [x] Desktop automation tools in `tools/desktop_automation.py`
- [x] System tools in `tools/system_tools.py`, `tools/system_management_tools.py`
- [x] Device tools in `tools/device_tools.py`

## STEP 6: Update Desktop Frontend
- [x] Update `apps/desktop/src/lib/api.ts` with full desktop, windows, files, aiOs API calls
- [x] WebSocket client ready in `wsClient.ts`
- [x] System monitor client ready in `systemMonitor.ts`
- [x] Dashboard page renders all metrics (CPU, RAM, Storage, GPU, Network, Battery, System)
- [x] Chat page with streaming via WebSocket

## STEP 7: Update Mobile App
- [x] Mobile `api_client.dart` — central HTTP client with JWT auth ready
- [x] Mobile `websocket_service.dart` — full WS client with auto-reconnect, heartbeat, message routing
- [x] Mobile `constants.dart` — all API paths defined
- [x] Dashboard page with live system metrics

## STEP 8: Create Validation Script
- [x] Create `apps/backend/dash_backend/validate_integration.py`
- [ ] Run validation script against running backend
- [ ] Test all endpoints
- [ ] Test all WebSocket events

## STEP 9: Fix Remaining Issues
- [ ] Start backend server
- [ ] Run validation and fix any failures
- [ ] Ensure all checkboxes are green (PASS)
- [ ] Install dependencies: pip install httpx websockets

### How to Run
1. Start backend: `cd apps/backend && python -m uvicorn dash_backend.main:app --reload --port 8000`
2. Run validation: `cd apps/backend && python -m dash_backend.validate_integration`
3. Or run as script: `python apps/backend/dash_backend/validate_integration.py`

