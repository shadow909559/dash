import { PageLayout } from "@/components/PageLayout";
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
  Mic,
  Globe,
  Puzzle,
  BarChart3,
  Bell,
  Settings,
  FileText,
  Eye,
  Target,
  Zap,
} from "lucide-react";

const FEATURES = [
  {
    category: "Core",
    items: [
      {
        icon: MessageSquare,
        title: "Multi-Mode Chat",
        desc: "5 specialized modes: General, Coder, Planner, Research, Executor. Each with isolated context and tailored behavior.",
        status: "available",
      },
      {
        icon: Brain,
        title: "Long-Term Memory",
        desc: "Episodic and semantic memory with typed categories (personal, preference, project, decision, experience), confidence scores, and project association.",
        status: "available",
      },
      {
        icon: FileText,
        title: "Context Engine",
        desc: "Gathers device state, project info, and activity into a unified context block for every AI interaction.",
        status: "available",
      },
    ],
  },
  {
    category: "Intelligence",
    items: [
      {
        icon: Target,
        title: "Proactive Suggestions",
        desc: "DASH detects issues and opportunities, then surfaces actionable suggestions with importance scoring and cooldown gating.",
        status: "available",
      },
      {
        icon: Eye,
        title: "Predictive Detection",
        desc: "Trend analysis on device metrics with least-squares regression. Predicts disk exhaustion, RAM pressure, and project health issues.",
        status: "available",
      },
      {
        icon: Calendar,
        title: "Goal & Task Engine",
        desc: "Create goals, break them into tasks, track deadlines, and monitor completion. Integrated with proactive suggestions.",
        status: "available",
      },
    ],
  },
  {
    category: "Tools",
    items: [
      {
        icon: Code2,
        title: "Coding Assistant",
        desc: "Code generation, explanation, refactoring, and debugging. Integrated with your project context.",
        status: "available",
      },
      {
        icon: Search,
        title: "Research Mode",
        desc: "Web research with source tracking, structured summaries, and citation management.",
        status: "available",
      },
      {
        icon: Workflow,
        title: "Automation Rules",
        desc: "Create trigger-action rules with scheduled execution. Run custom scripts and commands.",
        status: "available",
      },
      {
        icon: Bot,
        title: "Multi-Agent Orchestration",
        desc: "Specialized agents with tool chains, decision engine, and execution graphs.",
        status: "available",
      },
    ],
  },
  {
    category: "Integration",
    items: [
      {
        icon: Monitor,
        title: "Desktop Control",
        desc: "Mouse, keyboard, window management, clipboard, file operations, and power controls.",
        status: "experimental",
      },
      {
        icon: Globe,
        title: "Browser Automation",
        desc: "Web scraping, tab management, and research mode via browser integration.",
        status: "experimental",
      },
      {
        icon: Mic,
        title: "Voice System",
        desc: "Speech-to-text, text-to-speech, wake word detection, and conversation mode.",
        status: "available",
      },
      {
        icon: Puzzle,
        title: "Plugin System",
        desc: "Install and manage third-party extensions. Built-in modules for all core features.",
        status: "available",
      },
    ],
  },
  {
    category: "Safety",
    items: [
      {
        icon: Shield,
        title: "Approval Controls",
        desc: "User-in-the-loop approval for consequential actions. Review, approve, or deny before execution.",
        status: "available",
      },
      {
        icon: Bell,
        title: "Notifications",
        desc: "System and proactive notifications with WebSocket push delivery and read tracking.",
        status: "available",
      },
      {
        icon: BarChart3,
        title: "Analytics Dashboard",
        desc: "Real-time system metrics, service health, and performance monitoring.",
        status: "available",
      },
      {
        icon: Settings,
        title: "Privacy Controls",
        desc: "Data export, deletion, inventory, and session management. Your data, your control.",
        status: "available",
      },
    ],
  },
];

export function FeaturesPage() {
  return (
    <PageLayout
      title="Features"
      description="Every feature exists because it solves a real problem. No filler, no fake capabilities."
    >
      <section className="section--sm">
        <div className="container">
          <div
            style={{
              display: "flex",
              gap: 16,
              marginBottom: 40,
              flexWrap: "wrap",
            }}
          >
            <span className="badge badge--available">Available</span>
            <span className="badge badge--experimental">Experimental</span>
            <span className="badge badge--planned">Planned</span>
            <span className="badge badge--concept">Concept</span>
          </div>

          {FEATURES.map((group) => (
            <div key={group.category} style={{ marginBottom: 48 }}>
              <h3
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--text-muted)",
                  marginBottom: 16,
                }}
              >
                {group.category}
              </h3>
              <div className="grid grid--2">
                {group.items.map((item) => (
                  <div key={item.title} className="card">
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        justifyContent: "space-between",
                        marginBottom: 10,
                      }}
                    >
                      <div
                        style={{
                          display: "flex",
                          alignItems: "center",
                          gap: 10,
                        }}
                      >
                        <item.icon
                          size={16}
                          style={{ color: "var(--accent)" }}
                        />
                        <span
                          style={{ fontWeight: 600, fontSize: 14 }}
                        >
                          {item.title}
                        </span>
                      </div>
                      <span className={`badge badge--${item.status}`}>
                        {item.status}
                      </span>
                    </div>
                    <p className="card__desc">{item.desc}</p>
                  </div>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>
    </PageLayout>
  );
}
