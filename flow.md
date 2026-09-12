# DASH — Execution Flow & Code Path Documentation

How execution travels between files, functions, and modules. What calls what, in what order, and exactly which parts were modified in this session.

---

## Table of Contents

1. [Backend Entry Point & Startup](#1-backend-entry-point--startup)
2. [API Request Lifecycle](#2-api-request-lifecycle)
3. [Proactive Suggestions Flow](#3-proactive-suggestions-flow)
4. [Predictive Risk Detection Flow](#4-predictive-risk-detection-flow)
5. [Predictive→Proactive Integration Flow](#5-predictiveproactive-integration-flow)
6. [Daily Briefing Flow](#6-daily-briefing-flow)
7. [End-of-Day Summary Flow](#7-end-of-day-summary-flow)
8. [Device Sampling Flow](#8-device-sampling-flow)
9. [Memory Extraction Flow](#9-memory-extraction-flow)
10. [Typed Memory & Decision Flow](#10-typed-memory--decision-flow)
11. [Session Lifecycle Flow](#11-session-lifecycle-flow)
12. [Legal Documents Flow](#12-legal-documents-flow)
13. [Desktop App Boot & Routing](#13-desktop-app-boot--routing)
14. [Command Center Data Flow](#14-command-center-data-flow)
15. [Sidebar Badge Flow](#15-sidebar-badge-flow)
16. [WebSocket Communication Flow](#16-websocket-communication-flow)

---

## 1. Backend Entry Point & Startup

```
uvicorn dash_backend.main:app
  └─ FastAPI app created in main.py
       └─ lifespan() context manager runs on startup:
            1. Alembic migrations (upgrade head)
            2. Supabase outbox worker (optional)
            3. Device identity (security/local_identity.py)
            4. Skills + desktop tools registration
            5. Permission manager init
            6. Executive worker (executive/service.py worker_loop)
            7. Automation scheduler start
            8. Event Bus start
            9. System services (scheduler, health monitor, metrics, resource manager)
           10. Device sampler start (predictive/sampler.py)
           11. Memory engine init (memory/service.py)
           12. Context engine init (context/engine.py)
```

**Modified in this session:** Device sampler startup (step 10) — added during Predictive Detection milestone.

---

## 2. API Request Lifecycle

```
Client request
  └─ FastAPI middleware (CORS, auth)
       └─ api/router.py routes to sub-router by prefix
            ├─ /auth/*          → auth router
            ├─ /proactive/*     → proactive router
            ├─ /predictive/*    → predictive router
            ├─ /executive/*     → executive router
            ├─ /memory/*        → memory router
            ├─ /security/*      → security router
            ├─ /legal/*         → legal router
            ├─ /privacy/*       → privacy router
            ├─ /context/*       → context router
            └─ ... (25+ routers)
       └─ Dependencies inject: get_current_user_id, get_db_session
       └─ Route handler executes
       └─ Response returned
```

**Modified in this session:** Added proactive, predictive, executive, security, privacy, and legal routers to `api/router.py`.

---

## 3. Proactive Suggestions Flow

This is the core flow that powers the Command Center "Attention Required" panel.

```
GET /proactive/suggestions?limit=5
  └─ proactive.py::get_suggestions()
       └─ get_proactive_engine()  [singleton]
       └─ ProactiveEngine.evaluate(session, user_id, limit)
            │
            ├─ 1. load_config() → reads proactive_config.json (or DEFAULT_CONFIG)
            ├─ 2. Check: enabled? → return [] if not
            ├─ 3. Check: in_quiet_hours()? → return [] if yes
            │
            ├─ 4. context_engine.snapshot_async()
            │      └─ ContextEngine.snapshot_async()
            │           ├─ device() → psutil CPU/RAM/disk/network
            │           ├─ project() → git status, branch, modified files
            │           └─ activity() → DB query: goals, tasks, conversations
            │           └─ Returns EnvironmentContext dataclass
            │
            ├─ 5. detect_signals(snap)  [signals.py]
            │      ├─ _system_health_signals(snap) → high CPU, low disk, etc.
            │      ├─ _project_signals(snap) → uncommitted work, stale branches
            │      ├─ _deadline_signals(snap) → upcoming/overdue tasks
            │      └─ _goal_signals(snap) → stuck/overdue goals
            │      └─ Returns List[Signal], sorted by importance desc
            │
            ├─ 6. For each signal:
            │      ├─ Skip if importance < threshold (0.55)
            │      ├─ Skip if already seen (dedup)
            │      ├─ Skip if within cooldown (120 min)
            │      └─ Append to results
            │
            ├─ 7. If len(results) < limit:
            │      └─ _append_predictive_suggestions()  ← MODIFIED THIS SESSION
            │           ├─ get_predictive_engine() → singleton
            │           ├─ PredictiveEngine.analyze()
            │           │    └─ (see Flow #4 below)
            │           ├─ For each prediction:
            │           │    ├─ Map severity → importance (high=0.8, warning=0.65, info=0.45)
            │           │    ├─ Skip if importance < threshold
            │           │    ├─ Skip if cooldown active
            │           │    └─ Append to results
            │           └─ Return results (proactive + predictive mixed)
            │
            └─ Return results list
```

**Modified in this session:** Steps 7 (predictive integration) — `_append_predictive_suggestions()` was added to `engine.py`. Severity mapping, threshold gating, cooldown, and slot-filling logic all new.

---

## 4. Predictive Risk Detection Flow

```
GET /predictive/risks
  └─ predictive.py::get_risks()
       └─ get_predictive_engine()  [singleton]
       └─ PredictiveEngine.analyze(session, user_id)
            │
            ├─ 1. context_engine.snapshot_async() → EnvironmentContext
            │
            ├─ 2. _device_predictions(snap)  [device trends]
            │      ├─ store.get_history() → reads predictive_samples.json
            │      ├─ If < 5 samples: return []
            │      ├─ numpy polyfit(disk) → linear trend + R²
            │      ├─ numpy polyfit(ram) → linear trend + R²
            │      ├─ If slope significant and R² > 0.5:
            │      │    └─ Create Prediction(severity, likelihood, horizon, evidence)
            │      └─ Return list of predictions
            │
            ├─ 3. _project_predictions(snap)  [git activity]
            │      ├─ Count stale branches (>7 days)
            │      ├─ Count modified files
            │      ├─ If stale branches > 10 or modified > 20:
            │      │    └─ Create Prediction
            │      └─ Return list of predictions
            │
            ├─ 4. _goal_predictions(session, user_id)  [DB query]
            │      ├─ Query goals with deadlines within 7 days
            │      ├─ If overdue goals found:
            │      │    └─ Create Prediction(severity="high")
            │      └─ Return prediction or None
            │
            └─ Return { predictions: [...], analyzed_at, summary }
```

**Modified in this session:** Not directly modified — the engine existed before. But it's called by the new `_append_predictive_suggestions()` in the proactive engine.

---

## 5. Predictive→Proactive Integration Flow

This is the new flow added this session — where predictive risks get appended to proactive suggestions.

```
ProactiveEngine.evaluate() (see Flow #3)
  └─ After proactive signals are collected:
       └─ _append_predictive_suggestions(results, seen, threshold, cooldown_s, now, limit)
            │
            ├─ 1. get_predictive_engine() → singleton (or self._predictive_engine if injected)
            ├─ 2. engine.analyze(session, user_id) → { predictions: [...] }
            │      └─ (see Flow #4)
            │
            ├─ 3. For each prediction:
            │      ├─ stable_id = f"predictive_{pred.id}"  (prefix for independent cooldown)
            │      ├─ Skip if stable_id in seen set
            │      ├─ importance = SEVERITY_TO_IMPORTANCE[severity]
            │      │    high → 0.80
            │      │    warning → 0.65
            │      │    info → 0.45
            │      ├─ Skip if importance < threshold
            │      ├─ Skip if last_shown within cooldown
            │      ├─ Add stable_id to seen
            │      ├─ Format payload: severity, likelihood, horizon, action, evidence
            │      └─ Append to results
            │
            └─ Return merged results list
```

**This entire flow was added in this session.** Files modified:
- `dash_backend/proactive/engine.py` — `_append_predictive_suggestions()`, `SEVERITY_TO_IMPORTANCE` map
- `dash_backend/proactive/briefing.py` — `_extract_top_risk()`, updated `build_briefing()` and `format_briefing()`

---

## 6. Daily Briefing Flow

```
GET /proactive/briefing
  └─ proactive.py::get_briefing()
       └─ build_briefing(session, user_id)  [briefing.py]
            │
            ├─ 1. context_engine.snapshot_async() → EnvironmentContext
            │      ├─ device() → CPU/RAM/disk
            │      ├─ project() → git info
            │      └─ activity() → goals, tasks, conversations
            │
            ├─ 2. _device_line(snap) → "CPU 45% | RAM 86% | Disk 81%"
            ├─ 3. _project_line(snap) → "dash (branch) - N modified file(s)"
            ├─ 4. _goals_lines(activity) → "Completed: N, Pending: N"
            ├─ 5. _deadline_lines(activity) → "Due today: ..., Overdue: ..."
            │
            ├─ 6. _trend_lines(store)  ← MODIFIED THIS SESSION
            │      └─ DeviceSampler store → numpy polyfit → trend lines
            │
            ├─ 7. _prediction_lines(session, user_id)  ← MODIFIED THIS SESSION
            │      └─ PredictiveEngine.analyze() → top 5 risks formatted
            │
            ├─ 8. detect_signals(snap) → proactive signals
            │
            ├─ 9. attention = top 5 signals (by importance)
            │
            ├─ 10. _extract_top_risk(attention)  ← MODIFIED THIS SESSION
            │       └─ Find predictive_* entries in attention → highest importance
            │
            └─ Return sections dict: device, project, goals, deadlines, trends, top_risk, attention

       └─ format_briefing(sections)  ← MODIFIED THIS SESSION
            ├─ "Briefing for {day}:"
            ├─ "System: {device_line}"
            ├─ "Project: {project_line}"
            ├─ "Goals: {goals_lines}"
            ├─ "Deadlines: {deadline_lines}"
            ├─ "Device trends: {trend_lines}"  ← NEW
            ├─ "Top risk: [{severity}] {title} ({horizon})"  ← NEW
            └─ "Attention: {attention_items}"  (expanded to 5 items)
```

**Modified in this session:** Steps 6, 7, 9-10, and `format_briefing()`. Added trend lines, prediction lines, top risk extraction, and the "Top risk:" section in formatted output.

---

## 7. End-of-Day Summary Flow

```
GET /proactive/summary
  └─ proactive.py::get_summary()
       └─ build_end_of_day(session, user_id)  [briefing.py]
            │
            ├─ 1. Query completed goals (last 24h)
            ├─ 2. Query completed tasks (last 24h)
            ├─ 3. Query recent conversations
            ├─ 4. Git commits (last 24h)
            │
            ├─ 5. _trend_lines(store)  ← MODIFIED THIS SESSION
            │       └─ Same trend analysis as briefing
            │
            └─ Return summary dict

       └─ format_end_of_day(summary)  ← MODIFIED THIS SESSION
            ├─ "End-of-day summary (last 24 hours):"
            ├─ "Completed: {N} goal(s), {N} task(s)."
            ├─ "Commits: {commit_list}"
            └─ "Device trends: {trend_lines}"  ← NEW
```

**Modified in this session:** Steps 5 and `format_end_of_day()` — added device trend lines from SampleStore.

---

## 8. Device Sampling Flow

```
App lifespan startup
  └─ start_device_sampler()  [sampler.py]
       └─ asyncio.create_task(DeviceSampler.run())
            └─ Loop every 300s (5 min):
                 ├─ _collect_sample()
                 │    ├─ psutil.cpu_percent()
                 │    ├─ psutil.virtual_memory()
                 │    ├─ psutil.disk_usage("/")
                 │    └─ Return dict with timestamp
                 │
                 ├─ store.append(sample)  → predictive_samples.json
                 │    └─ Prune if > 7 days or > 2 MB
                 │
                 └─ sleep(interval)

  └─ Used by:
       ├─ PredictiveEngine._device_predictions() → trend analysis
       ├─ briefing._trend_lines() → briefing trend display
       └─ CommandCenterPage (indirectly, via /predictive/risks)
```

**Modified in this session:** Not directly modified, but its output is now consumed by the briefing trend lines and predictive-proactive integration.

---

## 9. Memory Extraction Flow

```
POST /conversations/{id}/messages  (or auto-extract on conversation end)
  └─ memory/service.py::extract_memories_from_conversation()
       │
       ├─ 1. Iterate messages (user role only)
       ├─ 2. For each message, check against preference_indicators:
       │      "my name is", "i like", "i prefer", "my goal", etc.
       │
       ├─ 3. If indicator found:
       │      ├─ Split into sentences
       │      ├─ Score importance (0.45 base + keyword bonuses)
       │      ├─ Determine type (Fact, Preference, Goal)
       │      └─ save_memory(content, source="conversation", ...)
       │           ├─ Compute embedding (nomic-embed-text via Ollama)
       │           ├─ Duplicate check (cosine similarity > 0.92)
       │           ├─ Insert into Memory table
       │           └─ Prune if > 500 per user
       │
       └─ Return list of new memories
```

**Modified in this session:** Not directly modified. But the Memory model was extended with `confidence` and `project_id` columns.

---

## 10. Typed Memory & Decision Flow

### Remember This Decision

```
POST /memory/decision
  └─ memory_routes.py::remember_decision()
       └─ memory/service.py::remember_decision(session, user_id, decision, rationale, alternatives, project_id)
            │
            ├─ content = f"Decision: {decision}. Rationale: {rationale}. Alternatives considered: {alternatives}."
            └─ save_typed_memory(session, user_id, content, memory_type="decision", ...)
                 └─ save_memory(content, memory_type="decision", category="Decision", importance=0.7, ...)
```

### Continue Where We Left Off

```
POST /memory/work-context
  └─ memory_routes.py::record_work_context()
       └─ memory/service.py::record_work_context(session, user_id, task, progress, blockers, next_steps)
            │
            ├─ content = f"Working on: {task}. Progress: {progress}. Blockers: {blockers}. Next steps: {next_steps}."
            └─ save_typed_memory(session, user_id, content, memory_type="experience", ...)

GET /memory/continue?project_id=...
  └─ memory_routes.py::get_continue_context()
       └─ memory/service.py::get_continue_context(session, user_id, project_id)
            └─ Query Memory WHERE content LIKE '%Working on:%' ORDER BY created_at DESC LIMIT 5
```

**Added in this session:** `remember_decision()`, `record_work_context()`, `get_continue_context()`, `save_typed_memory()`, and the `confidence`/`project_id` columns on the Memory model.

---

## 11. Session Lifecycle Flow

### Session Creation (on login/register/refresh)

```
POST /auth/register or POST /auth/login or POST /auth/refresh
  └─ auth/service.py::issue_token_response()
       ├─ 1. Create/validate User record
       ├─ 2. Generate refresh token (secrets.token_urlsafe)
       ├─ 3. Hash refresh token (sha256)
       ├─ 4. Create Session record:
       │      user_id, refresh_token_hash, device_info,
       │      ip_address, user_agent, created_at, expires_at
       ├─ 5. Create JWT access token
       └─ 6. Return { access_token, refresh_token, session_id }
```

### Session Listing

```
GET /security/sessions
  └─ security.py::list_sessions()
       └─ session_service.list_user_sessions(user_id)
            └─ Query Session WHERE user_id=? AND revoked_at IS NULL AND expires_at > now()
```

### Session Revocation

```
POST /security/sessions/{session_id}/revoke
  └─ security.py::revoke_session_endpoint()
       └─ session_service.revoke_session(session_id, user_id)
            └─ UPDATE Session SET revoked_at=now() WHERE id=? AND user_id=?

POST /security/sessions/revoke-all
  └─ security.py::revoke_all_sessions_endpoint()
       └─ session_service.revoke_all_sessions(user_id)
            └─ UPDATE Session SET revoked_at=now() WHERE user_id=? AND revoked_at IS NULL
```

**Added in this session:** All session lifecycle endpoints and service methods.

---

## 12. Legal Documents Flow

```
GET /legal/
  └─ legal.py::legal_index()
       └─ Return { documents: ["privacy", "terms", "accessibility"], version }

GET /legal/privacy
  └─ legal.py::privacy_policy()
       └─ Return { content: PRIVACY_POLICY, version, effective_date }

GET /legal/terms
  └─ legal.py::terms_and_conditions()
       └─ Return { content: TERMS_AND_CONDITIONS, version, effective_date }

GET /legal/accessibility
  └─ legal.py::accessibility_statement()
       └─ Return { content: ACCESSIBILITY_STATEMENT, version, effective_date }
```

**No authentication required** — these are public documents.

**Modified in this session:** Privacy Policy content (section 3.1 accuracy fix, section 7.3 font disclosure).

---

## 13. Desktop App Boot & Routing

```
Electron main process
  └─ Loads React app in BrowserWindow
       └─ App.tsx (root component)
            │
            ├─ 1. Boot screen (BootScreen.tsx) → 5s animation
            │      └─ Orbitron font, particles, ring animation
            │      └─ role="status" aria-label="DASH loading"
            │
            ├─ 2. Main layout:
            │      ├─ TitleBar (custom frameless)
            │      ├─ DASHSidebar (navigation)
            │      └─ <Routes> (page content)
            │
            ├─ 3. useEffect on mount:
            │      ├─ startSystemStatsPolling(5000)  → aiStore
            │      └─ startBadgePolling(60000)  ← ADDED THIS SESSION
            │
            └─ 4. Routes (HashRouter):
                  ├─ /              → CommandCenterPage  ← ADDED THIS SESSION (was HomePage)
                  ├─ /orb           → HomePage (old orb view)
                  ├─ /chat          → ChatPage
                  ├─ /voice         → VoicePage
                  ├─ /memory        → MemoryPage
                  ├─ /knowledge     → KnowledgePage
                  ├─ /obsidian      → ObsidianPage
                  ├─ /projects      → ProjectsPage
                  ├─ /research      → ResearchPage
                  ├─ /browser       → BrowserPage
                  ├─ /desktop       → DesktopControlPage
                  ├─ /phone         → PhonePage
                  ├─ /automation    → AutomationPage
                  ├─ /planner       → PlannerPage
                  ├─ /agents        → AgentsPage
                  ├─ /notifications → NotificationsPage
                  ├─ /approvals     → ApprovalsPage
                  ├─ /plugins       → PluginsPage
                  ├─ /analytics     → AnalyticsPage
                  ├─ /system-monitor → SystemMonitorPage
                  ├─ /settings      → SettingsPage
                  └─ *              → HomePage (fallback)
```

**Modified in this session:** Route `/` changed from HomePage to CommandCenterPage. Added `/orb` route for the old view. Added `startBadgePolling`.

---

## 14. Command Center Data Flow

```
CommandCenterPage (mounts at /)
  │
  ├─ useEffect (every 30s):
  │    └─ Promise.allSettled([
  │         commandCenter.briefing()    → GET /proactive/briefing
  │         commandCenter.deadlines()   → GET /executive/goals/upcoming?days=7
  │         commandCenter.risks()       → GET /predictive/risks
  │         commandCenter.suggestions() → GET /proactive/suggestions?limit=20
  │         systemStats (from aiStore)  → /status/system (polled every 5s)
  │       ])
  │
  ├─ Panel: System Context
  │    └─ Reads systemStats from aiStore (CPU/RAM/disk bars)
  │
  ├─ Panel: Active Project
  │    └─ Parses briefing response → project name + branch
  │
  ├─ Panel: Upcoming Deadlines
  │    └─ GET /executive/goals/upcoming?days=7
  │    └─ Renders goals + tasks with due dates
  │    └─ Click → navigates to /planner  ← ADDED THIS SESSION
  │
  ├─ Panel: Predictive Risks
  │    └─ GET /predictive/risks → top 4 predictions
  │    └─ Shows severity badge, category, horizon
  │
  └─ Panel: Attention Required
       └─ GET /proactive/suggestions (proactive + predictive mixed)
       └─ Click → POST /proactive/ack  ← ADDED THIS SESSION
       └─ "+ New Goal" form → POST /executive/goals  ← ADDED THIS SESSION
```

**Modified in this session:** Added deadline click navigation, suggestion acknowledgment, and quick-create goal form.

---

## 15. Sidebar Badge Flow

```
App.tsx useEffect
  └─ startBadgePolling(60000)
       └─ setInterval every 60s:
            └─ badgeStore.fetchCounts()
                 ├─ Promise.allSettled([
                 │    fetch("/executive/goals/upcoming?days=7") → deadline count
                 │    fetch("/proactive/suggestions?limit=20")  → suggestion count
                 │  ])
                 └─ Update Zustand store: { deadlines: N, suggestions: N }

DASHSidebar renders
  └─ useBadgeStore() → { counts }
       └─ resolveBadge(item, counts)
            ├─ If item.id === "home":
            │    ├─ total = deadlines + suggestions
            │    ├─ If total === 0: no badge
            │    ├─ Collapsed: colored dot (7px, top-right of icon)
            │    └─ Expanded: count pill with number
            └─ Else: no badge
```

**Added in this session:** `badgeStore.ts`, `resolveBadge()`, badge rendering in DASHSidebar.

---

## 16. WebSocket Communication Flow

```
Desktop App
  └─ wsClient.ts::connect()
       ├─ 1. Fetch device token from electron API
       ├─ 2. new WebSocket(wsUrl + "?token=...")
       ├─ 3. On open: send auth handshake
       ├─ 4. On message: parse JSON, route by type:
       │      ├─ "chat.response" → chatStore (append token)
       │      ├─ "chat.done" → chatStore (finalize message)
       │      ├─ "orch.*" → orchestratorStore
       │      ├─ "voice.tts_ready" → play audio
       │      └─ "system.*" → aiStore (status updates)
       ├─ 5. Heartbeat: pong every 30s
       ├─ 6. Stale detection: reconnect if no pong > 60s
       └─ 7. Reconnect: exponential backoff (1s → 30s max)

  └─ ws.ts::initializeWebSocket()
       └─ Wires wsClient events to Zustand stores
```

---

## What Was Modified in This Session

| File | Change | Flow # |
|------|--------|--------|
| `proactive/engine.py` | Added `_append_predictive_suggestions()`, `SEVERITY_TO_IMPORTANCE` map, `predictive_engine` param | #5 |
| `proactive/briefing.py` | Added `_trend_lines()`, `_prediction_lines()`, `_extract_top_risk()`, updated `format_briefing()` and `format_end_of_day()` | #6, #7 |
| `memory/service.py` | Added `save_typed_memory()`, `remember_decision()`, `record_work_context()`, `get_continue_context()` | #10 |
| `db/models/memory.py` | Added `confidence` float, `project_id` UUID columns | #9, #10 |
| `api/routes/security.py` | Added session list/revoke endpoints | #11 |
| `api/routes/legal.py` | Added legal document endpoints | #12 |
| `legal/privacy.py` | Fixed section 3.1 accuracy, section 7.3 font disclosure | #12 |
| `apps/desktop/src/App.tsx` | Route `/` → CommandCenterPage, added `/orb` route, badge polling | #13, #15 |
| `apps/desktop/src/pages/CommandCenterPage.tsx` | Added deadline click, ack action, quick-create goal | #14 |
| `apps/desktop/src/stores/badgeStore.ts` | New store for badge polling | #15 |
| `apps/desktop/src/components/DASHSidebar.tsx` | Added badge rendering (collapsed dot, expanded pill) | #15 |
| `apps/desktop/src/lib/api.ts` | Added commandCenter.* API methods | #14 |
| `sync/supabase_outbox_worker.py` | `_TABLE_COLUMNS` payload filter, NOT-NULL defaults, ValueError exhaustion comment | #31 |
| `executive/service.py` | `delete_goal` now enqueues `tombstone` (was invalid `delete`), also tombstones the goal itself | #31 |
| `tests/test_supabase_outbox.py` | Regression test: extra columns stripped before delivery | #31 |
| `apps/desktop/src/components/WorkflowCanvas.tsx` | New: drag-and-drop canvas (pointer events, SVG edges, grid snap, port wiring, Delete-key) | #17 |
| `apps/desktop/src/pages/AutomationPage.tsx` | Rewritten: Rules | Builder tabs, node palette, properties panel, save/run/duplicate/delete | #17 |
| `apps/desktop/src/lib/api.ts` | Added `workflows` client (list/templates/get/create/update/delete/execute/duplicate) + types | #17 |
| `api/routes/enhanced_features.py` | Added `PUT /enhanced/workflows/{id}` (WorkflowUpdateRequest) for canvas saves | #17 |
| `services/workflow_builder.py` | Custom workflows persist to `%LOCALAPPDATA%\DASH\workflow_state.json`, reloaded in `__init__` | #17 |
| `tests/test_workflow_builder_canvas.py` | 7 tests: CRUD persistence, template immutability, PUT route, if/else E2E | #17 |

---

## 17. Workflow Builder Canvas Flow

**Entry point:** Sidebar → `/automation` → `AutomationPage` (tab "builder") → `WorkflowCanvas`.

```
AutomationPage (BuilderTab)
  ├─ mount: workflowsApi.list() + listTemplates()        → GET /enhanced/workflows[/templates]
  ├─ select workflow → setNodes/setEdges from its shape
  ├─ palette drag → dataTransfer("application/dash-node-type") → canvas onDrop → new node (grid-snapped)
  ├─ node drag (pointer capture) → onPointerMove → snap(x,y) → onChange(nodes, edges) → dirty flag
  ├─ wire edge: port pointerdown → ghost path follows cursor → drop near target node
  │     → nearest-port hit → edge {from, to, condition: true|false|undefined}
  │     → replaces same-branch edge (one edge per output port)
  ├─ properties panel → updateNodeConfig(key, value) → node.config
  ├─ Save → PUT /enhanced/workflows/{id} {nodes, edges}
  │     → enhanced_features.update_workflow → workflow_engine.update() → _save_custom()
  │     → %LOCALAPPDATA%\DASH\workflow_state.json (custom only; templates excluded)
  ├─ Run → POST /enhanced/workflows/{id}/execute → engine.execute() → nodes_executed
  └─ backend restart → WorkflowEngine.__init__ → _load_custom() → workflows restored
```

Cycle warning: DFS over edges inside BuilderTab flags loops before save.

## 18. Knowledge Graph & Enhanced Settings UI Flow

### Knowledge graph (Knowledge page → Graph tab)

```
KnowledgePage.tsx
  └─ tab "graph" → components/KnowledgeGraphView.tsx
       ├─ GET /enhanced/knowledge-graph?max_nodes=250      → { nodes, edges }
       │    └─ KnowledgeGraph.get_graph()                   (in-memory + state file)
       ├─ POST /enhanced/knowledge-graph/rebuild
       │    └─ enhanced_features.rebuild_knowledge_graph()
       │         ├─ SELECT * FROM memories ORDER BY created_at DESC LIMIT 500
       │         └─ KnowledgeGraph.build_graph_from_memories(memories)
       │              ├─ extract_entities(title + content)   → ent_* nodes (NER + tech terms + dates)
       │              ├─ tags                                → tag_* nodes
       │              ├─ co_mentioned edges per memory pair   (_has_edge dedupe)
       │              └─ _save_state() → %LOCALAPPDATA%\DASH\knowledge_graph_state.json
       ├─ GET /enhanced/knowledge-graph/node/{id}            → node + neighbors (details panel)
       └─ requestAnimationFrame loop
            ├─ physics: repulsion(O(n²)) + springs + center pull, alpha decay
            └─ render: edges → nodes (type color, mention-count radius, selection halo, search dimming)
```

Interactions: drag node (pins during drag), drag empty space (pan), wheel (zoom-at-cursor), click node (details panel + neighbor navigation), type chips toggle visibility, search dims non-matches (Enter selects first match).

### Model Selector (ModelSelectorPage.tsx)

```
GET /enhanced/models/available → { models[], active }
GET /enhanced/models/history   → { history[] }
click card → POST /enhanced/models/swap?model_id=… → refresh history
model_ensemble.model_hotswap.swap() mutates the active model for all subsequent AI requests
```

### Plugins marketplace (PluginsPage.tsx → Marketplace tab)

```
GET /enhanced/plugins/marketplace → registry catalogue (id, rating, installs, permissions)
GET /enhanced/plugins/installed   → user registry with status
Install/Uninstall/Toggle → POST /enhanced/plugins/{id}/{action} → plugin_registry mutates → refetch both
```

### Settings: Shortcuts / Sounds / DND (SettingsPage.tsx)

```
loadShortcutSettings():
  GET /enhanced/shortcuts → shortcut_manager.get_all()      (action, shortcut, default, is_custom)
  GET /enhanced/sounds     → notification_sounds.get_settings() (sounds map, volume, enabled, options)
  GET /enhanced/dnd        → dnd_manager.get_state()            (enabled, schedule, exceptions)

Shortcuts: edit inline → POST /enhanced/shortcuts/update {action, shortcut}
           reset  → POST /enhanced/shortcuts/reset?action=…
Sounds:    per-event select → POST /enhanced/sounds/update {event_type, sound_id}
           volume slider    → POST /enhanced/sounds/volume?volume=…
           master toggle    → POST /enhanced/sounds/toggle?enabled=…   (route added this session)
DND:       toggle           → POST /enhanced/dnd/toggle?enabled=…
           schedule         → POST /enhanced/dnd/schedule?start=…&end=…
           exceptions       → POST /enhanced/dnd/exception?action=…
                            → POST /enhanced/dnd/exception/remove?action=…  (route added this session)
```

### Analytics activity row (AnalyticsPage.tsx)

```
fetchMetrics() now also fetches:
  GET /enhanced/activity/productivity → { score, tasks_completed, messages_sent, … }
  GET /enhanced/activity/daily        → { total_events, by_type, hourly_distribution }
Rendered as a 4-stat row only when the backend responds (no fake fallbacks).
```

**Session additions to backend:** `POST /enhanced/knowledge-graph/rebuild`, `POST /enhanced/sounds/toggle`, `POST /enhanced/dnd/exception/remove`, `KnowledgeGraph.build_graph_from_memories/_save_state/_load_state/_has_edge`; KG state now persists across backend restarts.

## 19. Security Services Flow (2FA, Biometrics, Vault, Chat, Anonymization)

### TOTP 2FA enrollment & verification

```
SecurityHardeningPage (2FA tab)
  ├─ GET  /features/security/2fa/status        → TOTPService.get_status(user_id)
  ├─ POST /features/security/2fa/enroll        → TOTPService.enroll(user_id)
  │    ├─ secret = base32(os.urandom(20))
  │    ├─ backup codes → SHA-256 hashes stored (plaintext shown once)
  │    ├─ _save() → %LOCALAPPDATA%\DASH\twofactor_state.json
  │    └─ returns otpauth:// URL (scan into authenticator app)
  ├─ POST /features/security/2fa/verify {code, confirm:true}
  │    └─ TOTPService.verify(user_id, code)
  │         ├─ normalize (strip spaces, 6/8 digits)
  │         ├─ backup-code check: SHA-256(code) in stored hashes → burn it
  │         └─ TOTP check: _hotp(key, counter) for counters now-1/now/now+1
  │              ├─ hmac.compare_digest against candidate
  │              ├─ replay guard: "counter:code" set (last 50 kept)
  │              └─ confirm=true sets confirmed → enable() unblocked
  └─ POST /features/security/2fa/enable        → requires confirmed enrollment
```

`_hotp`: HMAC-SHA1(key, struct.pack(">Q", counter)) → dynamic truncation (RFC 4226 §5.3) → 6 digits.

### Biometric verification (data never leaves the device)

```
SecurityHardeningPage (Biometric tab)
  ├─ GET /features/security/biometric/status   → BiometricAuthService.get_status
  ├─ Enroll:
  │    ├─ electronAPI.biometric.availability() → ipcMain "biometric:availability"
  │    │    └─ systemPreferences.canPromptTouchID() (macOS) / win32 probe
  │    └─ POST /features/security/biometric/enroll
  ├─ Test verification:
  │    ├─ POST /features/security/biometric/challenge {action}
  │    │    └─ single-use nonce (token_urlsafe(32)), TTL 120s
  │    ├─ electronAPI.biometric.prompt("Unlock DASH") → ipcMain "biometric:prompt"
  │    │    └─ macOS: systemPreferences.promptTouchID (native dialog)
  │    └─ POST /features/security/biometric/verify {challenge, success}
  │         └─ pops challenge (single use), checks TTL, audits outcome
  └─ GET /features/security/biometric/audit    → attempt history (last 200)
```

### Password vault (AES-256-GCM at rest)

```
PasswordManagerPage → authFetch("/features/vault/*")
  ├─ POST   /vault/entries              → add_entry(category, title, fields, notes, tags)
  ├─ GET    /vault/entries[?category=]  → list (decrypted server-side for the owner)
  ├─ GET    /vault/entries/{id}         → get_entry (access_count++)
  ├─ PATCH  /vault/entries/{id}         → update_entry (title/fields/notes/tags/favorite)
  ├─ DELETE /vault/entries/{id}         → delete_entry
  ├─ GET    /vault/generate-password    → secrets.choice over alphabet
  └─ GET    /vault/stats                → totals, weak-password count (<12 chars)

Persistence (PasswordManager._save):
  entry_json → HKDF(master, info=entry_id) → AESGCM.encrypt(nonce, json, aad=entry_id)
  → vault_state.json {encrypted: {entry_id: nonce+ct b64}}
  master key: vault_master.key (random per install; PBKDF2 passphrase path reserved)
```

### Encrypted chat (per-conversation keys)

```
POST /features/messenger/send {recipient, content}
  └─ EncryptedMessenger.send_message(sender=user.id, recipient, content)
       ├─ conv_key = "::".join(sorted([a, b]))
       ├─ HKDF(root, info="conv:<conv_key>") → AESGCM key
       ├─ content → ct = AESGCM.encrypt(nonce, content, aad=msg_id)
       └─ messenger_state.json stores ct only (plaintext asserted absent in tests)

POST /features/messenger/messages {other_user} → get_messages (decrypt for participant)
GET  /features/messenger/conversations          → inbox with unread counts
GET  /features/messenger/unread                 → total unread
root key: messenger_root.key beside state file (survives restarts)
```

### PII anonymization

```
POST /features/privacy/scan      → DataAnonymizer.scan_text (report, no mutation)
POST /features/privacy/anonymize → DataAnonymizer.anonymize(text, mask_types?)

Pattern order (specific → greedy):
  email → ssn → credit_card → ip_address → api_key → phone (last, no "." in class)
  email/ip → HMAC-SHA256(pepper, type:value)[:12] deterministic pseudonym
  ssn/card/key → [TYPE] full mask; phone → [PHONE_...last4]
```

**Security routes added this session:** biometric (availability/enroll/status/challenge/verify/revoke/audit), vault PATCH/DELETE/{id}, messenger messages-by-conversation; 2FA verify now takes `confirm` and enable requires it; all security endpoints key on stable `user.id` instead of `id(user)`.

## 20. Feature Pages → Services Wiring Map

### Email (EmailPage.tsx)

```
Promise.all:
  GET /features/email/accounts  → {accounts}
  GET /features/email/inbox?limit=50 → {emails}
  GET /features/email/stats     → {total_inbox, unread, total_sent, accounts, rules}
select email → optimistic read flag + POST /features/email/mark-read {email_id}
             → email_service.mark_read (marks in service registry)
search: Enter → GET /features/email/search?q=… → {results}
Add Account → POST /features/email/accounts {email, provider:"imap"}
```

### Calendar (CalendarPage.tsx)

```
GET /features/calendar/events|list|stats → month grid + today panel + counters
New Event → POST /features/calendar/events {title, start, end}
            end = start + 1h (client-side default; dialog has no end field)
```

### Voice Commands (VoiceCommandsPage.tsx)

```
GET /features/voice/config     → {wake_words[], language, command_count, listening}
GET /features/voice/commands   → {commands: {id: {patterns[], action, target}}}
GET /features/voice/memos      → {memos[]}
stop recording (with transcript) → POST /features/voice/memos {title, transcript, duration_seconds}
```

### Browser Management (BrowserPage.tsx)

```
GET /features/browser/tabs|bookmarks|history?limit=30|stats
Open URL → normalize (https:// if scheme missing) → POST /features/browser/tabs/open {url, title}
Close tab → POST /features/browser/tabs/close {tab_id}
ExternalLink → window.open(url) handoff to system browser
```

### Collaboration (CollaborationPage.tsx)

```
GET /features/workspaces → {workspaces}
New Workspace → POST /features/workspaces {name, description} → owner = str(user.id) (stable)
Delete → DELETE /features/workspaces/{id}
```

### Prompt Studio (PromptStudioPage.tsx)

```
GET /features/prompts           → {prompts}
GET /features/prompts/templates → {templates}  (click = prefill create dialog)
Create → POST /features/prompts {name, content, category}
Copy/Test → clipboard + handoff to Chat
```

### Infrastructure (InfrastructurePage.tsx, 15s auto-refresh)

```
GET /features/infra/circuit-breaker → {breakers: {name: {state, failures, total_trips}}}
GET /features/infra/cache/stats     → {size, max_size, hits, misses, hit_rate}
GET /features/infra/health          → {overall, services: {name: {status}}}
Clear cache → POST /features/infra/cache/clear → refetch stats
```

**Convention applied to all seven pages:** no fabricated fallback data — failures render an explicit error banner; real empty states when the backend has no data; all create/delete actions surface real success/failure via notifications.

## 21. Local SQLite Persistence Flow (services/local_store.py)

### Startup path (migration time)
```
backend starts
  └─ imports services (email_calendar, voice_browser, collaboration,
     advanced_ai, model_ensemble, plugin_service, shortcuts_service,
     security_hardening)
       └─ each singleton constructor: LocalStore.instance()
             └─ LocalStore.__init__ → _open()
                  ├─ mkdir %LOCALAPPDATA%\DASH
                  ├─ sqlite3.connect(dash_local.db)  [WAL, synchronous=NORMAL]
                  └─ _migrate()
                       ├─ CREATE TABLE IF NOT EXISTS schema_migrations
                       ├─ SELECT applied versions
                       └─ for each pending (version, statements):
                            BEGIN → run DDL → INSERT version → COMMIT
                            (transaction = all-or-nothing per migration;
                             OperationalError = another process won the race → rollback, continue)
       └─ constructor hydrates in-memory state:
            e.g. EmailService.__init__: _accounts = store.list_docs("email_accounts")
                 DNDManager.__init__: state = store.kv_get("dnd_state")
                 BiometricAuthService.__init__: SELECT … FROM biometric_enrollments
```

### Request path (write-through)
```
API route (e.g. POST /features/calendar/events)
  └─ CalendarService.create_event()
       ├─ mutate in-memory dict (unchanged service semantics)
       └─ store.put_doc("calendar_events", id, event, seq=next_seq())
            └─ INSERT … ON CONFLICT(id) DO UPDATE  [RLock-guarded, committed]
```
Reads never hit the store after startup — they serve the hydrated in-memory
lists, exactly as before; the store is the durability layer, not a query
engine (except where filtered queries exist: emails by folder, comments by
entity, biometric audit tail).

### Restart path (the guarantee being tested)
```
process dies → process restarts → singletons re-import
  └─ constructors hydrate from dash_local.db
       └─ previously-created emails/events/workspaces/plugins/shortcuts/
          DND/sounds/biometric enrollments reappear
```
`tests/test_local_store_persistence.py` proves this per service by writing
with one instance and reading with a *fresh* instance on the same file, plus:
- migration idempotence (reopen 3×, no duplicate schema_migrations rows),
- the no-store-arg production path lands in the shared singleton file,
- biometric revoke deletes its enrollment row (not just the dict entry).

### Store API (one connection per store, RLock-guarded)
- `put_doc(table, id, data, seq)` / `delete_doc(table, id)` / `list_docs(table, newest_first=)`
- `kv_get(key, default)` / `kv_set(key, value)` / `kv_del(key)` → `kv_settings`
- raw `execute(sql)` / `query(sql)` for indexed/columnar tables
  (`emails.folder`, `comments(entity_type, entity_id)`, `biometric_audit`)
- `LocalStore.instance()` = process-wide shared file; `open_store(path)` = explicit path for tests

## 22. Connector Webhook Flow (Slack / Telegram / Notion)

### Inbound (platform → DASH)
```
Platform (Slack/Telegram/Notion servers)
  └─ POST /api/v1/connectors/{platform}/events   [no DASH JWT — platform-verified]
       └─ routes/integration_connectors.py
            ├─ Slack:    ingest_slack(ts, raw_body, X-Slack-Signature)
            ├─ Telegram: ingest_telegram(payload, X-Telegram-…-Secret-Token | path token)
            └─ Notion:   ingest_notion(payload, X-Notion-Signature | verification_token)
                 └─ verify (HMAC / constant-time compare) → FAIL ⇒ 401, event logged, no state change
            ├─ Slack url_verification ⇒ plain-text challenge response
            ├─ parse_{slack,telegram,notion}_* → {event_id, author, channel, text, …}
            └─ ConnectorService._record_inbound()
                 ├─ dedup by platform event id (Slack event_id / TG update_id / Notion request_id)
                 │    └─ seen ⇒ {ok, duplicate: true}, nothing stored twice
                 ├─ append message + kv_set(connector_msgs_<svc>)   [LocalStore #36]
                 └─ rules[svc].to_dash? ⇒ _notify_dash()
                      └─ get_notification_service().send(title="Slack #C9: U1", body=text)
                           └─ push service applies its own quiet hours/cooldown
```

### Outbound (DASH → platform)
```
Desktop/API client — POST /api/v1/connectors/forward  [JWT required]
  {service, text, channel?}
       └─ ConnectorService.forward_out()
            ├─ connector not configured/disabled ⇒ 400 (no silent no-op)
            ├─ Slack:    POST <incoming-webhook-url> {text}
            ├─ Telegram: POST api.telegram.org/bot<token>/sendMessage {chat_id, text}
            ├─ Notion:   POST configured relay webhook {content}
            └─ status: sent (2xx) | recorded (no credentials configured — honest)
                       | failed (platform error, stored with error code)
                 └─ message + status persisted (kv_set connector_msgs_<svc>)
```

### Configuration & persistence
```
POST /connectors/configure  [JWT] → secrets AES-256-GCM encrypted (connector_secrets.key
  beside dash_local.db) before kv_set(connector_cfg_<svc>)
Backend start → ConnectorService() singleton hydrates configs (decrypts), rules, messages
  from LocalStore — restarts keep credentials, forwarding rules, and history
GET /connectors/status | /rules | /messages/{svc} | /events  [JWT — booleans only, secrets never returned]
```

## 23. API Sweep Suite — How the Invariants Travel

**Entry:** `tests/test_api_sweep.py` builds the app via `create_app()` and calls `app.openapi()` — the OpenAPI schema is the source of truth, so the sweep's coverage is always exactly the deployed surface (654 operations / 591 paths today).

**Operation discovery:** `_all_operations(spec)` flattens `spec["paths"]` into `(method, path)` pairs — this list parameterizes the two no-5xx sweeps. Path params are filled from each operation's own parameter schemas (`_fill_params`); request bodies come from `_minimal_valid`, a recursive schema-walker that satisfies required fields from enums/defaults/types (uuid/date-time formats included).

**Request flow per case:** pytest parametrization generates one case per operation per phase → `TestClient(create_app())` → ASGI transport → middleware chain (CORS → auth dependency → rate limiter) → route handler. The rate limiter's buckets are cleared between phases (`get_api_limiter().buckets.clear()`) so limiter state never decides an outcome.

**The five enforcement layers, in order:**
1. `test_no_5xx_on_minimal_valid_input` — every operation, valid-shaped input: asserts status < 500 (503 whitelisted as "dependency not configured").
2. `test_no_5xx_on_junk_body` — same surface, hostile body: a malformed payload must be *rejected* (4xx) by validation, never crash a handler.
3. `test_every_protected_route_rejects_anonymous` — the auth contract: anon client walks all 654 operations; anything answering 2xx outside the curated public allowlist (`/health`, `/api/v1/legal/*`, `/api/v1/memory/types`) is a leak reported with its exact `(method, path, status)`.
4. `test_openapi_covers_full_surface` — guards the guard: fails loudly if the exposed surface shrinks (≥600 ops expected), so the sweep can't silently pass against a broken app.
5. Deep happy-paths — memory literal-route regression (`/stats|/types|/continue` must beat `/{memory_id}` matching), memory create→search→delete roundtrip, proactive suggestions, legal docs, health.

**What the first run proved:** zero-500 across all 654 operations *after* fixing the five crash paths it found (OAuth provider ValueError, webhook JSONDecodeError, ollama-tunnel proxy exceptions, memory route shadowing, briefing None-format) — and the auth layer found three fully-public routers (`integrations_all`, `cloud_relay`, `ecosystem`, plus `ollama_tunnel`) that now 401 anonymously.

**Regression promise:** a route added tomorrow is swept automatically. A router mounted without `dependencies=[Depends(get_current_user)]`, a handler that lets an exception escape, or a webhook receiver that trusts request bodies — each fails CI with the offending route in the assertion message.

## 24. Autostart Flow — Login to Working Backend

**Boot chain, in order:**
1. **Windows login** → `HKCU\...\Run` key `DASH = "C:\Program Files\DASH\DASH.exe" --hidden` (written by `app.setLoginItemSettings` with `args:["--hidden"]` when Start-minimized is on).
2. **DASH.exe (Electron main, `dist-electron/main.js`)** → module init: single-instance lock (second launch quits and focuses the first). `launchHidden` = `--hidden`/`--start-minimized` argv OR `getLoginItemSettings().openAsHidden`.
3. **`app.whenReady()`** → `backendManager.start()` (serialized on its op-chain mutex):
   - probe `/health` on 127.0.0.1:8000 → healthy DASH? **reuse** (never a second backend)
   - port occupied by stale DASH → kill it, wait 1.2s, spawn exactly one
   - port occupied by non-DASH → **blocked** (never fight a foreign process)
   - port free → **spawn**: packaged = `process.resourcesPath/backend` (DashBackend.exe, else bundled venv python, else system python) with `-m uvicorn dash_backend.main:app --host 127.0.0.1 --port 8000`; dev = `apps/backend` venv-or-global python
   - `waitForBackend`: 120 × 500ms health probes (60s window; child-exit aborts in ~0.5s); on health → `lifecycle=healthy`, 15s monitor loop starts with backoff-restart (max 3 attempts)
4. **Backend lifespan (`dash_backend/main.py`)**, each step failure-isolated: alembic `upgrade head` → device identity → executive worker → automation scheduler → event bus → system services (scheduler/health/metrics/resource/cache + AI provider monitor) → enhanced sync → plugin manager + hot reloader → autonomous agents + brain → performance optimizers → Ollama auto-start (model `dash-finetuned`) + background monitor → predictive device sampler → `system.startup` event.
5. **Back in Electron** → `createWindow()`; if `launchHidden`: `startAsOrb` ? floating orb window : hide to tray (`enableBackgroundMode`).

**Startup prefs flow:** SettingsPage toggle → `startup:set-settings` IPC → `app.setLoginItemSettings(openAtLogin, openAsHidden, args:["--hidden"])` + persist full pref object to `userData/startup-prefs.json`; read path merges login-item state, `launchArguments`, and persisted prefs (Windows can't report openAsHidden).

**What the tests lock:** `tests/test_autostart_contract.py` asserts the chain's load-bearing details — Run-key args written, prefs persisted, orb honored inside the `launchHidden` block, packaged dir on `process.resourcesPath`, dual spawn fallbacks, ≥60s health window, uvicorn args, stale-replace/reuse logic, stale-bundle markers on the built artifact, and a live boot with every service engaged, zero startup exceptions, and clean shutdown.

## 24. New feature pages render flow (this session)

App.tsx lazy-loads ConnectorsPage/RagDocumentsPage/FineTuningPage/Phase3OpsPage/AiLabsPage/RemoteAccessPage per route (/connectors, /documents, /fine-tuning, /operations, /ai-labs, /remote-access); CommandPalette NAV_ITEMS now exposes all six.

Data path per page: mount → useCallback fetchAll → authFetch (lib/api.ts) resolves relative or absolute URL against API_BASE (VITE_API_URL or http://127.0.0.1:8000/api/v1), attaches Bearer device token from preload window.electronAPI.auth.deviceToken() → backend route (integration_connectors.py, rag/router.py, fine_tuning.py, phase3_features.py, phase4_features.py, ec2_control.py + tunnel.py + cloud_relay.py) → service singleton → JSON → React state → GlassCard lists. Failures degrade to empty-state text, never crash the page (safe() wrapper with .ok checks and try/catch).

Modified: lib/api.ts (authFetch resolution), App.tsx (routes), CommandPalette.tsx (entries), 6 new page files; backend rag/router.py (text() fix).

## 25. Terminal-Flash Elimination Flow (decisions.md #41)

**Every spawn path in DASH and how it stays windowless:**

1. **Backend runtime spawns** — `dash_backend/__init__.py` imports `_win_noswindow` FIRST (before any service/route module), which wraps `subprocess.Popen/run/call/check_call/check_output` to OR `CREATE_NO_WINDOW` into creationflags. Because asyncio's Proactor `create_subprocess_exec/_shell` allocates through `subprocess.Popen`, the ~20 async spawn sites (system samplers, cloud relay, Ollama monitor) inherit the same guarantee. Flow: any service module → `subprocess.run(...)` → wrapped Popen → `CreateProcessW` with CREATE_NO_WINDOW → no console allocated.
2. **Logon tasks** — Windows login → Task Scheduler → `wscript.exe run-hidden.vbs <command>` (wscript is a GUI-subsystem host: zero console) → target runs hidden. DASH-Backend, DASH-AllServices, DASH-Ollama, DASH-AutoConnect, DASH-Watchdog all route through it; DASH-Desktop runs `DASH.exe --hidden` (Electron window flag, not a console).
3. **Electron spawns** — already `windowsHide: true` (BackendManager child + any helper exec); unchanged.
4. **Test guarantee** — `test_no_flash_terminal.py` proves the shim is active after any `import dash_backend`, that real cmd.exe children run correctly under it, that caller flags are OR-preserved, and that `__init__.py` keeps the shim wired (source-level regression guard).

**What was flashing before:** context collectors polling tasklist/wmic, git status probes, ping reachability checks, winget update detection — each spawning a console every poll interval from the console-less backend, plus the two misconfigured logon tasks.

## 26. Test-Run DB Flow (decisions.md #42)

**Which database each test layer touches, in order of import:**
1. pytest starts → `tests/conftest.py` runs at collection: sets `DASH_DATABASE_URL` to a fresh temp FILE db (`dash_test.db`), then `Base.metadata.create_all` builds the schema and `alembic.command.stamp(..., "head")` marks it current — before any test imports the app.
2. App-booting tests (`create_app()` + ASGITransport) → `dash_backend/db/session.py` engine binds `settings.database_url` → conftest's env var wins → all app writes land in the temp DB, never `dash_dev.db`. ASGITransport does not run the lifespan, so only the lifespan test runs alembic — which sees the stamp and no-ops.
3. Tests using the `db_session`/`db_engine` fixtures → separate per-test in-memory engines (unchanged behavior).
4. Feature-service tests → `DASH_LOCAL_STORE` temp file (pre-existing hermetic override).

**Boot-time migration flow (production):** `main.py` lifespan → `alembic upgrade head` with `sqlalchemy.url` = settings.database_url → SQLite URLs now also carry `connect_args timeout:30` on the app engine, so a concurrent writer makes the boot wait instead of erroring.

**Why a file DB, not `:memory:`:** the app engine pools connections; with `:memory:` each pooled connection gets its own empty database and schema-dependent queries fail intermittently. A file DB is shared by all pooled connections — the same semantics as production SQLite.

## 27. Outbox Dead-Letter Recovery Flow (decisions.md #43)

**Event lifecycle, including the recovery loop:**
1. `enqueue_event` → `pending` (attempt_count 0, recovery_count 0).
2. Worker `deliver_once` (every 5s): FIRST re-arms due dead letters via `claim_dead_letter_events` (`status = dead_letter AND recovery_count < 3 AND next_retry_at <= now` → each becomes `pending`, attempt_count 0, recovery_count+1), THEN `claim_pending_events` delivers whatever is due.
3. Delivery failure → `fail_event`: attempts 1-4 → `pending` with bounded exponential retry (2s…5min); attempt 5 → `dead_letter` with `next_retry_at = now + 1h` (the hourly recovery gate).
4. If the hour passes while recovery budget remains, step 2 re-arms → fresh 5-attempt budget against the (possibly healed) cloud; success → `completed` (recovery_count keeps its value, proving it survived recovery). Budget exhausted (recovery_count = 3) → dead letter is final; no claim query ever selects it again.
5. Deterministic errors (ValueError: invalid payload/operation) short-circuit the loop: attempt_count → 4 AND recovery_count → 3, so they dead-letter immediately and never resurrect.

**State invariants:** `recovery_count` only increments in `claim_dead_letter_events`; `attempt_count` resets only there. `next_retry_at` is always non-null for pending/dead-letter events with remaining budget. Every transition commits in its own helper (`fail_event`/`complete_event`/`claim_*`), so a crash mid-pass leaves at most a `processing` row that the next pass's claim ignores until... (note: `processing` rows are not re-claimed — pre-existing behavior, outbox is best-effort one-way sync by design).

**Migration flow:** `b2c3d4e5f6a7` adds `recovery_count` with server_default 0 → existing dead letters become recovery-eligible immediately after upgrade (intentional catch-up).

## 28. Test Determinism Flow (decisions.md #44)

**What runs live vs stubbed, in collection order:**
1. conftest import time: `SUPABASE_ENABLED/SYNC_ENABLED` forced false → goal/task writes never enqueue outbox events in tests unless a test monkeypatches `sync_is_enabled` itself.
2. Every test (autouse `_hermetic_ai_providers`): `get_embedding`/`create_embedding` stubbed at all four binding sites (memory.service, conversation_embeddings.service, rag.service, both provider modules) → memory search takes the lexical fallback, no network.
3. `test_integration.py`: session-scoped in-memory engine with StaticPool → schema always matches current models; no stale file, no git-tracked db.
4. Whole suite: pytest-timeout 60s/test (thread method) → a hang is a failure with a stack trace, never a frozen job.

**Still live by design:** the piper binary tests (skip cleanly without tools/piper/piper.exe), the autostart lifespan boot (real alembic + services against a temp DB), and the API sweep (ASGI in-process, no network).

## 29. Git Sync Flow After Reconciliation (decisions.md #45)

**Old flow (retired):** edit locally → fetch in /tmp/dash_final clean clone → reset --hard → cp files → commit → push (worked around 3.7GB legacy pack making direct pushes time out).

**New flow:** edit locally → `git add <files>` → `git commit` → `git push origin website-v1` directly. First post-reconcile push sent only the 183-file tree adoption + delta commits (small); subsequent pushes send only real deltas. `main` is kept a strict fast-forward of `website-v1` — publish to main with `git push origin origin/website-v1:main` (no local main needed) or push the same commit to both refs.

**Recovery:** pre-reconcile local history (121 commits, incl. the duplicated work) remains reachable at branch `backup/pre-reconcile`; delete it once confident nothing unique was lost: `git branch -D backup/pre-reconcile`.

## 30. Outbox Health Flow (decisions.md #46)

**Data path:** worker loop (every 5s: re-arm dead letters → deliver pending) mutates `sync_outbox_events.status/attempt_count/recovery_count` → desktop App.tsx mount starts `startBadgePolling(60s)` → `badgeStore.fetchCounts` calls three endpoints in parallel via authFetch (`/executive/goals/upcoming`, `/proactive/suggestions`, new `/sync/outbox/health`) → outbox body stored in badgeStore (`outbox`, `outboxError`) → `DASHSidebar` footer renders `SyncHealthIndicator` from that state.

**Endpoint flow:** `GET /sync/outbox/health` → device-token auth (router-level `get_current_user_id`) → sync disabled? → `{state: LOCAL_ONLY}` → else one grouped count + retryable count + 5 newest dead letters + max(completed_at) against the app DB → state derivation: processing>0 → SYNCING; dead|pending>0 → DEGRADED; else HEALTHY → JSON. Never touches Supabase (the point is to reflect LOCAL reality, and the endpoint must stay fast even when the cloud is down — that's usually when someone checks it).

**UI decision flow:** state null (no data / backend down) → render nothing (global connection dot covers it) → HEALTHY/LOCAL_ONLY → nothing (absence = healthy) → ERROR → static warning chip, click → Command Center → DEGRADED → warning chip with dead-letter count, click toggles inline expansion (pending/retryable/stuck + recent failure rows), last-sync timestamp at bottom.

**Failure semantics:** non-OK health response → `state: ERROR` kept in store (visible "unknown"), fetch rejection (backend unreachable) → outbox cleared to null (the system-ready dot already signals disconnection) — the indicator never lies by showing stale healthy data.

## 31. Workflow Execution History Flow (decisions.md #47)

**Write path:** `POST /enhanced/workflows/{id}/execute` → `WorkflowEngine.execute` → builds exec_record (status/nodes/duration/error) → appends to `self._executions` → if the workflow is NOT a template, `_save_custom()` writes `{version, custom_workflows, executions: last 500}` to the state file atomically → run_count/last_run updated on the workflow (and persisted for custom workflows).

**Restart path:** backend boots → module import → `workflow_engine = WorkflowEngine()` → `_load_custom()` (custom workflows) + `_load_executions()` (ring buffer, trimmed) → history survives restarts even though executions of template runs only live in memory for the session (templates are code-owned; their history still displays until restart).

**Read path:** detail card History toggle → `GET /enhanced/workflows/{id}/executions?limit=20` (per-workflow) — the all-workflows `GET /enhanced/workflows/executions?limit=N` literal route sits BEFORE the dynamic `/{workflow_id}` route in the router so it is never shadowed → newest-first list → React panel maps each record to status icon + duration + start time + node chain + error.

**Selection flow:** clicking a workflow (`selectWorkflow`) keeps the History toggle state and reloads that workflow's history if open; Run re-fetches history when the panel is visible, so the newest execution appears immediately without toggling.

## 32. Template Instantiation Flow (decisions.md #48)

Click **Use** (gallery card) or **Use Template** (detail view) →
`POST /enhanced/workflows/templates/{id}/instantiate` →
`enhanced_features.instantiate_template_route` (literal path, no dynamic-segment shadowing) →
`WorkflowEngine.instantiate_template()`:

1. Template lookup in code-seeded `_templates`; missing → `{"ok": False, "reason": "Template not found"}`
2. `copy.deepcopy` nodes/edges (template dicts are shared code-seeded state — never handed to editable copies)
3. Name dedup against custom workflows + prior instances → `"<Name> (2) (3)…"`
4. Custom workflow dict created: `is_template=False`, `instantiated_from=<tpl id>`, fresh `id`/`created_at`, `run_count=0`
5. Persisted into the state file's `workflows` list; returned in the response

UI then `setSelected(newWorkflow)` (detail view opens on the editable copy) and re-fetches lists — the new workflow appears under **My Workflows** instantly. Duplicate runs of the same template produce `(2)`, `(3)` names instead of errors.

## 33. Browser Preview Auth + Builder Interaction Flow (decisions.md #49)

Renderer boots in a browser (no Electron bridge) →

1. `getDeviceToken()` — bridge absent → `fetchBrowserDevToken()` → `GET /api/v1/devtools/device-token` → backend gate: `env=="development"` AND loopback client → returns device token → cached; every `authFetch`/`request` attaches `Authorization: Bearer`. `wsClient.connect()` uses the same accessor for the handshake `?token=`.
2. AutomationPage → Builder tab → `workflowsApi.list()` (custom only, templates filtered server-side) + `listTemplates()` → dropdown, no duplicates.
3. Canvas interactions → `WorkflowCanvas` (`editable=isCustom`): pointer drag → world coords → grid snap → `mutate()` (page re-guards) → dirty → Save → `PUT /enhanced/workflows/{id}` → persisted to state file. Port drag → `finishConnect`: body-rect hit wins, else nearest visible port within threshold → one edge per out/branch port (replace) → `onChange`.
4. Run → `POST .../execute` → engine executes nodes → status line "Run completed (…ms, N nodes)".

Boot (any DASH process): lifespan → alembic upgrade (retry ×3, WAL+busy_timeout on SQLite) → services. Two concurrent boots no longer corrupt schema; lock contention is absorbed by pragmas + retry.

## 33. Browser Preview Auth + Builder Interaction Flow (decisions.md #49)

Renderer boots in a browser (no Electron bridge):

1. getDeviceToken() — bridge absent → fetchBrowserDevToken() → GET /api/v1/devtools/device-token → backend gate: env==development AND loopback client → returns device token → cached; every authFetch/request attaches Authorization Bearer. wsClient.connect() uses the same accessor for the handshake token query param.
2. AutomationPage → Builder tab → workflowsApi.list() (custom only, templates filtered server-side) + listTemplates() → dropdown, no duplicates.
3. Canvas interactions → WorkflowCanvas (editable=isCustom): pointer drag → world coords → grid snap → mutate() (page re-guards) → dirty → Save → PUT /enhanced/workflows/{id} → persisted to state file. Port drag → finishConnect: body-rect hit wins, else nearest visible port within threshold → one edge per out/branch port (replace) → onChange.
4. Run → POST .../execute → engine executes nodes → status line Run completed (duration, node count).

Boot (any DASH process): lifespan → alembic upgrade (retry x3, WAL+busy_timeout on SQLite) → services. Two concurrent boots no longer corrupt schema; lock contention is absorbed by pragmas + retry.

## 34. Branch Execution Flow (decisions.md #50)

Run: POST /enhanced/workflows/{id}/execute (optional {"input_data": {...}}) → engine.execute → _traverse(wf, exec_record, context):

1. Start at trigger nodes (fallback: first node) → queue.
2. Pop (node, branch): unknown id → skip; already visited → skip (cycle guard); step cap 200 → RuntimeError → run failed.
3. Execute node → append to nodes_executed.
4. condition node → _evaluate_condition(config, context) → condition_results[id]=result → successors = edges tagged matching branch (fallback to unconditional edges when the node has no branch-tagged edges at all).
5. other nodes → successors = unconditional edges.
6. output.conditions = condition_results; desktop Run line and history chips render TRUE/FALSE per condition.

_evaluate_condition: field missing → False; _coerce normalizes "50"→50, "false"→False; op dispatch (eq/ne/gt/gte/lt/lte/contains/not_contains/starts_with/ends_with/in/truthy); unknown op or type error → False (fail-safe to the non-effect branch).

## 35. Knowledge Graph Data Flow (decisions.md #51)

Rebuild: KnowledgePage "Rebuild from memories" → POST /enhanced/knowledge-graph/rebuild → KnowledgeGraph.rebuild_from_memories() scans the memory table → heuristic NER extracts entities (capitalized phrases → concept/person etc.) + co-mention edges (every entity pair within one memory) → persists graph JSON to the service state file → returns {memories_scanned, entities_extracted, edges_created}.

Render: GET /enhanced/knowledge-graph → KnowledgeGraphView force-directed canvas (type chips filter, search-select opens detail panel, neighbor buttons traverse entity→entity; empty graph renders a role=status hint instead of blank canvas).

Entries tab: GET /memory?limit=200 (client-side knowledge filter — the endpoint has no type param; the old phantom ?type=knowledge was silently ignored).
