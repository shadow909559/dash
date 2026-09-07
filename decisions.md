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
