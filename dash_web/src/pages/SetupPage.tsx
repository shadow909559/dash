import { PageLayout } from "@/components/PageLayout";
import { CodeBlock } from "@/components/CodeBlock";

export function SetupPage() {
  return (
    <PageLayout
      title="First-Time Setup"
      description="Configure DASH after installation. Required and optional steps."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700 }}>
          {/* Required */}
          <h2 style={{ marginBottom: 16 }}>Required setup</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 24, marginBottom: 48 }}>
            <div className="card">
              <h4 style={{ marginBottom: 8 }}>1. AI Provider</h4>
              <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 12 }}>
                DASH needs an AI provider to function. The default is Ollama
                (local), which requires no API keys.
              </p>
              <p style={{ fontSize: 13, color: "var(--text-muted)" }}>
                <strong style={{ color: "var(--text-primary)" }}>Option A:</strong>{" "}
                Install Ollama from{" "}
                <a href="https://ollama.ai" target="_blank" rel="noopener noreferrer">
                  ollama.ai
                </a>{" "}
                and pull a model:
              </p>
              <CodeBlock
                language="bash"
                code={`ollama pull llama3.2:1b\n# or for better quality:\nollama pull llama3.3:70b`}
              />
              <p style={{ fontSize: 13, color: "var(--text-muted)", marginTop: 12 }}>
                <strong style={{ color: "var(--text-primary)" }}>Option B:</strong>{" "}
                Add a cloud provider API key in Settings → AI Providers.
              </p>
            </div>

            <div className="card">
              <h4 style={{ marginBottom: 8 }}>2. Permissions</h4>
              <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                DASH will request permissions for file access, clipboard, and
                system monitoring. These are required for core functionality.
                You can review and revoke permissions in Settings → Security.
              </p>
            </div>
          </div>

          {/* Optional */}
          <h2 style={{ marginBottom: 16 }}>Optional configuration</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            {[
              {
                title: "Voice System",
                desc: "Configure speech-to-text and text-to-speech providers in Settings → Voice. DASH supports multiple TTS engines.",
              },
              {
                title: "Cloud AI Providers",
                desc: "Add API keys for Groq, Gemini, OpenAI, or Anthropic in Settings → AI Providers. These are optional — DASH works fully with local Ollama.",
              },
              {
                title: "Obsidian Integration",
                desc: "Connect your Obsidian vault for knowledge management in Settings → Integrations.",
              },
              {
                title: "Android Companion",
                desc: "Install the Android companion app and pair it via Settings → Phone for mobile notifications and voice commands.",
              },
              {
                title: "Privacy Settings",
                desc: "Review privacy settings in Settings → Security. You can configure data export, session management, and audit logging.",
              },
            ].map((item) => (
              <div key={item.title} className="card">
                <h4 style={{ marginBottom: 6 }}>{item.title}</h4>
                <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
