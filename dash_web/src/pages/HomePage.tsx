import { Link } from "react-router-dom";
import {
  MessageSquare,
  Brain,
  Code2,
  Search,
  Workflow,
  Bot,
  Calendar,
  Shield,
  Monitor,
  ArrowRight,
  Github,
  Download,
  ExternalLink,
  CheckCircle,
} from "lucide-react";
import { config } from "@/lib/config";
import { PageLayout } from "@/components/PageLayout";

const CAPABILITIES = [
  {
    icon: MessageSquare,
    title: "Chat",
    desc: "Multi-mode conversation with specialized agents for coding, planning, research, and execution.",
    status: "available" as const,
  },
  {
    icon: Brain,
    title: "Memory",
    desc: "Long-term episodic and semantic memory with typed categories, confidence scores, and project association.",
    status: "available" as const,
  },
  {
    icon: Code2,
    title: "Coding",
    desc: "Code generation, explanation, refactoring, and debugging across multiple languages.",
    status: "available" as const,
  },
  {
    icon: Search,
    title: "Research",
    desc: "Web research with source tracking and structured summaries.",
    status: "available" as const,
  },
  {
    icon: Workflow,
    title: "Automation",
    desc: "Rule-based automation with scheduled triggers and custom actions.",
    status: "available" as const,
  },
  {
    icon: Bot,
    title: "Agents",
    desc: "Specialized AI agents with tool chains, orchestration, and approval controls.",
    status: "available" as const,
  },
  {
    icon: Calendar,
    title: "Planning",
    desc: "Goal and task management with deadlines, priorities, and progress tracking.",
    status: "available" as const,
  },
  {
    icon: Shield,
    title: "Approvals",
    desc: "User-in-the-loop approval controls for consequential actions.",
    status: "available" as const,
  },
  {
    icon: Monitor,
    title: "Computer Control",
    desc: "Desktop automation, window management, file operations, and system interaction.",
    status: "experimental" as const,
  },
];

export function HomePage() {
  return (
    <PageLayout>
      {/* Hero */}
      <section
        style={{
          padding: "80px 0 60px",
          textAlign: "center",
        }}
      >
        <div className="container">
          <div
            style={{
              display: "inline-flex",
              alignItems: "center",
              gap: 6,
              padding: "4px 12px",
              background: "var(--accent-dim)",
              border: "1px solid rgba(34, 197, 94, 0.2)",
              borderRadius: "var(--radius-sm)",
              fontSize: 12,
              fontFamily: "var(--font-mono)",
              color: "var(--accent)",
              marginBottom: 24,
            }}
          >
            <span
              style={{
                width: 6,
                height: 6,
                borderRadius: "50%",
                background: "var(--accent)",
              }}
            />
            v{config.version} — Open Source
          </div>

          <h1
            style={{
              maxWidth: 700,
              margin: "0 auto 20px",
              lineHeight: 1.1,
            }}
          >
            Your AI, working
            <br />
            from your desktop.
          </h1>

          <p
            style={{
              fontSize: 17,
              maxWidth: 540,
              margin: "0 auto 36px",
              lineHeight: 1.6,
            }}
          >
            DASH combines conversation, memory, coding, research, automation,
            and computer interaction into one personal AI operating system.
          </p>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <Link to="/download" className="btn btn--primary btn--lg">
              <Download size={16} />
              Download DASH
            </Link>
            <Link to="/product" className="btn btn--secondary btn--lg">
              Explore the system
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </section>

      {/* Terminal Preview */}
      <section style={{ padding: "0 0 80px" }}>
        <div className="container">
          <div
            style={{
              background: "var(--bg-secondary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-lg)",
              overflow: "hidden",
              maxWidth: 800,
              margin: "0 auto",
            }}
          >
            <div
              style={{
                padding: "10px 16px",
                borderBottom: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                gap: 8,
              }}
            >
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#ef4444",
                }}
              />
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#f59e0b",
                }}
              />
              <div
                style={{
                  width: 8,
                  height: 8,
                  borderRadius: "50%",
                  background: "#22c55e",
                }}
              />
              <span
                style={{
                  marginLeft: 8,
                  fontSize: 12,
                  color: "var(--text-muted)",
                  fontFamily: "var(--font-mono)",
                }}
              >
                DASH Terminal
              </span>
            </div>
            <pre
              style={{
                padding: 20,
                margin: 0,
                fontSize: 13,
                lineHeight: 1.6,
                fontFamily: "var(--font-mono)",
                color: "var(--text-secondary)",
                background: "transparent",
                border: "none",
              }}
            >
              <span style={{ color: "var(--accent)" }}>dash</span>
              <span style={{ color: "var(--text-muted)" }}> $ </span>
              <span>analyze project performance</span>{"\n"}
              <span style={{ color: "var(--text-muted)" }}>
                [context] Loading project: dash (branch: main)
              </span>
              {"\n"}
              <span style={{ color: "var(--text-muted)" }}>
                [memory] Retrieved 12 relevant memories
              </span>
              {"\n"}
              <span style={{ color: "var(--text-muted)" }}>
                [predictive] 2 risks detected
              </span>
              {"\n\n"}
              <span style={{ color: "var(--accent)" }}>System:</span>
              <span> CPU 45% | RAM 86% | Disk 81%</span>{"\n"}
              <span style={{ color: "var(--accent)" }}>Project:</span>
              <span> dash (main) — 3 modified files</span>{"\n"}
              <span style={{ color: "var(--warning)" }}>Risk:</span>
              <span> Disk usage trending upward (+2.1%/week)</span>
              {"\n\n"}
              <span style={{ color: "var(--text-muted)" }}>
                Ready for next task.
              </span>
            </pre>
          </div>
        </div>
      </section>

      {/* Capabilities */}
      <section className="section" style={{ background: "var(--bg-secondary)" }}>
        <div className="container">
          <div className="text-center mb-32">
            <h2>Built for real work</h2>
            <p style={{ marginTop: 12, margin: "12px auto 0" }}>
              Every feature exists because it solves a real problem.
            </p>
          </div>

          <div className="grid grid--3">
            {CAPABILITIES.map((cap) => (
              <div key={cap.title} className="card">
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 12,
                  }}
                >
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 10,
                    }}
                  >
                    <cap.icon size={18} style={{ color: "var(--accent)" }} />
                    <span className="card__title" style={{ marginBottom: 0 }}>
                      {cap.title}
                    </span>
                  </div>
                  <span className={`badge badge--${cap.status}`}>
                    {cap.status}
                  </span>
                </div>
                <p className="card__desc">{cap.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* How It Works */}
      <section className="section">
        <div className="container">
          <div className="text-center mb-32">
            <h2>How it works</h2>
            <p style={{ marginTop: 12, margin: "12px auto 0" }}>
              Three steps from download to productive.
            </p>
          </div>

          <div className="grid grid--3">
            {[
              {
                step: "01",
                title: "Install",
                desc: "Download and run the installer. DASH sets up everything automatically.",
              },
              {
                step: "02",
                title: "Configure",
                desc: "Choose your AI provider (local Ollama or cloud), set preferences, and connect tools.",
              },
              {
                step: "03",
                title: "Work",
                desc: "Start a conversation, create goals, or let DASH proactively suggest improvements.",
              },
            ].map((item) => (
              <div key={item.step} className="card">
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--accent)",
                    marginBottom: 12,
                  }}
                >
                  {item.step}
                </div>
                <h3 style={{ marginBottom: 8 }}>{item.title}</h3>
                <p className="card__desc">{item.desc}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* CTA */}
      <section className="section" style={{ textAlign: "center" }}>
        <div className="container">
          <h2>Ready to start?</h2>
          <p style={{ marginTop: 12, margin: "12px auto 0", marginBottom: 32 }}>
            Open source. Runs on your machine. Your data stays local.
          </p>
          <div
            style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              gap: 12,
              flexWrap: "wrap",
            }}
          >
            <Link to="/download" className="btn btn--primary btn--lg">
              <Download size={16} />
              Download DASH
            </Link>
            <a
              href={config.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn--secondary btn--lg"
            >
              <Github size={16} />
              View on GitHub
              <ExternalLink size={12} />
            </a>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
