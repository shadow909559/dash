import { PageLayout } from "@/components/PageLayout";
import { CodeBlock } from "@/components/CodeBlock";
import { CheckCircle } from "lucide-react";

const STEPS = [
  {
    number: "01",
    title: "Check system requirements",
    desc: "Ensure you have Windows 10/11 (64-bit) with adequate RAM and storage.",
  },
  {
    number: "02",
    title: "Download DASH",
    desc: "Get the latest release from the download page or GitHub Releases.",
  },
  {
    number: "03",
    title: "Run the installer",
    desc: "Execute the downloaded installer. Follow the on-screen prompts.",
  },
  {
    number: "04",
    title: "Launch DASH",
    desc: "DASH will start automatically after installation. The boot animation will play while the system initializes.",
  },
  {
    number: "05",
    title: "Sign in",
    desc: "Create an account or sign in. Authentication is handled locally — your credentials never leave your device.",
  },
  {
    number: "06",
    title: "Complete initial setup",
    desc: "Configure your AI provider (Ollama for local, or add a cloud API key), set your preferences, and verify the connection.",
  },
  {
    number: "07",
    title: "Verify",
    desc: "Open the System Monitor page and confirm all services show ONLINE. Start a test conversation in Chat.",
  },
];

export function InstallPage() {
  return (
    <PageLayout
      title="Install DASH"
      description="Step-by-step installation guide."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700 }}>
          <div style={{ display: "flex", flexDirection: "column", gap: 0 }}>
            {STEPS.map((step, i) => (
              <div
                key={step.number}
                style={{
                  display: "flex",
                  gap: 20,
                  padding: "24px 0",
                  borderBottom:
                    i < STEPS.length - 1 ? "1px solid var(--border)" : "none",
                }}
              >
                <div
                  style={{
                    fontFamily: "var(--font-mono)",
                    fontSize: 12,
                    color: "var(--accent)",
                    fontWeight: 600,
                    paddingTop: 2,
                    minWidth: 24,
                  }}
                >
                  {step.number}
                </div>
                <div>
                  <h3 style={{ fontSize: 15, marginBottom: 6 }}>{step.title}</h3>
                  <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
                    {step.desc}
                  </p>
                </div>
              </div>
            ))}
          </div>

          {/* Build from Source */}
          <div style={{ marginTop: 48 }}>
            <h2 style={{ marginBottom: 16 }}>Build from source</h2>
            <p style={{ marginBottom: 16, fontSize: 14 }}>
              If you prefer to build DASH yourself:
            </p>
            <CodeBlock
              language="bash"
              code={`# Clone the repository
git clone https://github.com/shadow909559/dash.git
cd dash

# Install backend dependencies
cd apps/backend
pip install -r requirements.txt

# Start the backend
python -m uvicorn dash_backend.main:app --reload

# Install desktop app dependencies
cd ../../apps/desktop
npm install

# Start the desktop app
npm run dev`}
            />
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
