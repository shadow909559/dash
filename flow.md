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
