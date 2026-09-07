import { PageLayout } from "@/components/PageLayout";

export function CookiesPage() {
  return (
    <PageLayout
      title="Cookie Policy"
      description="Effective Date: September 7, 2026"
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700, fontSize: 14, lineHeight: 1.8 }}>
          <div
            style={{
              padding: 20,
              background: "var(--bg-tertiary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              marginBottom: 32,
            }}
          >
            <strong style={{ color: "var(--accent)" }}>Simple answer:</strong>{" "}
            DASH does not use cookies. Not now, not ever.
          </div>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Why this page exists</h2>
          <p style={{ marginBottom: 24 }}>
            This cookie policy exists for completeness and regulatory
            transparency. DASH is a native desktop application (Electron) that
            stores data in a local SQLite database and JSON files. It does not
            use web-based tracking technologies.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>What DASH does NOT use</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>Session cookies</li>
            <li>Analytics cookies</li>
            <li>Advertising cookies</li>
            <li>Third-party tracking cookies</li>
            <li>Web beacons or tracking pixels</li>
            <li>Session replay tools</li>
            <li>Heatmap or behavior tracking</li>
            <li>Local storage tracking</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Authentication</h2>
          <p style={{ marginBottom: 24 }}>
            DASH uses device tokens stored in a local JSON file
            (%LOCALAPPDATA%\DASH\identity.json), not browser cookies.
            Authentication is handled entirely locally.
          </p>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>This website</h2>
          <p>
            This public website (dash-ai.dev) does not use cookies, analytics,
            or tracking of any kind. No data is collected from visitors.
          </p>
        </div>
      </section>
    </PageLayout>
  );
}
