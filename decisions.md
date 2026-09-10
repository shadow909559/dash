# DASH — Decision Log

Every meaningful technical decision, why it was made, and what alternatives were considered.

---

## 1. Proactive Intelligence Engine — Signal-Based Architecture

**Decision:** Use a `Signal` dataclass with id/category/title/message/importance/payload, detected by `detect_signals()` from an `EnvironmentContext` snapshot, rather than polling individual subsystems.

**Why:** A snapshot-then-detect pattern means one call gathers all context (device, project, activity), and the signal detectors are pure functions over that snapshot. This is testable, deterministic, and avoids N+1 database queries. An alternative would have been event-driven (subscribe to state changes), but signals are ephemeral — they only matter when the user asks for suggestions, not in real time.

**Files:** `dash_backend/proactive/signals.py`, `dash_backend/proactive/engine.py`

---

## 2. ProactiveEngine — Threshold + Cooldown + Dedup Gating

**Decision:** Suggestions pass through three gates: importance threshold (default 0.55), per-signal cooldown (default 120 min), and session-level dedup (seen set cleared each evaluate call).

**Why:** Without gating, the same low-importance signal would appear on every 30-second poll. Cooldown prevents nagging. Dedup prevents duplicates within one request. Threshold filters noise. This matches the spec's requirement for "respectful" proactive behavior. The alternative was a simpler "show all" approach, but that would overwhelm users.

**File:** `dash_backend/proactive/engine.py` — `evaluate()`

---

## 3. ProactiveState — Disk-Persisted Cooldown File

**Decision:** Store signal shown-times in a JSON file at `%LOCALAPPDATA%/DASH/proactive_state.json` rather than in SQLite.

**Why:** The proactive state is ephemeral and doesn't need ACID transactions. A JSON file is faster for reads, simpler to debug, and survives database resets. It also avoids schema migrations for a feature that's purely operational state.

**File:** `dash_backend/proactive/state.py`

---

## 4. Predictive Engine — Least-Squares Trend Detection

**Decision:** Use numpy's `polyfit` (degree 1) for linear regression on device sample history, rather than a more complex time-series model.

**Why:** DASH samples device metrics every 5 minutes, giving ~288 points/day. A simple linear trend with R² confidence is sufficient to detect "disk is filling up" or "RAM usage is climbing." More complex models (ARIMA, exponential smoothing) would add dependencies for marginal accuracy gains on this data volume. The trend analysis is supplementary — it's used for predictions, not critical decisions.

**File:** `dash_backend/predictive/engine.py` — `_device_predictions()`

---

## 5. PredictiveEngine — SampleStore with Rolling Window

**Decision:** Keep device samples in a JSON file with a 7-day rolling window (max 2016 samples at 5-min intervals), capped at 2 MB.

**Why:** A rolling window prevents unbounded disk growth. 7 days provides enough history for meaningful trend detection (e.g., "disk usage increased 2% this week"). JSON was chosen over SQLite because samples are append-only, rarely queried by index, and the entire file is read for trend analysis anyway.

**File:** `dash_backend/predictive/sampler.py`

---

## 6. DeviceSampler — Background Task with Configurable Interval

**Decision:** Run the device sampler as an `asyncio.create_task` with a minimum interval of 30 seconds (overridable for tests), started during app lifespan.

**Why:** The sampler needs to run continuously in the background without blocking request handlers. `asyncio.create_task` is the standard FastAPI pattern for background work. The 30-second floor prevents test files from spamming the sampler during full test runs. An alternative was a periodic scheduler (like APScheduler), but the app already uses APScheduler for automation rules — adding another scheduler instance would be wasteful.

**File:** `dash_backend/predictive/sampler.py`

---

## 7. Predictive→Proactive Integration — Fill Remaining Slots

**Decision:** Predictive risks fill remaining suggestion slots after proactive signals, never competing for the same limit.

**Why:** Proactive signals are immediate and actionable ("you have uncommitted work"). Predictive risks are forward-looking and informational ("disk will fill in 3 days"). Users should see actionable items first, with predictive risks as supplementary context. If predictive risks competed for slots, a high-severity prediction could push out a more actionable suggestion.

**File:** `dash_backend/proactive/engine.py` — `_append_predictive_suggestions()`

---

## 8. Severity-to-Importance Mapping for Predictions

**Decision:** Map prediction severity to proactive importance: `high` → 0.8, `warning` → 0.65, `info` → 0.45.

**Why:** The proactive system uses a 0-1 importance scale. Predictions use severity strings. The mapping ensures that `info` predictions (0.45) are filtered by the default 0.55 threshold — users only see predictions they'd care about. `high` predictions always pass. This was tuned so that the system isn't noisy but doesn't miss critical risks.

**File:** `dash_backend/proactive/engine.py`

---

## 9. Briefing — Top Risk vs. Full Prediction List

**Decision:** Show only the single highest-importance predictive risk in the briefing, not a full list.

**Why:** The briefing is designed to be scannable in under 30 seconds. A single "Top risk:" line with severity, title, and horizon is more useful than a list of 5 predictions. Full predictions are available via `/predictive/risks`. The alternative was showing all predictions, but that would make the briefing too long.

**File:** `dash_backend/proactive/briefing.py` — `_extract_top_risk()`, `format_briefing()`

---

## 10. Briefing Trend Lines — Least-Squares with Confidence

**Decision:** Show trend direction (rising/falling/stable) with a confidence indicator based on history span, using linear regression.

**Why:** Users need to know *what's happening* (RAM is rising) and *how confident* we are (based on 3 days of data vs. 3 hours). The confidence indicator prevents false alarms from short data spans. An alternative was percentage-based ("RAM increased 5%"), but that doesn't indicate direction or predict future behavior.

**File:** `dash_backend/proactive/briefing.py` — `_trend_lines()`

---

## 11. Typed Memory — Five Canonical Types

**Decision:** Define exactly 5 memory types: `personal`, `preference`, `project`, `decision`, `experience`. Use a `type_map` for bidirectional normalization.

**Why:** The spec calls for typed memory (Part 9-10). Five types cover all use cases without being so granular that users are confused about which to use. The type_map allows `"personal"` and `"Personal"` to resolve to the same internal type, preventing bugs from inconsistent casing.

**File:** `dash_backend/memory/service.py`

---

## 12. Remember Decision Flow — Structured Memory Record

**Decision:** `remember_decision()` creates a memory with structured content: "Decision: {decision}. Rationale: {rationale}. Alternatives considered: {alternatives}."

**Why:** Decisions need context to be useful later. A flat string "we chose SQLite" is less useful than "Decision: Use SQLite. Rationale: Faster to iterate. Alternatives: PostgreSQL, MySQL." The structured format enables `get_continue_context()` to parse and present decisions clearly.

**File:** `dash_backend/memory/service.py`

---

## 13. Continue Work Flow — Work Context Records

**Decision:** `record_work_context()` stores task/progress/blockers/next_steps as a single memory, and `get_continue_context()` retrieves the most recent ones filtered by project.

**Why:** "Continue where we left off" needs to know what was being done, what's done, what's blocking, and what's next. Storing this as a single memory (rather than separate fields) keeps the schema simple and allows the LLM to parse it naturally. Filtering by project_id ensures relevant context for multi-project users.

**File:** `dash_backend/memory/service.py`

---

## 14. Memory — Confidence Score (0.0–1.0)

**Decision:** Add a `confidence` float column to Memory, defaulting to 0.5, clamped to [0.0, 1.0].

**Why:** Not all memories are equally reliable. A user-stated preference ("I prefer dark mode") has higher confidence than an inferred fact. The confidence score enables retrieval to weight reliable memories higher. Default 0.5 is neutral — neither trusted nor suspect.

**File:** `dash_backend/db/models/memory.py`

---

## 15. Memory — Project Association

**Decision:** Add a nullable `project_id` UUID column to Memory for project-scoped memories.

**Why:** Users work on multiple projects. A memory about "use TypeScript" is relevant to the TypeScript project but noise for a Python project. Project scoping enables `get_continue_context(project_id)` to return only relevant work state.

**File:** `dash_backend/db/models/memory.py`

---

## 16. Session Lifecycle — Hashed Refresh Tokens

**Decision:** Store refresh tokens as SHA-256 hashes in the database, never raw.

**Why:** If the database is compromised, hashed tokens are useless to attackers. Raw refresh tokens grant full account access. This is a standard security practice (same approach as OAuth 2.0 token storage). The hash is fast enough for the single lookup needed during token refresh.

**File:** `dash_backend/db/models/session.py`, `dash_backend/auth/session_service.py`

---

## 17. Session Revocation — Per-Session and Bulk

**Decision:** Support both `revoke_session(id)` and `revoke_all_sessions()` endpoints.

**Why:** Per-session revocation lets users remove a specific compromised device. Bulk revocation is essential for "I think my account is hacked" scenarios. Both are needed for a complete security story.

**File:** `dash_backend/api/routes/security.py`, `dash_backend/auth/session_service.py`

---

## 18. Privacy Policy — Local-by-Default, Cloud-Opt-In

**Decision:** Clearly state that DASH processes data locally by default, and cloud AI providers only receive data when explicitly configured by the user.

**Why:** This is the honest truth — DASH's default config uses Ollama (local). The privacy policy must accurately reflect actual behavior. Section 3.1 was initially misleading ("All data processing occurs on your local machine" without qualification). Fixed to "By default, DASH processes all data on your local machine. DASH does not send your personal data to any external service unless you explicitly configure a cloud AI provider."

**File:** `dash_backend/legal/privacy.py`

---

## 19. Legal Documents — Backend-Served Markdown

**Decision:** Serve legal documents as Python string constants in `dash_backend/legal/*.py`, exposed via API routes, not as static HTML files.

**Why:** Backend-served documents can be versioned programmatically, tested for accuracy, and served with proper content-type headers. They're part of the application logic, not static assets. An alternative was serving from `/static/`, but that would bypass the API layer and make versioning harder.

**Files:** `dash_backend/legal/privacy.py`, `dash_backend/legal/terms.py`, `dash_backend/legal/accessibility.py`, `dash_backend/api/routes/legal.py`

---

## 20. Legal Endpoints — No Authentication Required

**Decision:** Legal document endpoints (`/legal/*`) require no authentication.

**Why:** Users must be able to read the privacy policy and terms before creating an account. Requiring auth to read the terms would be a catch-22. This matches standard practice for privacy policies (spec Part 35).

**File:** `dash_backend/api/routes/legal.py`

---

## 21. Command Center — Promise.allSettled for Panel Resilience

**Decision:** Use `Promise.allSettled()` instead of `Promise.all()` when fetching Command Center data from 5 endpoints.

**Why:** If one endpoint fails (e.g., backend is partially down), the other panels should still render. `Promise.all()` would fail the entire page. `Promise.allSettled()` lets each panel handle its own loading/error state independently.

**File:** `apps/desktop/src/pages/CommandCenterPage.tsx`

---

## 22. Command Center — Quick-Create Goal Form

**Decision:** Add an inline goal creation form directly in the Command Center, not a modal or separate page.

**Why:** The Command Center is the "at-a-glance" view. Forcing users to navigate to `/planner` to create a goal breaks the flow. An inline form (expand/collapse) keeps the user in context. The form is deliberately minimal (name, priority, deadline) — full editing happens on the goals page.

**File:** `apps/desktop/src/pages/CommandCenterPage.tsx`

---

## 23. Sidebar Badges — Combined Dashboard Badge

**Decision:** Show a single combined badge on the Dashboard nav item (deadlines + suggestions), not separate badges on multiple items.

**Why:** Separate badges on multiple nav items would create visual noise. A single badge on the home icon draws attention to "there's something to look at" without cluttering the sidebar. The badge color shifts based on urgency (deadlines = warning, suggestions only = accent-secondary).

**Files:** `apps/desktop/src/stores/badgeStore.ts`, `apps/desktop/src/components/DASHSidebar.tsx`

---

## 24. Badge Polling — 60-Second Interval

**Decision:** Poll badge counts every 60 seconds, not every 5 seconds like system stats.

**Why:** Badge counts (deadlines, suggestions) change infrequently — goals are created/deleted on human timescales. Polling every 5 seconds would waste resources. 60 seconds is a reasonable balance between freshness and efficiency.

**File:** `apps/desktop/src/stores/badgeStore.ts`

---

## 25. Accessibility — Global :focus-visible Ring, No outline:none

**Decision:** Use a global `:focus-visible` CSS rule for focus rings, and remove all `outline: none` from interactive elements.

**Why:** `outline: none` destroys keyboard accessibility. The global `:focus-visible` rule provides consistent focus indication across all interactive elements. This is the standard WCAG-compliant approach — focus rings appear only for keyboard users, not mouse clicks.

**File:** `apps/desktop/src/index.css`, all page components

---

## 26. Accessibility — Semantic HTML + ARIA Labels

**Decision:** Use `<nav>`, `<main>`, `<aside>`, `<section>`, `<h1>`-`<h3>` semantic elements, and add `aria-label` to all icon-only buttons and form inputs.

**Why:** Screen readers rely on semantic HTML to convey page structure. Icon-only buttons without `aria-label` are invisible to screen readers. Form inputs without labels are inaccessible. This is WCAG 2.1 Level AA compliance (spec Parts 28-35).

**Files:** All desktop app pages and components

---

## 27. Content Audit — No Fake Claims Policy

**Decision:** Ensure every user-facing claim (plugin descriptions, analytics stats, legal documents) corresponds to real implementation, with no placeholder text, mock data, or unsupported statistics.

**Why:** Fake claims erode trust. If the Plugins page says "Memory Engine" exists, the `dash_backend/memory/` directory must exist with real code. If the privacy policy says "no cookies," DASH must not use cookies. This is fundamental to spec Parts 37-40.

**Files:** All public-facing content

---

## 28. Orbitron Font — Google Fonts CDN (SIL OFL)

**Decision:** Load the Orbitron font from Google Fonts CDN for the boot animation, disclosed in the Privacy Policy.

**Why:** Orbitron gives the boot screen its sci-fi aesthetic. The SIL Open Font License permits free commercial use. Google Fonts CDN is reliable and widely cached. The alternative was self-hosting the font, but that would add ~50KB to the bundle for a purely cosmetic element. The privacy policy was updated to honestly disclose this external resource.

**Files:** `apps/desktop/src/components/BootScreen.css`, `apps/desktop/src/components/JarvisHUD.css`, `dash_backend/legal/privacy.py`

---

## 29. Electron — HashRouter for Desktop App

**Decision:** Use `HashRouter` instead of `BrowserRouter` for the React routing in Electron.

**Why:** Electron serves files from `file://` protocol. `BrowserRouter` requires a server to handle fallback routes. `HashRouter` uses URL fragments (`/#/chat`) that work without a server, making it the standard choice for Electron + React apps.

**File:** `apps/desktop/src/App.tsx`

---

## 30. WebSocket Client — Generation-Based Stale Socket Detection

**Decision:** Use a `socketGeneration` counter to detect stale WebSocket connections during reconnection, rather than comparing socket references.

**Why:** During rapid reconnection (network flap), multiple `new WebSocket()` calls may be in flight. A generation counter ensures only the most recent connection handles messages, preventing race conditions where an old socket's messages arrive after a new socket is established.

**File:** `apps/desktop/src/lib/wsClient.ts`

---

## 31. Supabase Outbox — Column Filtering + Tombstone Deletes

**Decision:** The outbox delivery worker now filters each payload to the columns that actually exist in the cloud tables (`_TABLE_COLUMNS` in `sync/supabase_outbox_worker.py`), injects NOT-NULL defaults (`status`, `created_at`, `updated_at`) for legacy events, and hard local deletes (`delete_goal`) are mirrored as `tombstone` operations (cloud soft-delete via `deleted_at`) instead of an unsupported `"delete"` operation.

**Why:** Local goal/task payloads carry `priority`, `deadline`, and `depends_on`, but the cloud `dash_projects`/`dash_tasks` tables deliberately omit those columns — PostgREST rejects unknown columns with HTTP 400, so 296+ events were dead-lettering and local↔cloud sync silently stalled. Rather than migrating the cloud schema (breaking change for existing rows), delivery strips unknown keys at the boundary — the outbox contract already treats payloads as opaque delivery envelopes. The `delete` operation was never part of the outbox contract (`upsert`/`tombstone` only); enqueuing it created events the worker could never deliver.

**Files:** `apps/backend/dash_backend/sync/supabase_outbox_worker.py`, `apps/backend/dash_backend/executive/service.py` (`delete_goal`), `apps/backend/tests/test_supabase_outbox.py` (new regression test `test_delivery_strips_columns_missing_from_cloud_schema`)

**Result:** Outbox went from 296 dead-lettered / 70 stuck-invalid to **1,416 completed, 0 pending, 0 dead-lettered** — verified live against the real Supabase project.

**Follow-up (same day):** Sustained operation exposed a second flaw — an upsert-based tombstone INSERTed a bare cloud row when the record had never been synced, violating `dash_tasks.project_id` NOT NULL. Tombstones now use PATCH semantics (`update().match({id, owner_id})`), making them no-ops for unknown cloud records. Regression test: `test_tombstone_for_never_synced_record_is_a_noop`. Verified stable at 1,452 completed / 0 dead-lettered under sustained load.

---

## 32. Workflow Builder — Zero-Dependency SVG Canvas + JSON State File

**Decision:** Built the drag-and-drop workflow builder as two pieces: (1) a self-contained `WorkflowCanvas` React component (drag nodes, drag port→port to wire edges, SVG bezier paths, grid snapping, Delete-key support, pan) using native pointer events and SVG — **no react-flow/React Flow library**; (2) a redesigned `AutomationPage` with a Rules | Builder tab split, a node palette (Trigger / Action / If-Else / Delay), and a properties panel. Backend gained `PUT /enhanced/workflows/{id}` (route + `WorkflowUpdateRequest`) and the engine now persists **custom** workflows to `%LOCALAPPDATA%\DASH\workflow_state.json` (override: `DASH_WORKFLOW_STATE`), reloaded on startup; templates stay code-seeded and immutable.

**Why:**
- *No React Flow:* the canvas needs ~450 lines for our scope (4 node types, 2 branch ports, one-edge-per-port rule). React Flow drags in ~50 dependencies, its own styling system that fights the DASH tokens, and license considerations — not worth it for a single-screen feature. Native pointer capture gives us grid snapping and port-hit logic exactly matching the backend's edge model.
- *If/Else as one node with TRUE/FALSE ports (not separate branch nodes):* mirrors the backend edge model (`edge.condition = "true"|"false"` from the existing template schema), so the UI saves exactly what the engine consumes — no translation layer.
- *JSON file over SQLite:* the predictive sampler already uses this exact pattern (`predictive_state.json`); workflows are few, read-mostly, and small — a table + migration for <10 objects is overhead. State file survives backend restarts (the in-memory engine silently lost user workflows on every restart — discovered when the test workflow vanished after a task restart).
- *One outgoing edge per port:* prevents accidental multi-fan-out that the engine's sequential executor can't honor; dragging a new wire to an occupied port replaces the old edge (predictable, like n8n).

**Files:** `apps/desktop/src/components/WorkflowCanvas.tsx` (new), `apps/desktop/src/pages/AutomationPage.tsx` (rewritten, tabs), `apps/desktop/src/lib/api.ts` (`workflows` client + types), `apps/backend/dash_backend/api/routes/enhanced_features.py` (PUT route), `apps/backend/dash_backend/services/workflow_builder.py` (persistence), `apps/backend/tests/test_workflow_builder_canvas.py` (7 tests).

**Verified:** live E2E against running backend — create → PUT if/else graph (4 nodes, TRUE/FALSE edges) → reload → execute (`completed`, nodes n1→n4) → delete; engine restarted via scheduled task and reloaded state from disk. Desktop `tsc -b` + vite build clean; backend suite 446 passed.

## 33. UI Pages for Backend Feature Services (Knowledge Graph, Model Selector, Marketplace, Settings)

**Date:** 2026-09-11

**Context:** The backend already exposed `/enhanced/*` endpoints for shortcuts, sounds, DND, tokens, activity, plugins, knowledge-graph, and model hot-swap — but the desktop UI either didn't exist (Model Selector), pointed at the wrong URLs (Plugins fetched `/plugins`, which no route serves), or ignored the endpoints entirely (Settings had no Shortcuts/Sounds/DND sections; Knowledge had no graph).

**Decision & reasons:**

- *Knowledge graph as a force-directed `<canvas>` (no graph library):* ~450 lines of physics (repulsion + springs + centering) covers our ≤250-node graphs at 60fps; a library (react-force-graph, d3-force + renderer) adds heavyweight deps for a single screen. Canvas over SVG because node counts can reach 250 with O(n²) repulsion per frame — SVG DOM updates would stutter. Node type colors, mention-count sizing, click-for-details, drag/pin, zoom/pan, and type filters included.
- *`build_graph_from_memories` co-mention model:* entities extracted per memory (existing NER heuristics + tags as first-class `tag` nodes) get `co_mentioned` edges to every other entity in the same memory. Idempotent (mention_count bumps instead of duplicate nodes; `_has_edge` prevents duplicate links). Seeded via `POST /enhanced/knowledge-graph/rebuild` (reads the 500 most recent memories) so users generate the graph from *their own data* rather than a canned demo. State persists to `%LOCALAPPDATA%\DASH\knowledge_graph_state.json` (same pattern as workflow/predictive state).
- *Model Selector as a new page (`/models`):* the hot-swap service existed with `/enhanced/models/available|swap|history` but no UI. Provider filter chips + tier badges + swap history timeline; active model highlighted with provider color. Swap is a query-param POST matching the existing route signature.
- *Plugins page rewired to the real marketplace:* `/enhanced/plugins/marketplace` + `/installed`, with install/uninstall/toggle actions and category filters. The old page fetched a nonexistent `/plugins` route and silently rendered nothing. Kept the "Built-in Modules" grid as a second tab.
- *Settings: Shortcuts/Sounds/DND sections:* wire the existing `shortcut_manager`, `notification_sounds`, `dnd_manager` services. Two route gaps found and filled: `POST /enhanced/sounds/toggle` (service had `toggle()` but no route) and `POST /enhanced/dnd/exception/remove` (service had `remove_exception()` but no route). Inline editing for shortcuts (keyboard-first: Enter saves, Escape cancels), switches use `role="switch"` + `aria-checked` for a11y.
- *Analytics activity section:* surfaces `/enhanced/activity/productivity` + `/activity/daily` as a 4-stat row (score, tasks completed, messages sent, events today) — the endpoints existed but nothing called them. Section renders only when the backend responds, so no fake data on failure.

**Files:** `apps/desktop/src/components/KnowledgeGraphView.tsx` (new), `apps/desktop/src/pages/KnowledgePage.tsx` (rewritten, Graph|Entries tabs), `apps/desktop/src/pages/ModelSelectorPage.tsx` (new), `apps/desktop/src/pages/PluginsPage.tsx` (rewritten, marketplace), `apps/desktop/src/pages/AnalyticsPage.tsx` (activity row), `apps/desktop/src/pages/SettingsPage.tsx` (3 new sections), `apps/desktop/src/App.tsx` (`/models` route), `apps/backend/.../enhanced_features.py` (3 new routes), `apps/backend/.../knowledge_graph.py` (memory seeding + persistence), `apps/backend/tests/test_knowledge_graph_seed.py` + `tests/test_enhanced_ui_routes.py` (11 tests).

**Verified:** 451 backend tests pass (full suite); desktop `tsc -b` + vite build clean with all page chunks emitted; KG seeding round-trip (9 entities → 16 edges from 2 memories, persisted across engine restart) tested live.
## 34. Real Security Services — TOTP 2FA, Encrypted Vault/Chat, Biometrics, PII Anonymization

**Date:** 2026-09-11

**Context:** The existing `security_hardening.py` services were stubs with dangerously misleading behavior: TOTP `verify()` accepted *any* code ("simplified - real impl uses pyotp"), the vault stored plaintext in memory while the UI claimed encryption, the messenger stored plaintext with an `"encrypted": true` flag, and everything was keyed by `id(user)` — a Python object address that changes every request/restart. The PasswordManagerPage also used unauthenticated raw `fetch`.

**Decision & reasons:**

- *Hand-rolled RFC 6238 on `cryptography` instead of adding pyotp:* HOTP is ~10 lines of HMAC-SHA1 (RFC 4226) and we already ship `cryptography` (used by the outbox). One less dependency for a standardized algorithm; window drift (±1) and replay protection (code+counter memory) match authenticator-app behavior.
- *AES-256-GCM for vault and chat:* authenticated encryption — tampering with a ciphertext fails decryption instead of silently returning garbage. Vault entries derive per-entry keys via HKDF (info = entry id) from the master secret, so one leaked ciphertext doesn't expose siblings; AAD binds each ciphertext to its entry id.
- *Key persistence without a passphrase (v1):* the master/root keys are random per install and stored beside the state file (`vault_master.key`, `messenger_root.key`) — this protects against other processes/users reading the DB, NOT against an attacker with full disk access. A passphrase-derived (PBKDF2, 600k iterations) master is the documented upgrade path; the constructor already accepts `master_secret`.
- *Anonymization keeps analytics usable:* deterministic HMAC-SHA256 pseudonyms (`[EMAIL_<12hex>]`) mean the same entity maps to the same token within a deployment — frequency analysis still works — while remaining unlinkable across deployments (per-deployment pepper). Phone masking keeps the last 4 digits for human matching. Pattern order matters: specific types first, greedy phone matcher last with `.` excluded from its char class so IPs/cards are never swallowed (a real bug found in testing).
- *Biometrics as challenge/response, data stays local:* the backend never receives biometric data. The desktop shell prompts the platform authenticator (Electron `systemPreferences` / Touch ID; Windows Hello via the platform credential flow), and the backend only issues single-use, 120s-TTL challenges and records the pass/fail outcome with a full audit log. Enrollment is gated on availability reported by the shell.
- *Stable user identity:* all security routes now key on `str(user.id)` (the DB UUID) instead of `id(user)` — previously enrollments silently vanished across restarts.
- *Desktop wiring:* PasswordManagerPage rewired from unauthenticated raw `fetch` to `authFetch` with the real contract (`fields` dict, categories, PATCH favorite, delete, generator). SecurityHardeningPage gains a Biometric tab (enroll/test/revoke through the Electron bridge) and the 2FA tab now requires a real code verify+confirm before enable.

**Files:** `apps/backend/dash_backend/services/security_hardening.py` (rewritten, ~680 lines), `apps/backend/dash_backend/api/routes/phase2_features.py` (biometric routes, vault PATCH/DELETE/GET, stable user ids), `apps/desktop/electron/main.ts` + `preload.ts` + `src/electron.d.ts` (biometric IPC), `apps/desktop/src/pages/PasswordManagerPage.tsx` (rewired), `apps/desktop/src/pages/SecurityHardeningPage.tsx` (biometric tab, real 2FA verify), `apps/backend/tests/test_security_hardening.py` (20 tests) + `tests/test_security_routes.py` (5 route tests).

## 35. Seven Feature Pages Wired to Real Services (Email, Calendar, Voice, Browser, Collaboration, Prompts, Infrastructure)

**Date:** 2026-09-11

**Context:** All seven pages existed but shared a common defect pattern: on any `fetch` failure they populated state with **fabricated sample data** (fake inbox emails, fake events, fake memos, fake cache stats showing 93.4% hit rate) — so a dead backend looked identical to a working one. Individually: EmailPage's mark-read posted to the wrong endpoint (no-op), Star/Archive/Delete buttons were decorative; CalendarPage created zero-duration events (`end = start`); BrowserPage bypassed the real browser service entirely and drove `/ai-os/execute` with a "Browse and summarize" prompt, keeping session history only in React state; CollaborationPage fetched comments for a hardcoded `mem_0` entity that never exists; VoiceCommandsPage's memo recorder saved a hardcoded 30s duration with no actual capture; the workspace/comment creation routes still keyed owners by `id(user)`.

**Decision & reasons:**

- *Fake-data fallbacks removed everywhere; explicit error banners instead:* a page must show "service unreachable" rather than plausible lies. Every list now renders real empty states when the backend genuinely has nothing.
- *Browser page on the real service:* Tabs / Bookmarks / History tabs over `/features/browser/tabs|bookmarks|history|stats`, open via `POST /browser/tabs/open` (URL normalization: scheme added if missing), close via new `POST /browser/tabs/close` route (service method existed, route didn't), external-link button for system-browser handoff.
- *Email:* new `POST /features/email/mark-read` route wired to the existing service method; account connect form using the existing `POST /email/accounts`; Star/Archive are honest local actions (service has no folder model yet) instead of silent no-ops; Delete removed rather than faked.
- *Calendar:* new events default to **1-hour duration** computed client-side (the create dialog had no end field; zero-length events broke the month-view display contract); create surfaces real failures.
- *Collaboration:* deleted the phantom `mem_0` activity feed — the backend's activity feed service isn't user-reachable yet, so the panel showed hardcoded chats; workspace cards show real owner/member data; new `DELETE /features/workspaces/{id}` route (service method existed unexposed); workspace `create`/comment routes now use stable `str(user.id)`.
- *Prompt Studio:* template cards are now **create-from-template** actions (prefill the dialog) instead of dead clicks; Test button copies the prompt and points the user at Chat; copy uses the clipboard with feedback.
- *Voice Commands:* recording toggle is explicit that browser speech capture isn't wired to this page yet — memo save only fires when the user typed a transcript (no more fabricated 30s memos); command list comes from the real registry.
- *Infrastructure:* 15s auto-refresh (it's a status page), honest hit-rate from the real `CacheService`, and the health panel renders the actual registered checks (empty until services register checks — previously three fake "healthy" rows).

**Files:** `apps/desktop/src/pages/{EmailPage,CalendarPage,BrowserPage,VoiceCommandsPage,CollaborationPage,PromptStudioPage,InfrastructurePage}.tsx`, `apps/backend/dash_backend/api/routes/phase2_features.py` (email mark-read, browser tab close, workspace delete, stable owner ids), `apps/backend/tests/test_feature_page_routes.py` (3 tests).

**Verified:** 482 backend tests pass; desktop `tsc -b` + vite build clean with all 7 page chunks emitted; workspace create→delete round-trip and browser open→close tested in-process.

**Verified:** 25 new tests pass; full backend suite 479 passed; desktop `tsc -b` + vite build clean; ciphertext-at-rest asserted in tests (disk files must not contain plaintext); TOTP verified against independently computed RFC 4226 codes including drift window and replay rejection.


## 36. SQLite Persistence for All Feature Services (local_store.py)

**Decision:** A single shared SQLite database (`%LOCALAPPDATA%\DASH\dash_local.db`, override with `DASH_LOCAL_STORE`) now backs every feature service that previously lived only in process memory: email accounts/messages/rules, calendars/events/reminders, contacts, voice memos, browser tabs/bookmarks/history/summaries, workspaces/members/comments/activity, prompts/evaluations/learning, model hot-swap history + active model, plugin installs/permissions/ratings, custom shortcuts, sounds settings, DND state, and biometric enrollments/audit.

**Why this approach:**
- *Why SQLite + one shared file, not per-service JSON:* the repo already had two persistence idioms — raw `sqlite3` (device_state_manager) and ad-hoc JSON files (workflow_state.json, knowledge_graph_state.json, predictive_state.json). JSON files race when two services write, have no schema evolution, and scattered files are undeletable as a unit. One SQLite file with a `schema_migrations` table gives real versioned migrations that run automatically on first connection — i.e., at backend startup when service singletons import. Idempotent by construction (applied versions recorded; re-open is a no-op).
- *Why document rows (`id, seq, data` JSON):* the services are dict-oriented (lists of dicts with `seq`-style ordering). Persisting JSON documents kept every service's in-memory semantics *exactly* — no dataclass refactors, no ORM coupling — while gaining durability. Where queries need filtering (emails by folder, comments by entity), real columns + indexes were added.
- *Why WAL + one connection per store with an RLock:* FastAPI runs sync route bodies on a worker pool, so concurrent access is real; WAL keeps the read-heavy path cheap, the lock keeps writes serialized without per-call connection churn.
- *Why kv helpers (`kv_get/kv_set`):* shortcut/sound/DND state is a handful of small config blobs, not queryable documents — a key-value table is the honest shape.
- *What deliberately did NOT persist:* biometric challenges (single-use, 120s TTL — ephemeral by design) and messenger/TOTP secrets (already persisted via their own encrypted files from #34).
- *Len-based IDs removed:* services that generated `email_0`, `ws_1`-style ids got collision-free `prefix_<12hex>` ids, because persisted data makes "next integer = count" ids collide across restarts.

**Migration pattern (services):** constructor takes `store: Optional[LocalStore] = None`, defaults to `LocalStore.instance()`; hydrates in-memory lists from the store in `__init__`; every mutating method writes through (`put_doc`/`delete_doc`/`kv_set`) alongside the in-memory update. Tests construct with an explicit temp-path store.

**Files:** `apps/backend/dash_backend/services/local_store.py` (new), `email_calendar.py`, `voice_browser.py`, `collaboration.py`, `advanced_ai.py`, `model_ensemble.py`, `plugin_service.py`, `shortcuts_service.py`, `security_hardening.py` (biometric), `tests/test_local_store_persistence.py` (new — 14 tests).

**Verified:** 14 persistence tests prove every migrated service survives a simulated restart (fresh instance on the same file sees the data), migrations are idempotent, and the no-arg production constructor path actually hits the shared file. Full suite: **544 passed**.

**Pre-existing flaky test fixed:** `TestPushNotificationService` failed whenever the suite ran during the push service's default quiet hours (23:00–07:00 UTC) because `send()` defers notifications at night — time-of-day-dependent test outcome. The tests now pin `_is_quiet_hours` off (setup/teardown) instead of depending on wall clock.
