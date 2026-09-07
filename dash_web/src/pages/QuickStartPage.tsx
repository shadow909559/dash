import { Link } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { Download, ArrowRight } from "lucide-react";
import { config } from "@/lib/config";

export function QuickStartPage() {
  return (
    <PageLayout
      title="Quick Start"
      description="From download to productive in under 5 minutes."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 600 }}>
          {[
            {
              step: "1",
              title: "Download DASH",
              desc: "Get the latest release for Windows.",
              link: "/download",
              linkText: "Download page",
            },
            {
              step: "2",
              title: "Install DASH",
              desc: "Run the installer. It sets up everything automatically.",
              link: "/install",
              linkText: "Installation guide",
            },
            {
              step: "3",
              title: "Sign in",
              desc: "Create an account. Your credentials stay on your machine.",
            },
            {
              step: "4",
              title: "Configure AI",
              desc: "Use local Ollama (default) or add a cloud API key in Settings.",
              link: "/setup",
              linkText: "Setup guide",
            },
            {
              step: "5",
              title: "Start working",
              desc: "Open Chat, pick a mode, and ask DASH something. Try: 'help me plan a project' or 'explain this code'.",
            },
          ].map((item, i) => (
            <div
              key={item.step}
              style={{
                display: "flex",
                gap: 16,
                padding: "20px 0",
                borderBottom:
                  i < 5 ? "1px solid var(--border)" : "none",
              }}
            >
              <div
                style={{
                  fontFamily: "var(--font-mono)",
                  fontSize: 14,
                  fontWeight: 700,
                  color: "var(--accent)",
                  minWidth: 28,
                }}
              >
                {item.step}
              </div>
              <div>
                <h3 style={{ fontSize: 15, marginBottom: 4 }}>{item.title}</h3>
                <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                  {item.desc}
                </p>
                {item.link && (
                  <Link
                    to={item.link}
                    style={{
                      fontSize: 13,
                      display: "inline-flex",
                      alignItems: "center",
                      gap: 4,
                      marginTop: 6,
                    }}
                  >
                    {item.linkText} <ArrowRight size={12} />
                  </Link>
                )}
              </div>
            </div>
          ))}

          <div style={{ marginTop: 40, textAlign: "center" }}>
            <Link to="/docs" className="btn btn--secondary">
              Read full documentation
              <ArrowRight size={14} />
            </Link>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
