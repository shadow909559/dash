import { Link } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import {
  BookOpen,
  Download,
  Settings,
  Zap,
  HelpCircle,
  Shield,
  ArrowRight,
  ExternalLink,
} from "lucide-react";
import { config } from "@/lib/config";

const DOCS = [
  {
    icon: Zap,
    title: "Quick Start",
    desc: "Get up and running in under 5 minutes.",
    link: "/quickstart",
  },
  {
    icon: Download,
    title: "Installation",
    desc: "Step-by-step installation guide with build-from-source instructions.",
    link: "/install",
  },
  {
    icon: Settings,
    title: "First-Time Setup",
    desc: "Configure AI providers, permissions, and optional integrations.",
    link: "/setup",
  },
  {
    icon: BookOpen,
    title: "How to Use DASH",
    desc: "Practical guides for chat, memory, coding, research, automation, and more.",
    link: "/howto",
  },
  {
    icon: HelpCircle,
    title: "Troubleshooting",
    desc: "Common issues and their solutions.",
    link: "/troubleshooting",
  },
  {
    icon: Shield,
    title: "Security",
    desc: "How DASH protects your data and system.",
    link: "/security",
  },
];

export function DocsPage() {
  return (
    <PageLayout
      title="Documentation"
      description="Everything you need to install, configure, and use DASH."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 800 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 16,
            }}
          >
            {DOCS.map((doc) => (
              <Link
                key={doc.title}
                to={doc.link}
                className="card"
                style={{
                  textDecoration: "none",
                  display: "flex",
                  gap: 16,
                  alignItems: "flex-start",
                }}
              >
                <doc.icon
                  size={20}
                  style={{ color: "var(--accent)", marginTop: 2, flexShrink: 0 }}
                />
                <div>
                  <h3 style={{ fontSize: 15, marginBottom: 4 }}>{doc.title}</h3>
                  <p style={{ fontSize: 13, color: "var(--text-secondary)", margin: 0 }}>
                    {doc.desc}
                  </p>
                </div>
              </Link>
            ))}
          </div>

          <hr className="divider" />

          <h2 style={{ marginBottom: 16 }}>Full Documentation</h2>
          <p style={{ marginBottom: 16, fontSize: 14 }}>
            The complete DASH system report covers architecture, components,
            API reference, and implementation details.
          </p>
          <a
            href={config.docsUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn--secondary"
          >
            DASH Report on GitHub
            <ExternalLink size={12} />
          </a>
        </div>
      </section>
    </PageLayout>
  );
}
