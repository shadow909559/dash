import { PageLayout } from "@/components/PageLayout";

export function AccessibilityPage() {
  return (
    <PageLayout
      title="Accessibility"
      description="Our commitment to accessibility and honest disclosure of limitations."
    >
      <section className="section--sm">
        <div className="container" style={{ maxWidth: 700, fontSize: 14, lineHeight: 1.8 }}>
          <h2 style={{ fontSize: 18, marginBottom: 16 }}>What we support</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>Keyboard navigation across all pages</li>
            <li>Visible focus indicators on all interactive elements</li>
            <li>Skip-to-content link for keyboard users</li>
            <li>ARIA labels on icon-only buttons and form inputs</li>
            <li>Semantic HTML structure (headings, landmarks, lists)</li>
            <li>Screen reader compatibility via ARIA attributes</li>
            <li>Reduced motion support via prefers-reduced-motion</li>
            <li>Minimum touch target size of 24px</li>
            <li>Color contrast meeting WCAG 2.1 Level AA</li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Known limitations</h2>
          <ul style={{ paddingLeft: 20, marginBottom: 24, color: "var(--text-secondary)" }}>
            <li>
              <strong>Orb visual interface:</strong> The animated Orb on the home
              page is primarily visual and may not convey information to screen
              readers. Status is also shown as text.
            </li>
            <li>
              <strong>Dark theme only:</strong> DASH currently offers only a dark
              color scheme. A light theme is planned.
            </li>
            <li>
              <strong>Mobile/touch:</strong> The desktop app is designed for
              keyboard and mouse. Touch support is limited to basic navigation.
            </li>
            <li>
              <strong>Language:</strong> DASH is currently available in English
              only.
            </li>
          </ul>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Accessibility features</h2>
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(200px, 1fr))",
              gap: 16,
              marginBottom: 32,
            }}
          >
            {[
              { title: "Keyboard", desc: "Full keyboard navigation with visible focus" },
              { title: "Screen Readers", desc: "ARIA labels and semantic HTML" },
              { title: "Motion", desc: "Respects prefers-reduced-motion" },
              { title: "Contrast", desc: "WCAG 2.1 Level AA compliant" },
              { title: "Forms", desc: "Labeled inputs with validation" },
              { title: "Navigation", desc: "Skip links and landmarks" },
            ].map((item) => (
              <div key={item.title} className="card" style={{ padding: 16 }}>
                <h4 style={{ marginBottom: 4, fontSize: 13 }}>{item.title}</h4>
                <p style={{ fontSize: 12, color: "var(--text-muted)", margin: 0 }}>
                  {item.desc}
                </p>
              </div>
            ))}
          </div>

          <h2 style={{ fontSize: 18, marginBottom: 16 }}>Report issues</h2>
          <p>
            If you encounter accessibility issues, please report them on{" "}
            <a
              href="https://github.com/shadow909559/dash/issues"
              target="_blank"
              rel="noopener noreferrer"
            >
              GitHub Issues
            </a>{" "}
            with the "accessibility" label.
          </p>
        </div>
      </section>
    </PageLayout>
  );
}
