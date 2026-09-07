import { PageLayout } from "@/components/PageLayout";
import {
  Cpu,
  HardDrive,
  Wifi,
  Database,
  Shield,
  Zap,
  Brain,
  Workflow,
} from "lucide-react";

export function ProductPage() {
  return (
    <PageLayout
      title="What is DASH?"
      description="DASH is a personal AI operating system, not a chatbot. It understands your environment, remembers context, and takes action."
    >
      <section className="section--sm">
        <div className="container">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 32,
            }}
          >
            <div>
              <h2 style={{ marginBottom: 16 }}>Not a chatbot</h2>
              <p style={{ lineHeight: 1.7 }}>
                Most AI tools are stateless. You ask a question, get an answer,
                and start over. DASH is different. It maintains long-term memory,
                understands your projects, tracks your goals, and proactively
                suggests improvements.
              </p>
              <p style={{ marginTop: 12, lineHeight: 1.7 }}>
                When you say "continue where we left off," DASH knows what you
                were working on, what decisions were made, and what the next
                steps are.
              </p>
            </div>
            <div>
              <h2 style={{ marginBottom: 16 }}>Runs locally</h2>
              <p style={{ lineHeight: 1.7 }}>
                DASH runs on your Windows PC. Your conversations, memories, and
                data stay on your machine. By default, DASH uses Ollama for AI
                inference, which runs entirely locally. Cloud AI providers
                (Groq, Gemini, OpenAI) are available as optional fallbacks.
              </p>
              <p style={{ marginTop: 12, lineHeight: 1.7 }}>
                No data leaves your device unless you explicitly configure a
                cloud provider.
              </p>
            </div>
          </div>
        </div>
      </section>

      <hr className="divider" style={{ maxWidth: "var(--max-width)", margin: "0 auto" }} />

      <section className="section--sm">
        <div className="container">
          <h2 className="mb-24">System components</h2>
          <div className="grid grid--4">
            {[
              {
                icon: Cpu,
                title: "Desktop App",
                desc: "Electron + React interface with 20+ pages, WebSocket real-time communication, and system integration.",
              },
              {
                icon: Database,
                title: "Backend",
                desc: "FastAPI Python backend with SQLite, 25+ API routers, background workers, and event bus.",
              },
              {
                icon: Brain,
                title: "AI Layer",
                desc: "Multi-provider LLM routing, local Ollama inference, context engine, and personality system.",
              },
              {
                icon: Workflow,
                title: "Agent System",
                desc: "Orchestrated multi-agent execution with tool chains, decision engine, and approval controls.",
              },
              {
                icon: HardDrive,
                title: "Memory Engine",
                desc: "Episodic and semantic memory with embeddings, typed categories, and hybrid search.",
              },
              {
                icon: Shield,
                title: "Security",
                desc: "Device-token authentication, session management, audit logging, and privacy controls.",
              },
              {
                icon: Wifi,
                title: "Sync Layer",
                desc: "Desktop-to-mobile sync via WebSocket with offline support and conflict resolution.",
              },
              {
                icon: Zap,
                title: "Automation",
                desc: "Scheduled tasks, rule-based triggers, and autonomous background operations.",
              },
            ].map((item) => (
              <div key={item.title} className="card">
                <item.icon size={18} style={{ color: "var(--accent)", marginBottom: 12 }} />
                <h4 style={{ marginBottom: 8 }}>{item.title}</h4>
                <p className="card__desc">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
