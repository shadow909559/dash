import { PageLayout } from "@/components/PageLayout";

export function ArchitecturePage() {
  return (
    <PageLayout
      title="Architecture"
      description="How DASH is built. Every component exists for a reason."
    >
      <section className="section--sm">
        <div className="container">
          {/* System Diagram */}
          <div
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              padding: 32,
              marginBottom: 48,
              overflow: "auto",
            }}
          >
            <pre
              style={{
                fontFamily: "var(--font-mono)",
                fontSize: 12,
                lineHeight: 1.5,
                color: "var(--text-secondary)",
                margin: 0,
                background: "transparent",
                border: "none",
                padding: 0,
                minWidth: 600,
              }}
            >
{`┌─────────────────────────────────────────────────────────────┐
│                    DASH SYSTEM ARCHITECTURE                  │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────┐    WebSocket     ┌──────────────────┐    │
│  │  Desktop App  │◄───────────────►│  Backend (Python) │    │
│  │  (Electron)   │                 │  FastAPI + WS     │    │
│  └──────────────┘                  └────────┬─────────┘    │
│                                              │              │
│  ┌──────────────┐    WebSocket     ┌────────▼─────────┐    │
│  │  Android App  │◄───────────────►│   LLM Providers   │    │
│  │  (Kotlin)     │                 │  ┌─────────────┐  │    │
│  └──────────────┘                  │  │ Ollama (Local)│  │    │
│                                     │  │ 1B - 70B     │  │    │
│  ┌──────────────┐                  │  ├─────────────┤  │    │
│  │  Cloud Relay  │◄───────────────►│  │ Groq (Cloud) │  │    │
│  │  (ngrok)      │                 │  │ Llama 3.3    │  │    │
│  └──────────────┘                  │  ├─────────────┤  │    │
│                                     │  │ Gemini (Cloud)│  │    │
│  ┌──────────────┐                  │  │ Flash/Pro     │  │    │
│  │  Local DB     │                 │  └─────────────┘  │    │
│  │  (SQLite)     │                  └──────────────────┘    │
│  └──────────────┘                                           │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Event Bus    │  │  Memory      │  │  Predictive  │     │
│  │  (pub/sub)    │  │  Engine      │  │  Engine      │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐     │
│  │  Proactive    │  │  Context     │  │  Orchestrator│     │
│  │  Engine       │  │  Engine      │  │  (agents)    │     │
│  └──────────────┘  └──────────────┘  └──────────────┘     │
│                                                             │
└─────────────────────────────────────────────────────────────┘`}
            </pre>
          </div>

          {/* Components */}
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
              gap: 24,
            }}
          >
            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Desktop App</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                Electron + React + TypeScript. Custom frameless window with
                sci-fi HUD. 20+ pages covering every system capability.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                Electron 35 · React 19 · Vite · Zustand
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Backend</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                FastAPI with async Python. 25+ API routers, WebSocket server,
                background workers, and event bus. SQLite for storage.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                FastAPI · SQLAlchemy · Alembic · asyncio
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>AI / LLM Layer</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                Multi-provider routing with fallback. Local Ollama for privacy,
                cloud providers (Groq, Gemini, OpenAI) for capability.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                Ollama · Groq · Gemini · OpenAI · Anthropic
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Memory Engine</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                Hybrid search combining semantic embeddings (nomic-embed-text)
                with lexical matching. Typed categories with confidence scoring.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                Embeddings · Cosine similarity · Hybrid retrieval
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Proactive Engine</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                Detects issues from environment snapshots. Threshold gating,
                cooldown, dedup, and quiet hours. Merges with predictive risks.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                Signal detection · Cooldown gating · Importance scoring
              </div>
            </div>

            <div className="card">
              <h3 style={{ marginBottom: 12 }}>Predictive Engine</h3>
              <p className="card__desc" style={{ marginBottom: 12 }}>
                Device metric trend analysis using least-squares regression.
                Predicts disk exhaustion, RAM pressure, and project health.
              </p>
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 12,
                  color: "var(--text-muted)",
                }}
              >
                NumPy polyfit · Rolling window · R² confidence
              </div>
            </div>
          </div>

          {/* Communication */}
          <div style={{ marginTop: 48 }}>
            <h2 className="mb-24">Communication</h2>
            <div className="grid grid--3">
              <div className="card">
                <h4 style={{ marginBottom: 8 }}>WebSocket</h4>
                <p className="card__desc">
                  Real-time bidirectional communication between desktop/mobile
                  and backend. Authenticated via device tokens. Supports chat
                  streaming, system events, and orchestration commands.
                </p>
              </div>
              <div className="card">
                <h4 style={{ marginBottom: 8 }}>REST API</h4>
                <p className="card__desc">
                  25+ authenticated endpoints for CRUD operations, system
                  control, and data access. All endpoints require valid device
                  tokens or session authentication.
                </p>
              </div>
              <div className="card">
                <h4 style={{ marginBottom: 8 }}>Event Bus</h4>
                <p className="card__desc">
                  Internal publish/subscribe system for decoupled component
                  communication. Enables proactive detection, notifications,
                  and cross-system coordination.
                </p>
              </div>
            </div>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
