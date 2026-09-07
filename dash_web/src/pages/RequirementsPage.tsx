import { PageLayout } from "@/components/PageLayout";

export function RequirementsPage() {
  return (
    <PageLayout
      title="System Requirements"
      description="What you need to run DASH."
    >
      <section className="section--sm">
        <div className="container">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(340px, 1fr))",
              gap: 24,
            }}
          >
            {/* Minimum */}
            <div className="card" style={{ border: "1px solid var(--border-hover)" }}>
              <h3 style={{ marginBottom: 16 }}>Minimum Requirements</h3>
              <table>
                <tbody>
                  {[
                    ["Operating System", "Windows 10/11 (64-bit)"],
                    ["CPU", "To be confirmed"],
                    ["RAM", "To be confirmed"],
                    ["Storage", "To be confirmed"],
                    ["GPU", "Not required (CPU inference supported)"],
                    ["Internet", "Required for cloud AI providers and updates"],
                    ["Architecture", "x86_64"],
                  ].map(([label, value]) => (
                    <tr key={label}>
                      <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                        {label}
                      </td>
                      <td>{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Recommended */}
            <div className="card">
              <h3 style={{ marginBottom: 16 }}>Recommended</h3>
              <table>
                <tbody>
                  {[
                    ["Operating System", "Windows 11 (64-bit)"],
                    ["CPU", "To be confirmed"],
                    ["RAM", "To be confirmed"],
                    ["Storage", "To be confirmed"],
                    ["GPU", "NVIDIA GPU with CUDA (for local AI inference)"],
                    ["Internet", "Broadband for cloud AI and research features"],
                    ["Architecture", "x86_64"],
                  ].map(([label, value]) => (
                    <tr key={label}>
                      <td style={{ fontWeight: 500, color: "var(--text-primary)" }}>
                        {label}
                      </td>
                      <td>{value}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

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
            <strong style={{ color: "var(--text-primary)" }}>Note:</strong>{" "}
            Hardware requirements are marked "To be confirmed" because they
            depend on your usage pattern. Local AI inference (Ollama) benefits
            from more RAM and a CUDA GPU. Cloud-only usage has minimal hardware
            requirements. We will update these once we have benchmark data.
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
