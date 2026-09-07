import { PageLayout } from "@/components/PageLayout";
import { FaqItem } from "@/components/FaqItem";

export function SecurityPage() {
  return (
    <PageLayout
      title="Security"
      description="How DASH protects your data and system."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 800 }}>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 24,
              marginBottom: 48,
            }}
          >
            {[
              {
                title: "Authentication",
                desc: "Device-token based authentication with bcrypt password hashing. Each device gets a unique token stored locally. No cloud authentication dependency.",
              },
              {
                title: "Session Management",
                desc: "Unique session IDs with expiration and revocation. View and revoke active sessions from Settings → Security. Sessions are hashed before storage.",
              },
              {
                title: "Authorization",
                desc: "All API endpoints require valid authentication. No unauthenticated access is possible. Role-based permissions for multi-user scenarios.",
              },
              {
                title: "Approval Controls",
                desc: "Consequential actions require explicit user approval. Review, approve, or deny before execution. All approvals are logged.",
              },
              {
                title: "Audit Logging",
                desc: "Security-relevant actions are logged with redacted sensitive values. Passwords, tokens, and API keys are never stored in logs.",
              },
              {
                title: "Data Protection",
                desc: "All data stored locally in SQLite. No telemetry, no analytics, no tracking. Data export and deletion available via API. Your data never leaves your machine unless you configure cloud AI.",
              },
            ].map((item) => (
              <div key={item.title} className="card">
                <h4 style={{ marginBottom: 8 }}>{item.title}</h4>
                <p className="card__desc">{item.desc}</p>
              </div>
            ))}
          </div>

          <h2 className="mb-24">Frequently asked questions</h2>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <FaqItem
              question="Does DASH send data to external servers?"
              answer="By default, no. DASH uses Ollama for local AI inference. Cloud AI providers (Groq, Gemini, OpenAI) only receive data if you explicitly configure them. Only prompt text is sent — never passwords, tokens, or other sensitive data."
            />
            <FaqItem
              question="Is my password stored securely?"
              answer="Yes. Passwords are hashed using bcrypt before storage. Raw passwords are never stored, logged, or transmitted. Refresh tokens are hashed with SHA-256."
            />
            <FaqItem
              question="Can someone access my data remotely?"
              answer="DASH runs locally on your machine. Remote access requires either the desktop app or Android companion, both of which require authentication. No data is accessible over the internet unless you explicitly set up cloud relay."
            />
            <FaqItem
              question="What about API keys for cloud AI providers?"
              answer="API keys are stored in your local configuration. They are never sent to any server other than the configured AI provider. They are never logged or included in any export."
            />
            <FaqItem
              question="Does DASH use cookies?"
              answer="No. DASH is a native desktop application (Electron) that stores data in a local SQLite database and JSON files. No cookies, no tracking, no analytics."
            />
            <FaqItem
              question="How do I delete all my data?"
              answer="Use DELETE /privacy/data-delete?confirm=true via the API, or use the privacy controls in Settings → Security. This removes all conversations, memories, sessions, tasks, and other data."
            />
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
