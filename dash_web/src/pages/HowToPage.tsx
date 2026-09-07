import { PageLayout } from "@/components/PageLayout";
import {
  MessageSquare,
  Brain,
  Code2,
  Search,
  Workflow,
  Bot,
  Shield,
  Calendar,
  Monitor,
} from "lucide-react";

const GUIDES = [
  {
    icon: MessageSquare,
    title: "Chat",
    content: [
      "Open the Chat page from the sidebar.",
      "Select a mode: General (conversation), Coder (code tasks), Planner (goals), Research (web research), or Executor (run commands).",
      "Type your message and press Enter.",
      "Each mode has its own isolated conversation history.",
      "DASH uses the context engine to provide relevant background with every response.",
    ],
  },
  {
    icon: Brain,
    title: "Memory",
    content: [
      "Open the Memory page to view stored memories.",
      "DASH automatically extracts important facts from conversations.",
      "You can manually create memories for preferences, decisions, and project context.",
      "Use the search function to find specific memories.",
      "Memories are typed: personal, preference, project, decision, or experience.",
    ],
  },
  {
    icon: Code2,
    title: "Coding",
    content: [
      "Switch to Coder mode in Chat.",
      "Describe what you want to build, fix, or explain.",
      "DASH uses project context from the Context Engine to understand your codebase.",
      "Code suggestions include explanations and can be applied directly.",
      "Use the Planning mode to break large coding tasks into steps.",
    ],
  },
  {
    icon: Search,
    title: "Research",
    content: [
      "Switch to Research mode in Chat.",
      "Ask a research question or topic.",
      "DASH will search, synthesize, and present findings with sources.",
      "Research results can be saved to memory for future reference.",
    ],
  },
  {
    icon: Workflow,
    title: "Automation",
    content: [
      "Open the Automation page from the sidebar.",
      "Create a new rule with a trigger and action.",
      "Triggers can be time-based (schedule) or event-based.",
      "Actions can run commands, send notifications, or trigger AI tasks.",
      "Rules can be enabled/disabled individually.",
    ],
  },
  {
    icon: Bot,
    title: "Agents",
    content: [
      "Open the Agents page to see available specialized agents.",
      "Agents are invoked automatically based on task requirements.",
      "The Orchestrator coordinates multiple agents for complex tasks.",
      "Tool chains allow agents to execute multi-step workflows.",
      "Monitor agent activity in real-time.",
    ],
  },
  {
    icon: Shield,
    title: "Approvals",
    content: [
      "When DASH needs to perform a consequential action, it requests approval.",
      "Review the action details in the Approvals page.",
      "Approve or deny each action individually.",
      "Approved actions are executed immediately.",
      "Denied actions are logged for audit purposes.",
    ],
  },
  {
    icon: Calendar,
    title: "Planning",
    content: [
      "Open the Planner page to manage goals and tasks.",
      "Create a goal with a name, priority, and optional deadline.",
      "Break goals into smaller tasks.",
      "Track progress as tasks are completed.",
      "DASH proactively reminds you of upcoming deadlines.",
    ],
  },
  {
    icon: Monitor,
    title: "System Monitor",
    content: [
      "Open the System Monitor to view real-time system metrics.",
      "Monitor CPU, RAM, disk usage, and GPU utilization.",
      "Check service health: Backend, WebSocket, AI Provider, Obsidian.",
      "View backend uptime and version information.",
      "Analytics are updated every 5 seconds.",
    ],
  },
];

export function HowToPage() {
  return (
    <PageLayout
      title="How to Use DASH"
      description="Practical guides for every major feature."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 800 }}>
          {GUIDES.map((guide, i) => (
            <div
              key={guide.title}
              style={{
                padding: "32px 0",
                borderBottom:
                  i < GUIDES.length - 1 ? "1px solid var(--border)" : "none",
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 16,
                }}
              >
                <guide.icon size={20} style={{ color: "var(--accent)" }} />
                <h2 style={{ marginBottom: 0, fontSize: 20 }}>{guide.title}</h2>
              </div>
              <ol
                style={{
                  paddingLeft: 20,
                  display: "flex",
                  flexDirection: "column",
                  gap: 8,
                }}
              >
                {guide.content.map((step, j) => (
                  <li
                    key={j}
                    style={{
                      fontSize: 14,
                      color: "var(--text-secondary)",
                      lineHeight: 1.6,
                    }}
                  >
                    {step}
                  </li>
                ))}
              </ol>
            </div>
          ))}
        </div>
      </section>
    </PageLayout>
  );
}
