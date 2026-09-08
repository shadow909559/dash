# DASH — Enhanced Features Added

## New Backend Services (9 services, 84 API routes)

### 1. Export Service (`services/export_service.py`)
- `ChatExporter` — Export conversations as Markdown, JSON, CSV, or HTML
- `MemoryExporter` — Export memories as Markdown, JSON, or CSV
- `SettingsExporter` — Export/import all user settings as JSON
- `DataExporter` — Full data export (memories, conversations, settings, goals, notifications)

### 2. Desktop Integration Service (`services/desktop_integration.py`)
- `HotkeyRegistry` — Register, unregister, and list global keyboard shortcuts
- `TrayActions` — System tray quick actions with recent history
- `WindowSnap` — 12 window snap positions (halves, thirds, quarters, center)

### 3. Shortcuts Service (`services/shortcuts_service.py`)
- `ShortcutManager` — 30+ customizable keyboard shortcuts with search
- `DNDManager` — Do Not Disturb mode with schedule, exceptions, and history
- `NotificationSounds` — 9 sound options per event type with volume control
- `SettingsSearch` — Full-text search across 30+ settings with categories

### 4. Analytics Service (`services/analytics_service.py`)
- `TokenTracker` — Token usage and cost tracking per provider, per day, with budget alerts
- `ActivityDashboard` — User activity tracking, daily/weekly summaries, productivity scoring
- `PerformanceProfiler` — Operation timing with p50/p95/p99 percentiles and slow operation detection
- `ErrorLogViewer` — Structured error logs with filtering, search, and stats

### 5. Memory Enhanced Service (`services/memory_enhanced.py`)
- `MemoryTagManager` — Create/delete tags, tag/untag memories, tag cloud generation
- `MemoryRelationshipManager` — 12 relationship types between memories (causes, contradicts, etc.)
- `MemoryAnalytics` — Creation stats, growth rates, access patterns
- `MemoryConsolidation` — Fuzzy duplicate detection, forgetting curve, memory merging

### 6. Workflow Builder Service (`services/workflow_builder.py`)
- `WorkflowEngine` — Create, update, delete, duplicate workflows with node/edge graphs
- 6 workflow templates (daily briefing, backup, email-to-memory, weekly report, code review, smart reminder)
- Cron schedule triggers, webhook triggers, execution history with stats

### 7. Plugin Service (`services/plugin_service.py`)
- `PluginRegistry` — Marketplace with 8 pre-built plugins, install/uninstall/toggle
- 24 granular permission types (memory, file, network, notification, etc.)
- Plugin ratings, stats, and permission management

### 8. Knowledge Graph Service (`services/knowledge_graph.py`)
- `KnowledgeGraph` — Entity extraction, relationship tracking, graph visualization
- `ChainOfThoughtVisualizer` — Multi-step reasoning with confidence per step
- `HallucinationDetector` — Cross-reference claims against known facts, detect unsupported claims
- `SourceVerifier` — Verify cited sources against stored sources with trust scoring

### 9. Model Ensemble Service (`services/model_ensemble.py`)
- `ModelEnsemble` — 4 strategies (best-of-N, vote, cascade, blend) with model weights
- `ConfidenceScorer` — 5-signal confidence scoring (length, sources, hedging, specificity, context)
- `ConversationBranching` — Fork conversations at any point, compare branches
- `ModelHotSwap` — 7 models available, hot-swap without losing context, swap history

---

## API Routes (84 new endpoints under `/api/v1/enhanced/`)

### Export (4 routes)
- `POST /export/chat` — Export conversation
- `POST /export/memory` — Export memories
- `POST /export/settings` — Export settings
- `POST /export/all` — Full data export

### Shortcuts & DND (7 routes)
- `GET/POST /shortcuts` — Get/update shortcuts
- `GET/POST /dnd` — DND state, toggle, schedule, exceptions

### Sounds & Settings (4 routes)
- `GET/POST /sounds` — Notification sound settings
- `GET /settings/search` — Search all settings

### Analytics (12 routes)
- `GET /tokens/*` — Token usage (today, week, month, budget)
- `GET /activity/*` — Activity (recent, daily, weekly, productivity)
- `GET /performance/*` — Performance (stats, slow operations, summary)
- `GET /errors/*` — Error logs (list, stats)

### Workflows (9 routes)
- `GET/POST/DELETE /workflows/*` — CRUD, execute, duplicate, schedule

### Plugins (6 routes)
- `GET/POST /plugins/*` — Marketplace, installed, install, uninstall, toggle, permissions

### Knowledge Graph (7 routes)
- `GET/POST /knowledge-graph/*` — Graph, entities, edges, extract, search, node details

### Reasoning (4 routes)
- `POST /reasoning/chain` — Create reasoning chain
- `POST /reasoning/chain/{id}/step` — Add reasoning step
- `GET /reasoning/chains` — List chains
- `GET /reasoning/chain/{id}/tree` — Get tree view

### Verification (6 routes)
- `POST /verification/hallucination-check` — Check response for hallucinations
- `POST/GET /verification/facts` — Manage known facts
- `POST/GET /verification/sources` — Manage and verify sources
- `POST /verification/verify` — Verify a specific claim

### Ensemble & Models (7 routes)
- `GET/POST /ensemble/*` — Config, strategy, history, stats
- `GET /confidence/*` — Average and distribution
- `GET/POST /models/*` — Available, swap, history

### Branches (5 routes)
- `GET/POST/DELETE /branches/*` — List, fork, get, delete, compare

### Desktop Integration (4 routes)
- `GET/POST /desktop/hotkeys` — Get/register hotkeys
- `GET /desktop/tray/actions` — Tray quick actions
- `GET /desktop/snap/positions` — Window snap positions

---

## What Each Feature Does

### Token Cost Tracker
Every AI API call is logged with provider, model, input/output tokens, and calculated cost. Users can see daily, weekly, and monthly usage with per-provider breakdowns and budget alerts.

### Workflow Builder
Visual node/edge workflows with trigger → condition → action flows. Pre-built templates for common tasks (daily briefing, email processing, code review). Cron scheduling and webhook triggers for automation.

### Plugin Marketplace
8 pre-built plugins (Weather, Todoist, GitHub, Notion, Slack, Code Runner, Image Gen, Zapier) with granular permission model. Each plugin runs sandboxed with only the permissions it needs.

### Knowledge Graph
Auto-extracts entities (people, projects, tech, concepts) from conversations and memories. Builds a relationship graph showing how concepts connect. Supports fuzzy search across all entities.

### Chain of Thought
Step-by-step reasoning visualization with confidence scores per step. Shows the AI's thinking process as a tree diagram with evidence and conclusion.

### Hallucination Detection
Cross-references AI responses against a database of known facts. Flags unsupported claims and partial mismatches. Provides a risk level (low/medium/high) for every response.

### Model Ensemble
Runs multiple AI models simultaneously and picks the best response. Four strategies: best-of-N (pick highest scored), vote (majority), cascade (cheap first, escalate), blend (weighted average). Hot-swap between 7 models without losing conversation context.

### Conversation Branching
Fork a conversation at any message to explore alternative paths. Compare branches side-by-side. Keep all branches with full history.

### Confidence Scoring
Every AI response is scored on 5 signals: length, source citations, hedging language, specificity, and context relevance. Provides a confidence level (high/medium/low) with explanation.
