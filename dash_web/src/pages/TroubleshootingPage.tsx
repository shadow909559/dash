import { PageLayout } from "@/components/PageLayout";
import { FaqItem } from "@/components/FaqItem";

const TROUBLESHOOTING = [
  {
    category: "Startup",
    items: [
      {
        q: "DASH will not start",
        a: "Check that no other DASH instance is running. Restart your computer and try again. If the issue persists, check the backend logs at apps/backend/backend_stderr.log. Ensure Python 3.14+ is installed and available in your PATH.",
      },
      {
        q: "Backend fails to start",
        a: "Ensure all dependencies are installed: cd apps/backend && pip install -r requirements.txt. Check that port 8000 is not in use by another application. Verify your .env file has correct DATABASE_URL.",
      },
      {
        q: "Desktop app shows blank screen",
        a: "The backend must be running for the desktop app to function. Start the backend first, then launch the desktop app. Check the Electron console for errors (Ctrl+Shift+I).",
      },
    ],
  },
  {
    category: "AI / Models",
    items: [
      {
        q: "AI provider unavailable",
        a: "For Ollama: ensure Ollama is running (ollama serve). For cloud providers: verify your API key is correct in Settings → AI Providers. Check your internet connection. The default model is llama3.2:1b for fast responses.",
      },
      {
        q: "Responses are slow",
        a: "Local Ollama inference speed depends on your hardware. GPU acceleration significantly improves speed. For faster responses, use a smaller model (llama3.2:1b) or switch to a cloud provider like Groq.",
      },
      {
        q: "Model not found",
        a: "Pull the required model: ollama pull <model-name>. Check available models in Settings → AI Providers. DASH supports Ollama, Groq, Gemini, OpenAI, and Anthropic.",
      },
    ],
  },
  {
    category: "Connection",
    items: [
      {
        q: "WebSocket connection failed",
        a: "Ensure the backend is running and accessible. Check that the WebSocket URL in Settings → Connection is correct. Verify no firewall is blocking the connection. The desktop app auto-reconnects on network changes.",
      },
      {
        q: "Authentication failed",
        a: "Your device token may have expired. Sign out and sign in again. Check Settings → Security for active sessions. You can revoke old sessions and create new ones.",
      },
    ],
  },
  {
    category: "Features",
    items: [
      {
        q: "Memory not working",
        a: "Memory requires the Ollama embedding model: ollama pull nomic-embed-text. Check that memory is enabled in Settings. Memories are extracted automatically from conversations and can be created manually.",
      },
      {
        q: "Voice not working",
        a: "Configure speech-to-text and text-to-speech providers in Settings → Voice. Ensure your microphone is accessible. Check that the required TTS engine is installed.",
      },
      {
        q: "Desktop control not working",
        a: "Desktop control is experimental. Ensure permissions are granted in Settings → Security. Some features require administrator privileges. Check the system monitor for service status.",
      },
    ],
  },
  {
    category: "Download / Install",
    items: [
      {
        q: "Download not starting",
        a: "Downloads are hosted on GitHub Releases. If the link does not work, visit the releases page directly. Check your browser's download settings and firewall. Try a different browser if the issue persists.",
      },
      {
        q: "Windows SmartScreen warning",
        a: "DASH is an open-source application. Windows may show a warning for unsigned executables. Click 'More info' and 'Run anyway' if you trust the source. You can verify the code on GitHub.",
      },
    ],
  },
];

export function TroubleshootingPage() {
  return (
    <PageLayout
      title="Troubleshooting"
      description="Common issues and their solutions."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700 }}>
          {TROUBLESHOOTING.map((group) => (
            <div key={group.category} style={{ marginBottom: 40 }}>
              <h3
                style={{
                  fontSize: 12,
                  fontWeight: 600,
                  textTransform: "uppercase",
                  letterSpacing: "0.08em",
                  color: "var(--text-muted)",
                  marginBottom: 12,
                }}
              >
                {group.category}
              </h3>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {group.items.map((item) => (
                  <FaqItem key={item.q} question={item.q} answer={item.a} />
                ))}
              </div>
            </div>
          ))}

          <div
            style={{
              marginTop: 32,
              padding: 16,
              background: "var(--bg-tertiary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              fontSize: 13,
              color: "var(--text-secondary)",
            }}
          >
            Still having issues?{" "}
            <a
              href="https://github.com/shadow909559/dash/issues"
              target="_blank"
              rel="noopener noreferrer"
            >
              Report an issue on GitHub
            </a>
            .
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
