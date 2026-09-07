import { PageLayout } from "@/components/PageLayout";

export function TermsPage() {
  return (
    <PageLayout
      title="Terms & Conditions"
      description="Effective Date: September 7, 2026 · Version 1.0"
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700, fontSize: 14, lineHeight: 1.8 }}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>1. Acceptance</h2>
          <p style={{ marginBottom: 24 }}>
            By using DASH, you agree to these terms. If you do not agree, do
            not use DASH.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>2. Description of Service</h2>
          <p style={{ marginBottom: 24 }}>
            DASH is a personal AI operating system that runs on your local
            machine. It provides AI-assisted conversation, memory, coding,
            research, automation, and system interaction capabilities.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>3. Your Responsibilities</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>Maintaining the security of your account</li>
            <li>All activity under your account</li>
            <li>Keeping contact information current</li>
            <li>Notifying of unauthorized use</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>4. AI Limitations</h2>
          <p style={{ marginBottom: 24 }}>
            DASH uses AI models that produce probabilistic output. AI-generated
            content may contain errors. DASH makes no guarantee of accuracy.
            You are responsible for verifying AI output before relying on it.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>5. Prohibited Use</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>Unauthorized access attempts</li>
            <li>Using DASH for illegal purposes</li>
            <li>Circumventing authentication controls</li>
            <li>Reselling or redistributing without authorization</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>6. Intellectual Property</h2>
          <p style={{ marginBottom: 24 }}>
            DASH and its original content, features, and functionality are owned
            by the DASH project. You retain all rights to content you create,
            input, or generate through DASH.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>7. Limitation of Liability</h2>
          <p style={{ marginBottom: 24 }}>
            DASH is provided "as is" without warranty. The DASH project is not
            liable for any damages arising from use of the software.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>8. Governing Law</h2>
          <p style={{ marginBottom: 24 }}>
            These terms are governed by the laws of India.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>9. Contact</h2>
          <p>
            For questions:{" "}
            <a href="https://github.com/shadow909559/dash/issues" target="_blank" rel="noopener noreferrer">
              GitHub Issues
            </a>
          </p>
        </div>
      </section>
    </PageLayout>
  );
}
