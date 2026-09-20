# DASH — Technical Documentation & Viva Preparation

> **Grounding rule of this document:** every claim below was verified against the actual
> repository source on 2026-09-16. Where the repository contains plans but no code, the
> feature is marked **PLANNED / NOT CURRENTLY IMPLEMENTED**. Where code exists but is
> incomplete, it is marked **PARTIALLY IMPLEMENTED**. Secrets are `[REDACTED]`.

---

## 1. Project Overview

DASH is a **local-first personal AI assistant system** with three clients and one backend:

- **apps/backend** — Python FastAPI server holding all intelligence: LLM chat, tool execution,
  workflow automation, vision, security monitoring, self-healing, sync.
- **apps/desktop** — the primary UI: an **Electron + React 19 + TypeScript** desktop app.
- **apps/mobile** — a **native Android (Kotlin)** companion app (not Flutter — verified:
  `apps/mobile/app/src/main/java/com/example/...`, Gradle build, no `pubspec.yaml`).
- **apps/web** — a browser build of the desktop UI (vite `vite.config.web.ts`).

The personality contract ("Candor Core") is implemented in code
(`apps/backend/dash_backend/autonomous/candor.py`): deterministic pre-checks + hard refusal
gates + persona rules injected into every system prompt.

## 2. Problem Statement

Give one person a private, verifiable assistant that: chats via a local LLM, executes real
machine actions through a permissioned tool system, automates recurring work (cron/webhook/
event triggers), sees through a camera, watches its own health, repairs itself, and can be
driven remotely from a phone — **without claiming capabilities it does not have**. The candor
contract makes honesty an engineering requirement, not a vibe.

## 3. DASH Architecture (actual, verified)

```text
User
 ↓
Desktop UI (React 19 + Zustand + Electron)     Android app (Kotlin, native)
 ↓ lib/api.ts (authFetch, REST)                ↓ AppConfig.kt builds base URLs
 ↓ lib/wsClient.ts (WebSocket)                 ↓ ws://IP:PORT/api/v1/ws
 ↓                                             ↓
FastAPI backend (uvicorn, dash_backend/main.py)
 ↓ Auth: device token (security/local_identity.py) + JWT/refresh (auth/security.py)
 ↓ REST routers (api/routes/*, prefix /api/v1)   WebSocket (api/routes/websocket.py)
 ↓ Service layer (services/, workflow_builder.py engine, vision/, security/)
 ↓ Event bus (events/event_bus.py) — pub/sub between producers and consumers
 ↓ Tool system (tools/tool_manager.py → tool_executor.py → 30+ tool modules)
 ↓ LLM layer (llm/service.py → Ollama local; OpenAI/Gemini fallback)
 ↓ Data: SQLAlchemy async (SQLite local / Postgres) + JSON state files + Redis optional
 ↓ Supabase outbox sync (sync/supabase_outbox_worker.py) — one-way local→cloud
Responses flow back over the same sockets (chat.token, trigger.update, notification.push)
```

**Verified cross-cutting patterns**

- **Push + poll**: state changes broadcast over the existing `/api/v1/ws` socket
  (`services/trigger_push.py`, decision #80); a 5s poll remains the reconciliation fallback;
  the UI shows LIVE/STALE honestly (#76).
- **Event bus over direct calls**: reminders, file watcher, vision watcher and workflows
  communicate via topics (`file.changed`, `reminder.fired`, `vision.person_seen`).

## 4. Repository Structure (verified)

```
dash/
├── apps/
│   ├── backend/            FastAPI server (dash_backend/ package, 77 test files in tests/)
│   │   ├── dash_backend/   main.py, api/, auth/, security/, tools/, services/, events/,
│   │   │   vision/, llm/, chat/, rag/, sync/, autonomous/ (candor.py, brain.py),
│   │   │   agents/, monitoring/, db/ (models/), plugins/
│   │   ├── tests/          77 pytest files
│   │   ├── scripts/        fetch_vision_models.py, candor_live_probe_ws.py, ...
│   │   └── Dockerfile      Fly.io deployment (python:3.12-slim, multi-stage)
│   ├── desktop/            Electron+React UI (src/pages ≈ 50 pages, src/stores, src/lib)
│   ├── mobile/             Native Android Kotlin app (app/src/main/java/com/example/...)
│   └── web/                Browser build of the UI
├── docs/ROADMAP.md         Phase plan (0 Candor …)
├── decisions.md            85 numbered, dated engineering decisions
├── models/, scripts/, tools/
```

## 5. Technology Stack (all verified in package files)

| Layer | Technology | Evidence |
|---|---|---|
| Backend | Python 3.12, FastAPI ≥0.115, Pydantic v2, uvicorn | `apps/backend/pyproject.toml` |
| DB | SQLAlchemy 2 async, Alembic, aiosqlite (SQLite), asyncpg/psycopg (Postgres), Redis | pyproject deps |
| LLM | Ollama (llama3.2:1b default), OpenAI (gpt-4o-mini), Gemini fallback | `config.py` L97–130, `llm/cloud_fallback.py` |
| Desktop | React 19, TypeScript 5.8, Vite 6, Electron 35, Zustand 5, React Router 7, Tailwind 4, Three.js/@react-three/fiber (3D orb), Framer Motion, lucide-react | `apps/desktop/package.json` |
| Mobile | Kotlin, Android SDK (Gradle), Room (`DashDatabase.kt`), API services, wake-word/STT/TTS | `apps/mobile/.../com/example/...` |
| Vision | OpenCV, ONNX Runtime (YOLOv8n via ultralytics export), YuNet faces, SFace landmarks | `vision/camera_vision.py`, `recognition.py` |
| Monitoring | psutil, py-cpuinfo, mss | pyproject |
| Cloud | Supabase (optional outbox sync), Fly.io (Dockerfile), EC2 control routes | `sync/`, `Dockerfile`, `api/routes/ec2_control.py` |
| Tests | pytest 8 + pytest-asyncio (auto) + pytest-timeout; ruff/black/mypy | pyproject `[dev]` |
| **NOT USED** | ~~Flutter/Dart/Riverpod~~ (mobile is Kotlin), ~~Docker Compose~~, ~~CI/CD~~ | no pubspec.yaml; no compose; no `.github/workflows` |

## 6–7. Backend Architecture & FastAPI

**Entry point:** `apps/backend/dash_backend/main.py`

- `lifespan(app)` (L36) — startup/shutdown manager. **Startup verified:** workflow trigger
  scheduler `.start()` (L130–138), event bridge `.start()` (L156–157), enhanced sync
  service (L238–239); shutdown mirrors each with `.stop()` (L372–409).
- **CORS** (L462–478): explicit origins from `DASH_CORS_ORIGINS_RAW` plus, when
  `settings.cors_localhost_dev` (default on), any localhost/127.0.0.1 origin on any port is
  reflected so credentialed browser dev works (decision #75 — vite moves ports).
- **Routers** assembled in `api/router.py` (L50 import, L312 include, tag "enhanced"),
  mounted under `/api/v1`. Auth dependencies: `get_current_user` / `get_current_user_id`
  (`auth/dependencies.py`); `monitor.py` pins device-token auth at router level.

| Feature | Actual File | Class/Function | Purpose |
|---|---|---|---|
| App + lifespan | `dash_backend/main.py` | `lifespan`, `app` | start/stop schedulers, bridges, sync |
| CORS | `main.py` L462–478 | — | dev preflights + pinned prod origins |
| Router registry | `api/router.py` | — | mounts ~40 route modules under /api/v1 |
| Workflows REST | `api/routes/enhanced_features.py` | `APIRouter(prefix="/enhanced")` | workflow CRUD, triggers, executions |
| Health | `api/routes/health.py` | `/health`, `/health/ai-provider` | liveness + provider probe |
| Status | `api/routes/status.py` | `status_overview` | db/cloud/provider/system/services |
| Monitor/repair | `api/routes/monitor.py` | `/monitor/health`, `/monitor/repairs` | diagnostics + repair actions |
| WebSocket | `api/routes/websocket.py` | ws endpoint | auth, dispatch, push registration |
| Cloud relay | `api/routes/cloud_relay.py` | — | Android↔PC status, Wake-on-LAN, commands |
| Ollama proxy | `api/routes/ollama_proxy.py` | `/ollama` | Android→backend→Ollama; tunnel fallback |

**Request lifecycle:** uvicorn → CORSMiddleware → auth dependency → route handler (services
imported lazily inside handlers) → service layer → DB (`AsyncSessionLocal`) or JSON state →
response. Route-order rule: **literal paths declared before `/{param}` routes** (documented
in-code; pinned by tests).

## 8–10. Authentication & Tokens (the viva centerpiece)

DASH has **two independent auth systems**, both verified.

### A. Local device identity (primary for Desktop/WebSocket)

**File:** `dash_backend/security/local_identity.py`

**Token generation — `_create_identity()` (L108):**
```python
identity = DeviceIdentity(
    install_id=secrets.token_hex(16),        # 32 hex chars
    device_token=secrets.token_urlsafe(48),  # 64-char URL-safe opaque token
    created_at=datetime.now(timezone.utc).isoformat(), path=str(path))
```
- Python **`secrets` module** (CSPRNG); `token_urlsafe(48)` = 48 bytes entropy, base64url.
  **Not a JWT**: an opaque bearer token.
- **Storage:** JSON file (`version`, `install_id`, `device_token`, `created_at`) at
  `_identity_file_path()`; Windows ACL hardened (`_harden_windows_acl`, L82). Token stored
  plaintext in the file (ACL-mitigated); a `token_fingerprint` property (L60) allows safe
  logging. **Hashed before storage: no** (it IS the local root of trust).
- **Validation — `verify_device_token()` (L205):**
```python
expected = hmac.new(b"dash-device-token", identity.device_token.encode(), hashlib.sha256).hexdigest()
provided = hmac.new(b"dash-device-token", token.encode(), hashlib.sha256).hexdigest()
return hmac.compare_digest(expected, provided)
```
  HMAC-SHA256 of stored vs provided token, **constant-time compare** (timing-safe).
- **Expiration: none** (local trust anchor). **Revocation/rotation:**
  `rotate_device_token()` (L215) mints a new token, preserves `install_id`; clients must be
  re-provisioned. **Invalid token:** WS close **4401**; REST 401.
- **Extraction:** `extract_ws_token()` (L245) — `?token=` query param or `x-dash-token`.

### B. User JWT + refresh tokens (REST sessions)

**File:** `dash_backend/auth/security.py`

- `create_access_token(subject)` (L65): signed **JWT**, expiry
  `settings.access_token_expire_minutes`, returns `(token, expires_in)`.
- `decode_access_token()` (L80): splits 3 segments, verifies signature, checks `typ`,
  requires `sub`+`exp`, raises `InvalidTokenError("Expired token")` — explicit failure per case.
- `create_refresh_token()` (L114): `secrets.token_urlsafe(64)`; **hashed before storage**
  (`hash_refresh_token` L119) → `db/models/refresh_tokens.py`.
- Passwords: salted (`secrets.token_urlsafe(24)` salt, L25) + constant-time verify (L44).
- **DB models:** `db/models/user.py`, `device.py`, `session.py`, `refresh_tokens.py`, `api_key.py`.

**Who uses what:** Desktop/WebSocket/device-routes → (A); user REST sessions → (B) via
`get_current_user`; Android → same WS token path (stored encrypted via `SecurityManager.kt`).

## 11. Database

```text
Application → AsyncSessionLocal (db/session.py) → SQLAlchemy 2 async models
           → alembic migrations → SQLite (aiosqlite, local) or Postgres (asyncpg)
           → results mapped back to Pydantic/dicts
```

- **Session:** `db/session.py` (`AsyncSessionLocal`, `get_db_session`); base `db/base.py`,
  mixins `db/mixins.py`.
- **Models** (`db/models/`): `user`, `device`, `session`, `refresh_tokens`, `api_key`,
  `conversation`, `conversation_summary`, `message`, `memory`, `notification`, `plugin`,
  `task`. Conversations hold messages; `conversation_summary` powers the compaction the chat
  handler calls (`chat/service.py`: `needs_summary`, `save_conversation_summary`).
- **Workflow state is NOT in SQL**: `services/workflow_builder.py` persists custom workflows,
  triggers and history to a JSON state file (`_save_custom`) — dict-passthrough, so new
  fields survive restarts.
- **Migrations:** Alembic; psycopg for sync online migrations.

## 12–14. Chat Flow, LLM Architecture, Ollama (verified trace)

The **real chat path is a WebSocket**, not REST:

```text
Desktop wsClient / Android socket
  ↓ ws://…/api/v1/ws?token=DEVICE_TOKEN          (local_identity.py: extract_ws_token)
  ↓ verify_device_token() → else close 4401       (api/routes/websocket.py)
  ↓ parse_client_message() → ChatSendMessage      (api/websocket/protocol.py L98)
  ↓ handle_chat_send()                            (api/websocket/handlers.py, 1261 lines)
  ├─ history: chat/service.py (get_conversation_messages, needs_summary,
  │            save_conversation_summary)
  ├─ memory/RAG: context/engine.build_context_block; handlers _retrieve_rag_context
  ├─ CANDOR: compose_candor_system_prompt(final_base, msg.content)  (handlers L283–284;
  │     autonomous/candor.py: rules + assess_idea(); refusal_for() hard gate at
  │     autonomous/agent_core.py L242–243)
  ├─ build_chat_messages(system_prompt, history, user_message, memory_context, summary)
  ↓ llm/service.py provider abstraction
  ↓ Ollama HTTP (ollama_base_url=http://127.0.0.1:11434, ollama_model="llama3.2:1b")
  │     llm/cloud_fallback.py: latency-checked escalation → gemini when local is slow
  ↓ tool loop (MAX_TOOL_STEPS): ToolCallRequest → ToolManager → ToolExecutor
  ↓ stream: chat.token … chat.done (+ tool.confirmation_required when needed)
```

- **Voice mode:** `VOICE_SYSTEM_PROMPT` when `msg.voice_mode`; candor still composes over it.
- **Live-verified (#83):** malware → deterministic refusal verbatim; bad idea → expectation
  correction. Probe: `apps/backend/scripts/candor_live_probe_ws.py`.
- **Android REST chat:** `OllamaChatApi.kt` → backend `/ollama` proxy (PC on: local
  Ollama; PC off: EC2 + tunnel URL) — `ollama_proxy.py` docstring.

## 15–17. Tool Calling: Registry, Decision, Execution

- **Protocol:** OpenAI-style. `ToolSpec.to_openai_tool()` (base_tool.py L80);
  definitions via `ToolManager.get_tool_definitions()` (tool_manager.py L90) with relevance
  selection (`select_tool_definitions` L94, scoring L119).
- **Decision:** LLM emits a call → `ToolCallRequest.from_openai_tool_call()` (L41) →
  `ToolExecutor.execute()`.
- **Registry:** `tools/tool_registry.py`; **base:** `tools/base_tool.py` (`ToolSpec`,
  `ToolParameter`, `ToolContext`, `PermissionLevel` with rank comparisons).
- **Execution:** `tools/tool_executor.py` — `execute()` (L52) with `DEFAULT_TOOL_TIMEOUT`;
  sensitive tools → **CONFIRMATION_REQUIRED**: `confirmation_token = uuid.uuid4()` stored in
  `_pending_confirmations`, `ToolResult` status `PENDING_CONFIRMATION`, event
  `tool.confirmation_required` (tool_result.py L15–33). `execute_confirmed()` (L114)
  completes after approval; `reject_confirmation()` (L144) discards.
  `check_dangerous_command()` (L240) flags dangerous shell commands.
- **Result:** `ToolResult` (L39): status, output, error, summary, confirmation_token.

**Three real tools:** `WebSearchTool` (`tools/web_tools.py`; used live by `/monitor/research`);
self-code-edit (`tools/self_code_edit_tool.py`; test-gated, git checkpoints); terminal
(`tools/terminal_tool.py`; dangerous-command gate + confirmation). 30+ modules verified by
file listing (files, git, gmail, keyboard, mouse, windows, wifi, registry, OCR, browser…).

## 18. Approval System

Implemented as **tool-level confirmation** (not a separate approvals REST queue):

1. Sensitive tool → `execute()` returns `PENDING_CONFIRMATION` + uuid `confirmation_token`.
2. Backend sends `ToolConfirmationRequiredMessage` over the socket.
3. Client answers `tool.confirmed` / `tool.rejected` (protocol.py L136/L141).
4. `execute_confirmed(token)` resumes; `reject_confirmation()` returns an error ToolResult
   into the LLM loop.
5. Also present: `security/approval_dialog.py` (Windows-side prompts) and desktop
   `ApprovalsPage.tsx`.

## 19. WebSockets

- **Endpoint:** `/api/v1/ws` (`api/routes/websocket.py`). Auth: `extract_ws_token` +
  `verify_device_token`; failure = close **4401**. `_resolve_owner_user_id()` anchors data.
- **Handlers** (`api/websocket/handlers.py`): chat, agent.run, voice stt/tts, phone.*
  (state, clipboard, volume, flashlight, notifications, apps, media), desktop.* (mouse,
  keyboard, power) — dispatched via `parse_client_message()`.
- **Frames** (JSON, `type` literal): client→`chat.send`, `auth`, `ping`, `agent.run`,
  `tool.confirmed/rejected`, `voice.stt/tts`; server→`chat.token/done/error/status`,
  `tool.confirmation_required`, `notification.push`, `trigger.update`,
  `ai.provider.status`, `pong`, `system`.
- **Push registries:** notifications + triggers (`services/trigger_push.py`:
  `register_trigger_socket`, loop-marshalled `_schedule_send`, dead-socket pruning).

## 20. EventBus (implemented and load-bearing)

`dash_backend/events/event_bus.py` — `EventBus` (L185), `Event` (L147), `EventPriority`
(L26), `EventTopics` (L37), 100-entry history + cleanup.

- `subscribe(topic, callback, name)` L332 → sub_id; `unsubscribe` L374.
- `publish(Event)` L252 (async); `publish_sync(topic, data, source)` L292 for sync
  producers; `_deliver` L313 contains subscriber exceptions.
- **Real producers/consumers:** reminders (`reminder.fired`), file watcher
  (`DASH_WATCH_PATHS` → `file.changed`), vision watcher (`vision.person_seen`), workflow
  bridge (`services/workflow_event_bridge.py` → `engine.fire_event()`), workflow
  `_act_bus_publish` action.
## 21. Automation / Scheduler (workflow engine)

**File:** `dash_backend/services/workflow_builder.py` (single-file engine, ~1,400 lines)

- `WorkflowEngine` (L301): templates + custom workflows; **JSON state persistence**
  (`_save_custom`, `_load_schedules_and_webhooks` — dict-passthrough so new fields survive
  restarts). State file: `DASH_WORKFLOW_STATE` override, default
  `%LOCALAPPDATA%/DASH/workflow_state.json`.
- **Cron:** hand-written 5-field parser (`_parse_cron_field` L176, `parse_cron` L246) with a
  **strict dialect** — unsupported expressions are rejected, not silently mis-fired;
  `cron_matches_due()` (L261) evaluates in LOCAL wall time with standard DOM/DOW OR
  semantics; `next_cron_due()` (#81) shares the same field evaluator (`_fields_match`) so
  the System page's "next due" is exactly what the scheduler will do; impossible dates
  (Feb 30) return None rather than an invented time.
- **`WorkflowTriggerScheduler`** (~L1290): 60s poll loop, `tick(now)` fires due workflows
  via `asyncio.to_thread(engine.execute, wf, None, "scheduled")`, `mark_fired()` stamps
  **per-minute idempotence so a restart cannot double-fire**; `running` + `last_tick_at`
  expose real liveness (#81). Retries: none — failures are logged and stamped `failed`
  (honest, no silent retry).
- **Triggers:** schedules, webhooks (constant-time secret compare in `fire_webhook`; 409
  when paused), event triggers (`fire_event` skips disabled), manual runs. **Pause/resume
  (#79/#84):** `paused_since` stamp, `skipped_fires` ledger accrued inside
  `due_schedules()` itself (per-minute idempotent, pre-pause minutes excluded, kept on
  resume, reset on cron replace). **Pause-all (#85, backend complete):**
  `set_all_schedules_enabled()` delegates per-workflow, idempotent, reports `changed`.
- **Execution:** `_traverse()` — real graph walk; branch-tagged edges (if/else runs ONE
  branch); `MAX_TRAVERSAL_STEPS=200` raise (fails loudly, live-proven in #82); delay nodes
  sleep in a bounded pool (never the event loop); actions on a dedicated executor with
  timeouts; history records `source/status/duration_ms/nodes_executed/error`.
- **WS push:** `services/trigger_push.py` broadcasts `trigger.update` on every fire/pause
  (#80) — verified by sabotaging the client's fetch: the counter still moved over the
  socket alone.

## 22. Desktop Application (Electron + React — NOT Flutter)

- **Entry:** `apps/desktop/src/main.tsx` → `App.tsx` → React Router 7 (~50 pages: Chat,
  Automate with Rules/Builder/Triggers tabs, System Monitor, Command Center, Memory…).
- **State:** Zustand (`src/stores/` — aiStore, chatStore, uiStore, badgeStore…).
- **API client:** `src/lib/api.ts` — typed `request<T>()`, `authFetch` (device-token
  header), `workflowsApi`/`triggersApi` calling `/enhanced/workflows/...`.
- **WS client:** `src/lib/wsClient.ts` — `getDeviceToken()`, generic `on(type)` dispatch;
  the Triggers tab consumes `trigger.update` through it.
- **Live-loop pattern:** 5s silent poll + generation guard (stale responses dropped),
  LIVE/STALE honesty indicator, visibility-aware polling (#76–78, #82).
- **3D orb:** `src/three/`, `orb-main.tsx` (@react-three/fiber + postprocessing).
- **Electron:** electron-vite + vite-plugin-electron; `vite.config.web.ts` = browser build.

## 23–24. Android Application & Android ↔ PC (native Kotlin — NOT Flutter)

Verified under `apps/mobile/app/src/main/java/com/example/`:

- `DashApplication.kt` (entry) · `data/config/AppConfig.kt` — builds
  `http(s)://IP:PORT/api/v1/` and `ws(s)://IP:PORT/api/v1/ws` (L39–41); HTTPS→443;
  server restored from encrypted storage (`data/security/SecurityManager.kt`).
- `data/connection/DashForegroundService.kt` — foreground Service: wake-word start/stop,
  notification channel (keeps the assistant alive). `AutoConnectManager.kt`,
  `ConnectionStateManager.kt` — discovery + reconnect.
- `data/api/` — `DashApiService.kt`, `OllamaChatApi.kt`, `CloudRelayApi.kt`,
  `Ec2ControlApi.kt`. `data/local/` — Room (`DashDatabase.kt`, `dao/DashDao.kt`).
- `data/audio/` — `SttRecorder`, `TtsPlayer`, `WakeWordDetector` (voice loop).

**Command end-to-end (two verified paths):**
1. **LAN:** Android WS client → `desktop.mouse_click` / `desktop.power_shutdown` /
   `keyboard.*` frames → backend handlers (`api/websocket/handlers.py`) execute on the PC.
2. **Remote:** Android → `CloudRelayApi.kt` → `/api/v1/...cloud_relay` routes (docstring:
   PC status, **Wake-on-LAN**, command relay, companion registration; state in Supabase)
   → PC receives command when it comes online. Reverse direction: `phone.*` handlers let
   the PC control the phone (volume, clipboard, flashlight, media, notifications).

## 25. System Monitoring

- **Collection:** psutil + py-cpuinfo; `api/routes/status.py` (`_system_section` L172,
  `status_overview` L280) and `api/routes/monitor.py` (`/monitor/health` via
  `monitoring.get_diagnostics_service()`, `/monitor/repairs` via `get_repair_routine()` —
  the self-heal loop).
- **UI:** `SystemMonitorPage.tsx` 5s poll of `/health`, `/monitor/health`, and (since #81)
  `/enhanced/workflows/trigger-status` — resource cards, Service Health rows, the Workflow
  Triggers card (scheduler liveness, paused counts, next due).

## 26. Cloud / Supabase Sync (one-way local→cloud, verified)

- `sync/outbox.py` — outbox + `claim_dead_letter_events`.
- `sync/supabase_outbox_worker.py` — `deliver_once(limit=25)` (L39): re-arms due dead
  letters (hourly `next_retry_at`, **max 3 recoveries**, #43); deterministic errors stay
  dead-lettered; `run(poll_seconds=5.0)` (L76) with backoff when cloud unreachable.
- `sync/enhanced_service.py` started in lifespan (main.py L238).
- **Cloud→LOCAL: NOT FOUND in code** — do not claim bidirectional sync.
- LOCAL works fully offline: SQLite + JSON state + Ollama.

## 27. Networking / Tunnels / Deployment

- `api/routes/ollama_tunnel.py` + `set_tunnel_url()` in `ollama_proxy.py` — tunnel URL
  cache so Android/browser can reach Ollama when the PC backend is not on the LAN path.
- `AppConfig.kt` USE_HTTPS switch: remote 443 vs LAN 8000.
- **Docker:** `apps/backend/Dockerfile` (python:3.12-slim multi-stage, "Fly.io Deployment").
- **Cloudflare Tunnel: PLANNED / NOT FOUND as repository config.**
- **Docker Compose: NOT FOUND. CI/CD: NOT FOUND** (no `.github/workflows`).

## 28. Security — Implemented vs Could-Be-Added

**IMPLEMENTED (verified):**
- Device token: `secrets.token_urlsafe(48)` (CSPRNG), HMAC-SHA256 + `hmac.compare_digest`
  constant-time validation, Windows ACL hardening on the identity file
  (`_harden_windows_acl`), fingerprint-only logging, `rotate_device_token()`, WS close 4401.
- JWT: signature/exp/typ checks with explicit errors; refresh tokens hashed at rest
  (`hash_refresh_token`); salted passwords (`hash_password`, `secrets.token_urlsafe(24)` salt).
- Webhook secrets constant-time compared; paused webhooks return 409 (#79).
- Candor hard gate `refusal_for()` before executor dispatch (#65, live-proven #83).
- `security/input_sanitizer.py`, `security/path_guard.py` (traversal protection),
  `security/rate_limiter.py` (exists; not verified as applied to every route).
- Tool confirmation flow + `check_dangerous_command()`.
- CORS (#75): pinned prod origins + localhost-dev reflection.

**COULD BE ADDED (honest gaps):** no CI pipeline running tests on push; rate limiting not
verified on all routes; identity token plaintext in file (ACL-mitigated only); no mTLS on
the LAN; webhook secret brute-force throttling not observed.

## 29. Error Handling (actual patterns)

- Workflow routes return honest refusals: `200 {ok:false, reason}` — the UI renders the
  backend's reason verbatim (see `saveCron`/`setSchedulePaused` in AutomationPage).
- Best-effort pushes never break fire paths (`trigger_push.py` swallows + logs).
- Tool failures → `ToolResult` error/timeout classification; scheduler failures → logged +
  stamped `failed` (no silent retries).
- Event-bus `_deliver` contains subscriber exceptions.
- UI honesty: LIVE/STALE indicator, "could not reach the backend", real empty states.

## 30. Testing

- **77 backend test files** — pytest, `asyncio_mode="auto"`, pytest-timeout (hang → stack
  dump, #44). Highlights: `test_workflow_triggers.py` (cron dialect, double-fire
  idempotence, pause ledgers #84, pause-all #85, route-order pin), `test_trigger_push.py`
  (**real end-to-end WS test**: socket via `/api/v1/ws`, fire from another thread, assert
  `trigger.update` arrives), `test_websocket.py`, `test_security.py`, candor suites,
  vision tests with fake cv2 injected, self-heal tests with fake checks.
- **Frontend: no test runner** — convention is `tsc -b` + live preview verification
  (stated honestly, not hidden).
- Live-probe scripts: `scripts/candor_live_probe_ws.py`, vision smoke test.
## 31–32. Important Files & Functions (quick reference)

| Component | File | Class/Function | Purpose |
|---|---|---|---|
| App startup | `dash_backend/main.py` | `lifespan` | starts scheduler, event bridge, sync |
| Device token gen | `security/local_identity.py` | `_create_identity` | `secrets.token_urlsafe(48)` |
| Device token check | `security/local_identity.py` | `verify_device_token` | HMAC + `compare_digest` |
| JWT create/decode | `auth/security.py` | `create_access_token`, `decode_access_token` | signed session tokens |
| Refresh tokens | `auth/security.py` | `create_refresh_token`, `hash_refresh_token` | opaque, hashed at rest |
| WS auth | `api/routes/websocket.py` | ws endpoint + `WS_UNAUTHORIZED_CODE=4401` | socket gate |
| Chat handler | `api/websocket/handlers.py` | `handle_chat_send` | the whole chat pipeline |
| Candor | `autonomous/candor.py` | `assess_idea`, `refusal_for`, `compose_candor_system_prompt` | honesty layer |
| LLM providers | `llm/service.py`, `llm/cloud_fallback.py` | provider selection/fallback | Ollama ↔ cloud |
| Tool schema | `tools/base_tool.py` | `ToolSpec.to_openai_tool` | OpenAI-style tool format |
| Tool dispatch | `tools/tool_manager.py` | `ToolManager`, `ToolCallRequest.from_openai_tool_call` | registry + parsing |
| Tool run | `tools/tool_executor.py` | `execute`, `execute_confirmed`, `reject_confirmation` | approval flow |
| Workflow engine | `services/workflow_builder.py` | `WorkflowEngine`, `WorkflowTriggerScheduler`, `cron_matches_due`, `due_schedules`, `mark_fired` | automation core |
| Trigger push | `services/trigger_push.py` | `push_trigger_update`, `register_trigger_socket` | live WS updates |
| Event bus | `events/event_bus.py` | `EventBus.publish/publish_sync/subscribe` | pub/sub |
| Cloud sync | `sync/supabase_outbox_worker.py` | `deliver_once`, `run` | one-way outbox + dead letters |
| Monitoring | `api/routes/status.py`, `monitor.py` | `status_overview`, `/monitor/health` | system + self-heal |
| Desktop API | `apps/desktop/src/lib/api.ts` | `request`, `authFetch`, `triggersApi` | REST client |
| Desktop WS | `apps/desktop/src/lib/wsClient.ts` | `getDeviceToken`, `on(type)` | push consumer |
| Android config | `.../data/config/AppConfig.kt` | URL builders, `setServer` | endpoint resolution |
| Android service | `.../data/connection/DashForegroundService.kt` | wake-word service | keeps assistant alive |

## 33. Important Code Snippets (explained)

**1. Device token validation — `security/local_identity.py::verify_device_token` (L205)**
```python
if not token: return False
identity = get_identity()
expected = hmac.new(b"dash-device-token", identity.device_token.encode(), hashlib.sha256).hexdigest()
provided = hmac.new(b"dash-device-token", token.encode(), hashlib.sha256).hexdigest()
return hmac.compare_digest(expected, provided)
```
Line by line: empty tokens fail fast; `get_identity()` loads (and caches, under a lock) the
file identity; both stored and provided tokens are hashed with the same HMAC key so raw
secrets are never compared directly; `hmac.compare_digest` performs the equality check in
constant time, preventing timing side-channels. Exists because this token is the root of
trust for every local WS/REST call. Before: client presents token; after: handler runs.

**2. Token creation — `local_identity.py::_create_identity` (L108)** — see §8A. `secrets`
(CSPRNG) → 48-byte URL-safe token → JSON file → Windows ACL hardening. The frontend's
`wsClient.getDeviceToken()` reads this file's value to authenticate.

**3. Candor composition — `autonomous/candor.py::compose_candor_system_prompt`**
```python
parts = [base_prompt.rstrip(), CANDOR_RULES]
block = reality_block(assess_idea(user_message))
if block: parts.append(block)
return "\n\n".join(parts)
```
Every chat message gets: the base prompt, the persona contract, and (if deterministic
pre-checks matched) a `[CANDOR REVIEW …]` block the model may not skip. `refusal_for()` is
the harder sibling used before executor dispatch — live-proven to reach replies verbatim (#83).

**4. Scheduler fire idempotence — `workflow_builder.py::due_schedules` + `mark_fired`**
`due_schedules()` compares each schedule's `last_fired_at` minute against `now` and skips
already-fired minutes; `mark_fired(at=now)` stamps the evaluation time (not wall clock) so
fake-clock tests and restarts stay consistent. This is why a restart cannot double-fire.

**5. Tool confirmation — `tools/tool_executor.py::execute` (sensitive branch)**
mints `confirmation_token = uuid.uuid4()`, parks the request in `_pending_confirmations`,
returns `ToolResult(status=PENDING_CONFIRMATION, confirmation_token=…)`; the WS frame
`tool.confirmation_required` reaches the client; `execute_confirmed()` resumes,
`reject_confirmation()` cancels.

**6. Android URL build — `AppConfig.kt`**
```kotlin
val scheme = if (USE_HTTPS) "wss" else "ws"
return "$scheme://$SERVER_IP:$port/api/v1/ws"
```
HTTPS implies port 443 (tunnel/remote), otherwise LAN port 8000 — one switch flips the
whole app between remote and local operation.

## 34. End-to-End Request Traces

**Trace 1 — user asks a question (chat):**
`AutomationPage/ChatPage` input → `wsClient.send({type:"chat.send", message_id, content})`
→ backend ws auth (`verify_device_token`) → `handle_chat_send` (handlers.py) → history +
summary (`chat/service.py`) → RAG/memory context (`_retrieve_rag_context`,
`context/engine.build_context_block`) → `compose_candor_system_prompt` (L283) →
`llm/service.py` → Ollama `llama3.2:1b` → streamed `chat.token` frames → `chat.done` →
message persisted (conversations/messages tables) → UI renders.

**Trace 2 — user asks DASH to act (tool):**
same path until the LLM emits a tool call → `ToolCallRequest.from_openai_tool_call` →
`ToolExecutor.execute` → if sensitive: `tool.confirmation_required` frame → user clicks
Approve in the tool UI (`tool.confirmed`) → `execute_confirmed` runs the tool (timeout
guarded) → result frame → LLM continues → final `chat.done`. Rejection:
`reject_confirmation` → error ToolResult → LLM explains it did not run.

**Trace 3 — Android connects to DASH:**
app start (`DashApplication.kt`) → `AppConfig` resolves server (encrypted stored IP/port) →
`AutoConnectManager`/`ConnectionStateManager` reach `ws(s)://…/api/v1/ws?token=…` →
backend `verify_device_token` (same identity file) → registered for pushes →
`DashForegroundService` keeps wake-word listening (`WakeWordDetector` → `SttRecorder` →
`voice.stt` frames → `handle_voice_stt` → TTS back via `TtsPlayer`). Remote path: PC off →
`CloudRelayApi.kt` → EC2/Fly backend → Supabase-persisted relay state → Wake-on-LAN boots
the PC → PC comes online → commands flow.

**Trace 4 — scheduled automation:** `WorkflowTriggerScheduler._loop` tick (60s) →
`engine.due_schedules(now)` (local-time cron match, pause ledger updated for skipped
minutes) → `asyncio.to_thread(engine.execute, wf, None, "scheduled")` → `_traverse` runs
nodes → `mark_fired` idempotence stamp → history persisted → `trigger.update` WS push →
Triggers tab counter moves instantly (#80).

## 35. Implemented vs Planned (evidence-based)

| Feature | Status | Evidence |
|---|---|---|
| FastAPI backend, ~40 routers, /api/v1 | IMPLEMENTED | `main.py`, `api/router.py` |
| Device-token auth (CSPRNG, HMAC, ACL) | IMPLEMENTED | `local_identity.py` L108/L205/L82 |
| JWT + hashed refresh tokens | IMPLEMENTED | `auth/security.py`, `db/models/refresh_tokens.py` |
| WS chat with streaming + candor | IMPLEMENTED (live-proven #83) | `handlers.py`, `candor.py`, `scripts/candor_live_probe_ws.py` |
| Tool registry + executor + confirmation | IMPLEMENTED | `tools/*` (tool_manager, tool_executor, tool_result) |
| Workflow engine: cron/webhook/event/manual, pause+ledger, push | IMPLEMENTED (#53–#85) | `services/workflow_builder.py`, `trigger_push.py` |
| Vision (OpenCV, YuNet, SFace, ONNX YOLO) | IMPLEMENTED | `vision/camera_vision.py`, `recognition.py`, `scripts/fetch_vision_models.py` |
| Guardian security monitoring | IMPLEMENTED | `security/guardian.py` |
| Self-heal loop + self-code-edit w/ git checkpoints | IMPLEMENTED | `monitoring/`, `tools/self_code_edit_tool.py`, `self_heal.py` |
| System monitoring UI | IMPLEMENTED | `status.py`, `SystemMonitorPage.tsx` |
| Supabase one-way outbox sync + dead letters | IMPLEMENTED | `sync/*` (#43) |
| Cloud relay / Wake-on-LAN (Android↔PC remote) | IMPLEMENTED (routes verified) | `api/routes/cloud_relay.py`, `CloudRelayApi.kt` |
| Flutter/Riverpod mobile | **NOT FOUND — mobile is native Kotlin** | no pubspec.yaml; Kotlin tree |
| Cloudflare Tunnel config | PLANNED / NOT FOUND (tunnel URL mechanism exists) | `ollama_tunnel.py` |
| Docker Compose / CI-CD pipelines | NOT FOUND | repo sweep |
| Voice (backend STT/TTS handlers; Android audio) | PARTIALLY VERIFIED (handlers + Kotlin classes exist; end-to-end quality unproven) | `handlers.py`, `data/audio/` |
| "Custom OS" (full OS replacement) | PLANNED / NOT CURRENTLY IMPLEMENTED | roadmap aspiration only |

## 36. Technology "Why" Answers

- **FastAPI** — async-native (needed for WS + many concurrent streams), Pydantic
  validation, dependency injection for auth; alternative Flask lacks native async/WS typing.
- **Ollama local-first** — privacy + offline; `cloud_fallback.py` adds cloud only when local
  is measurably slow; alternative pure-cloud loses privacy and works offline never.
- **WebSocket for chat** — token streaming + tool confirmation + pushes need bidirectional
  low-latency; REST polling cannot stream tokens; REST retained for CRUD.
- **SQLAlchemy async + SQLite/Postgres** — zero-config local (aiosqlite), upgrade path to
  Postgres (asyncpg) with the same models; Alembic for migrations.
- **JSON state file for workflows** — the engine's triggers are small, single-writer, and
  must survive restarts atomically per save; simpler than SQL for this shape.
- **Electron + React** — reuse of one web codebase for desktop + web build
  (`vite.config.web.ts`); alternative Flutter desktop would fragment the UI codebase.
- **Kotlin for Android** — native foreground services, wake-word audio, Room caching;
  alternatives (Flutter/RN) complicate service + audio pipelines.
- **Zustand** — minimal store boilerplate vs Redux for a single-developer codebase.
- **Supabase outbox** — decouples local writes from cloud availability; dead-letter +
  backoff (#43) makes flaky networks safe.
- **`secrets` + HMAC constant-time compare** — CSPRNG entropy and timing-attack resistance
  are the difference between a toy token and a real one.

## 37–39. Viva Questions, Model Answers, Cross-Questions

**L1 (basics) — short answers:** What is FastAPI? (async Python web framework with type-
driven validation.) REST vs WebSocket? (request/response vs persistent bidirectional
frames — DASH uses both deliberately.) What is a JWT? (signed token with
header.payload.signature; DASH uses it for user sessions, but NOT for the device token.)
What is SQLAlchemy? (ORM/query toolkit; here in async mode.)

**L2 (DASH-specific) with code references:**

1. *Where does DASH start?* → `dash_backend/main.py::lifespan` — starts the trigger
   scheduler, event bridge, sync service.
2. *What happens when the user sends a message?* → Trace 1; end at `chat.done`.
3. *Where is the chat endpoint?* → **WS** `/api/v1/ws` (`handle_chat_send`); REST proxy
   `/ollama` exists for Android.
4. *How is the token generated?* → `secrets.token_urlsafe(48)` in `_create_identity`.
5. *Where is it stored?* → identity JSON file, ACL-hardened on Windows; desktop client
   reads it via `wsClient.getDeviceToken()`.
6. *How is it validated?* → `verify_device_token` — HMAC-SHA256 both sides +
   `compare_digest`; failure = WS close 4401.
7. *How does DASH call Ollama?* → `llm/service.py` to `ollama_base_url:11434`, model
   `llama3.2:1b`; fallback via `cloud_fallback.py`.
8. *How does DASH execute a tool?* → `ToolCallRequest` → `ToolExecutor.execute` →
   `ToolResult` (+ confirmation branch).
9. *How does approval work?* → §18 five-step flow.
10. *Why can't a restart double-fire a schedule?* → `last_fired_at` minute-stamp guard in
    `due_schedules` + `mark_fired(at=now)` persistence.

**L3 (code-level):** Why is `handle_chat_send` async? (streaming + DB + tool awaits on one
event loop; blocking tool work is pushed to executors/threads.) Why is the workflow engine
not a DB table? (single-writer JSON state with dict-passthrough persistence — see §11.)
What if the LLM times out? (provider health monitor + cloud fallback; tool calls have
`DEFAULT_TOOL_TIMEOUT`.) What if a tool throws? (ToolResult error, run continues; candor
hard-gates refuse dangerous classes before the LLM even runs.) Why literal routes before
`/{param}`? (FastAPI matches in declaration order — otherwise "trigger-status" would 422 as
a workflow_id; pinned by test.) Why `asyncio.to_thread` in the scheduler? (delay nodes and
tools must never block the loop that serves WS clients.)

**Examiner cross-questions (Why → How → Show me → What if → Why this way?):**

- "Why an opaque device token instead of JWT?" → Root-of-trust lives on one machine;
  opaque + HMAC-compare avoids signature-key management; rotation is a file rewrite.
  Show `_create_identity`/`verify_device_token`. If the file leaks → attacker has access
  until `rotate_device_token()`; mitigation is the ACL hardening.
- "Why WebSocket for triggers instead of SSE?" → Two-way: the same socket already carries
  chat; `trigger.update` needed no new endpoint; the 5s poll is the reconciliation layer,
  so push loss is survivable. Show `trigger_push.py` + the fetch-sabotage live proof (#80).
- "What if Ollama is down?" → `cloud_fallback.py` latency check escalates to Gemini;
  `ai.provider.status` frames surface provider state in the UI.
- "Why is the skipped-fires ledger kept after resume?" → It answers "what did pausing
  cost me?" — a historical fact; clearing it would rewrite history (#84).

## 40. "Show Me the Code" Quick Reference

| Examiner asks | Open this file | Show this |
|---|---|---|
| Token generation | `dash_backend/security/local_identity.py` | `_create_identity` |
| Token validation | same | `verify_device_token` |
| Token rotation | same | `rotate_device_token` |
| JWT session tokens | `dash_backend/auth/security.py` | `create_access_token`, `decode_access_token` |
| Chat endpoint | `dash_backend/api/websocket/handlers.py` | `handle_chat_send` |
| Candor/honesty | `dash_backend/autonomous/candor.py` | `assess_idea`, `refusal_for`, `compose_candor_system_prompt` |
| LLM call/fallback | `dash_backend/llm/service.py`, `llm/cloud_fallback.py` | provider selection |
| Tool registry | `dash_backend/tools/tool_manager.py`, `base_tool.py` | `ToolManager.get_tool_definitions`, `ToolSpec.to_openai_tool` |
| Tool execution/approval | `dash_backend/tools/tool_executor.py` | `execute`, `execute_confirmed` |
| WebSocket endpoint | `dash_backend/api/routes/websocket.py` | ws handler, close 4401 |
| Scheduler | `dash_backend/services/workflow_builder.py` | `WorkflowTriggerScheduler.tick`, `due_schedules`, `mark_fired` |
| Pause ledger | same | `set_schedule_enabled`, `due_schedules` skip accounting |
| DB session | `dash_backend/db/session.py` | `AsyncSessionLocal`, `get_db_session` |
| Outbox sync | `dash_backend/sync/supabase_outbox_worker.py` | `deliver_once`, dead-letter re-arm |
| System monitoring | `dash_backend/api/routes/status.py` | `_system_section`, `status_overview` |
| Android connection | `apps/mobile/.../data/config/AppConfig.kt` | URL builders |
| Android service | `.../data/connection/DashForegroundService.kt` | wake-word service |
| Desktop API client | `apps/desktop/src/lib/api.ts` | `request`, `authFetch`, `triggersApi` |
| Desktop WS client | `apps/desktop/src/lib/wsClient.ts` | `getDeviceToken`, `on()` |
| Startup | `dash_backend/main.py` | `lifespan` |

## 41. Final 5-Minute Revision Sheet

**DASH in one sentence:** a local-first AI assistant system — FastAPI brain, Electron/React
desktop, native-Kotlin Android companion — that chats over Ollama, executes permissioned
tools, runs a cron/webhook/event workflow engine, and tells the truth by construction.

**Architecture in 30s:** clients → `/api/v1` REST + `/api/v1/ws` → device-token auth →
routers → services → SQLAlchemy/JSON state; event bus links producers (vision, reminders,
file watcher) to consumers (workflows, notifications); outbox pushes local data to Supabase.

**Chat request in 30s:** `chat.send` frame → auth → history/summary + RAG context → candor
prompt composition → Ollama stream → `chat.token`s → tool loop if needed → `chat.done`,
message persisted.

**Authentication in 30s:** two systems — device token (opaque, HMAC constant-time, WS 4401)
and user JWT + hashed refresh tokens; Android reuses the device-token path with encrypted
local storage.

**Token generation in 30s:** `secrets.token_urlsafe(48)` at identity creation, JSON file +
ACL hardening, fingerprint-only logging, `rotate_device_token()` for revocation.

**LLM flow in 30s:** candor-composed system prompt + history + memory → provider selection
(local Ollama vs Gemini fallback) → streamed tokens → tool-call loop bounded by
MAX_TOOL_STEPS.

**Tool calling in 30s:** OpenAI-style schemas from `ToolSpec`; LLM emits a call; executor
runs with timeout; sensitive tools park as PENDING_CONFIRMATION until `tool.confirmed`.

**WebSocket in 30s:** one socket carries chat streaming, confirmations, notification.push,
trigger.update; registries are best-effort; the 5s poll reconciles; LIVE/STALE tells the
truth about the poll feed.

**Android connection in 30s:** AppConfig builds ws URL → device token → foreground service
keeps wake-word alive → voice frames → backend; remote control goes through cloud relay +
Wake-on-LAN.

**Database in 30s:** async SQLAlchemy, SQLite locally / Postgres in the cloud deployment;
conversations, messages, summaries, users, devices, refresh tokens; workflow state is a
JSON file, not SQL.

**Most important 20 files:** main.py; api/router.py; api/routes/websocket.py;
api/websocket/handlers.py; api/websocket/protocol.py; api/routes/enhanced_features.py;
security/local_identity.py; auth/security.py; auth/dependencies.py; db/session.py;
db/models/conversation.py; autonomous/candor.py; llm/service.py; llm/cloud_fallback.py;
tools/tool_manager.py; tools/tool_executor.py; tools/base_tool.py;
services/workflow_builder.py; services/trigger_push.py; events/event_bus.py.

**Most important 20 functions/classes:** `lifespan`; `handle_chat_send`;
`compose_candor_system_prompt`; `assess_idea`; `refusal_for`; `verify_device_token`;
`_create_identity`; `rotate_device_token`; `create_access_token`; `decode_access_token`;
`ToolExecutor.execute`; `execute_confirmed`; `ToolSpec.to_openai_tool`;
`ToolCallRequest.from_openai_tool_call`; `WorkflowEngine.execute`; `_traverse`;
`due_schedules`; `mark_fired`; `EventBus.publish_sync`; `SupabaseOutboxWorker.deliver_once`.

**30 questions to absolutely know:** (1) entry point; (2) two auth systems and where each
is used; (3) token generation function + entropy; (4) constant-time compare; (5) WS close
code on bad auth; (6) chat frame names; (7) candor layers (deterministic vs model);
(8) live-probe result for malware vs bad idea; (9) Ollama model + fallback; (10) tool
protocol format; (11) confirmation flow states; (12) dangerous-command gate; (13) trigger
types (4) + their auth; (14) cron dialect strictness; (15) restart double-fire prevention;
(16) pause ledger semantics (#84); (17) pause-all idempotence (#85); (18) trigger push vs
poll + LIVE/STALE; (19) event bus topics in production; (20) workflow state persistence
shape; (21) DB engines + switch; (22) refresh-token hashing; (23) outbox dead letters +
retry cap; (24) Wake-on-LAN path; (25) phone.* vs desktop.* handler directions; (26)
monitoring endpoints + UI cadence; (27) Docker/deployment target + what is NOT configured
(compose, CI, Cloudflare); (28) frontend test convention (tsc + live preview, no runner);
(29) backend test count + hang protection; (30) honest gaps list (§35).

---

*Generated 2026-09-16 from repository inspection; decisions.md #53–#85 record the
per-change engineering history. Secrets redacted.*
