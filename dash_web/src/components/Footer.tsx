import { Link } from "react-router-dom";
import { Github, ExternalLink } from "lucide-react";
import { config } from "@/lib/config";

export function Footer() {
  return (
    <footer
      style={{
        borderTop: "1px solid var(--border)",
        padding: "48px 0 32px",
        marginTop: 80,
      }}
    >
      <div className="container">
        <div
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fit, minmax(160px, 1fr))",
            gap: 32,
            marginBottom: 40,
          }}
        >
          {/* Product */}
          <div>
            <h4
              style={{
                fontSize: 12,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-muted)",
                marginBottom: 12,
              }}
            >
              Product
            </h4>
            <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Link to="/product" className="footer-link">
                Overview
              </Link>
              <Link to="/features" className="footer-link">
                Features
              </Link>
              <Link to="/architecture" className="footer-link">
                Architecture
              </Link>
              <Link to="/download" className="footer-link">
                Download
              </Link>
            </nav>
          </div>

          {/* Resources */}
          <div>
            <h4
              style={{
                fontSize: 12,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-muted)",
                marginBottom: 12,
              }}
            >
              Resources
            </h4>
            <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Link to="/docs" className="footer-link">
                Documentation
              </Link>
              <Link to="/quickstart" className="footer-link">
                Quick Start
              </Link>
              <Link to="/troubleshooting" className="footer-link">
                Troubleshooting
              </Link>
              <a
                href={config.issuesUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="footer-link"
              >
                Report Issue
                <ExternalLink size={10} />
              </a>
            </nav>
          </div>

          {/* Legal */}
          <div>
            <h4
              style={{
                fontSize: 12,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-muted)",
                marginBottom: 12,
              }}
            >
              Legal
            </h4>
            <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <Link to="/privacy" className="footer-link">
                Privacy Policy
              </Link>
              <Link to="/terms" className="footer-link">
                Terms & Conditions
              </Link>
              <Link to="/cookies" className="footer-link">
                Cookie Policy
              </Link>
              <Link to="/accessibility" className="footer-link">
                Accessibility
              </Link>
            </nav>
          </div>

          {/* Community */}
          <div>
            <h4
              style={{
                fontSize: 12,
                fontWeight: 600,
                textTransform: "uppercase",
                letterSpacing: "0.08em",
                color: "var(--text-muted)",
                marginBottom: 12,
              }}
            >
              Community
            </h4>
            <nav style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              <a
                href={config.repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="footer-link"
              >
                <Github size={12} />
                GitHub
                <ExternalLink size={10} />
              </a>
              <a
                href={`${config.repoUrl}/issues`}
                target="_blank"
                rel="noopener noreferrer"
                className="footer-link"
              >
                Issues
                <ExternalLink size={10} />
              </a>
            </nav>
          </div>
        </div>

        <div
          style={{
            borderTop: "1px solid var(--border)",
            paddingTop: 24,
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            flexWrap: "wrap",
            gap: 16,
          }}
        >
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              fontSize: 13,
              color: "var(--text-muted)",
            }}
          >
            <div
              style={{
                width: 20,
                height: 20,
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "var(--font-mono)",
                fontSize: 10,
                fontWeight: 700,
                color: "var(--accent)",
              }}
            >
              D
            </div>
            <span style={{ fontFamily: "var(--font-mono)" }}>DASH</span>
            <span>v{config.version}</span>
          </div>
          <p style={{ fontSize: 12, color: "var(--text-muted)" }}>
            Open source personal AI operating system.
          </p>
        </div>
      </div>

      <style>{`
        .footer-link {
          display: inline-flex;
          align-items: center;
          gap: 4px;
          font-size: 13px;
          color: var(--text-secondary);
          text-decoration: none;
          transition: color var(--transition-fast);
        }
        .footer-link:hover {
          color: var(--text-primary);
        }
      `}</style>
    </footer>
  );
}
