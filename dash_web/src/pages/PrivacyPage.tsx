import { PageLayout } from "@/components/PageLayout";

export function PrivacyPage() {
  return (
    <PageLayout
      title="Privacy Policy"
      description="Effective Date: September 7, 2026 · Version 1.0"
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700, fontSize: 14, lineHeight: 1.8 }}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>1. Overview</h2>
          <p style={{ marginBottom: 24 }}>
            DASH is a personal AI operating system that runs on your local
            machine. This privacy policy describes what data DASH collects, how
            it is used, where it is stored, and what controls you have over it.
            DASH is designed as a single-user, locally-run application. Your
            data stays on your machine by default.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>2. Data We Collect</h2>
          <p style={{ marginBottom: 12 }}>
            DASH stores the following data locally on your device:
          </p>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>Account information (email, username, password hash)</li>
            <li>Session records (session ID, hashed refresh token, IP, user agent)</li>
            <li>Conversations and messages</li>
            <li>Memory entries (preferences, facts, decisions)</li>
            <li>Goals and tasks</li>
            <li>Notifications</li>
            <li>Audit log entries (security events only)</li>
            <li>Device information (name, type, platform)</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>3. How Data Is Used</h2>
          <p style={{ marginBottom: 12 }}>
            <strong>Local Processing (Default):</strong> By default, DASH
            processes all data on your local machine. DASH does not send your
            personal data to any external service unless you explicitly configure
            a cloud AI provider.
          </p>
          <p style={{ marginBottom: 12 }}>
            <strong>AI Model Providers (Optional):</strong> When you configure a
            cloud AI provider, DASH sends only prompt text and conversation
            context. Passwords, tokens, and other sensitive data are never sent.
          </p>
          <p style={{ marginBottom: 24 }}>
            <strong>No Tracking:</strong> DASH does not use cookies, analytics,
            tracking pixels, or any web-based tracking technologies.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>4. Data Storage</h2>
          <p style={{ marginBottom: 24 }}>
            All data is stored in a local SQLite database on your machine. State
            files are stored in your local application data directory. No cloud
            storage is used. No data leaves your device unless you manually
            export it or configure a cloud AI provider.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>5. Your Rights</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li><strong>Export:</strong> Download all your data at any time</li>
            <li><strong>Delete:</strong> Remove all data permanently</li>
            <li><strong>Inventory:</strong> View all data stores and their contents</li>
            <li><strong>Sessions:</strong> View and revoke active sessions</li>
            <li><strong>Account deletion:</strong> Remove account and all associated data</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>6. Security</h2>
          <p style={{ marginBottom: 24 }}>
            DASH implements bcrypt password hashing, SHA-256 token hashing,
            session management with expiration and revocation, audit logging
            with sensitive value redaction, and device-token based authentication.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>7. Contact</h2>
          <p>
            For privacy-related questions:{" "}
            <a href="https://github.com/shadow909559/dash/issues" target="_blank" rel="noopener noreferrer">
              GitHub Issues
            </a>
          </p>
        </div>
      </section>
    </PageLayout>
  );
}
