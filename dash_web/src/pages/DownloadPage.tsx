import { Monitor, Smartphone, ExternalLink, Download, Info } from "lucide-react";
import { config } from "@/lib/config";
import { PageLayout } from "@/components/PageLayout";

export function DownloadPage() {
  return (
    <PageLayout
      title="Download DASH"
      description="Get DASH for your platform. Open source, free to use."
    >
      <section className="section--sm">
        <div className="container">
          <div
            style={{
              display: "grid",
              gridTemplateColumns: "repeat(auto-fit, minmax(300px, 1fr))",
              gap: 24,
            }}
          >
            {/* Desktop */}
            <div
              className="card"
              style={{
                border: "1px solid var(--border-hover)",
                padding: 32,
              }}
            >
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <Monitor size={24} style={{ color: "var(--accent)" }} />
                <div>
                  <h3 style={{ marginBottom: 0 }}>Desktop App</h3>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    Windows · Electron
                  </span>
                </div>
              </div>

              <p className="card__desc" style={{ marginBottom: 20 }}>
                Full DASH experience with system integration, voice support, and
                desktop automation.
              </p>

              <a
                href={config.downloadUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn--primary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                <Download size={14} />
                Download for Windows
                <ExternalLink size={12} />
              </a>

              <p
                style={{
                  fontSize: 12,
                  color: "var(--text-muted)",
                  marginTop: 12,
                  textAlign: "center",
                }}
              >
                Version {config.version} ·{" "}
                <a href={config.releaseUrl} target="_blank" rel="noopener noreferrer">
                  Release notes
                </a>
              </p>
            </div>

            {/* Android */}
            <div className="card" style={{ padding: 32 }}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 12,
                  marginBottom: 20,
                }}
              >
                <Smartphone size={24} style={{ color: "var(--accent)" }} />
                <div>
                  <h3 style={{ marginBottom: 0 }}>Android Companion</h3>
                  <span
                    style={{
                      fontSize: 12,
                      color: "var(--text-muted)",
                      fontFamily: "var(--font-mono)",
                    }}
                  >
                    Android · Kotlin
                  </span>
                </div>
              </div>

              <p className="card__desc" style={{ marginBottom: 20 }}>
                Companion app for mobile notifications, voice commands, and
                remote control of your DASH instance.
              </p>

              <a
                href={config.androidUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="btn btn--secondary"
                style={{ width: "100%", justifyContent: "center" }}
              >
                <Download size={14} />
                Download APK
                <ExternalLink size={12} />
              </a>

              <p
                style={{
                  fontSize: 12,
                  color: "var(--text-muted)",
                  marginTop: 12,
                  textAlign: "center",
                }}
              >
                Requires Android 8.0+ · Sideloading required
              </p>
            </div>
          </div>

          {/* Info Box */}
          <div
            style={{
              marginTop: 32,
              padding: 16,
              background: "var(--bg-tertiary)",
              border: "1px solid var(--border)",
              borderRadius: "var(--radius-md)",
              display: "flex",
              gap: 12,
              alignItems: "flex-start",
            }}
          >
            <Info
              size={16}
              style={{ color: "var(--info)", flexShrink: 0, marginTop: 2 }}
            />
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>
              <strong style={{ color: "var(--text-primary)" }}>
                Downloads are hosted on GitHub Releases.
              </strong>{" "}
              DASH is open source. You can also build from source by cloning the{" "}
              <a href={config.repoUrl} target="_blank" rel="noopener noreferrer">
                repository
              </a>{" "}
              and following the build instructions.
            </div>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
