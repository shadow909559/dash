import { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Menu, X, Github, ExternalLink } from "lucide-react";
import { useScrollPosition } from "@/hooks/useScrollPosition";
import { config } from "@/lib/config";

const NAV_ITEMS = [
  { path: "/", label: "Home" },
  { path: "/product", label: "Product" },
  { path: "/features", label: "Features" },
  { path: "/architecture", label: "Architecture" },
  { path: "/download", label: "Download" },
  { path: "/docs", label: "Docs" },
  { path: "/security", label: "Security" },
];

export function Header() {
  const { scrollY, isAtTop } = useScrollPosition();
  const [mobileOpen, setMobileOpen] = useState(false);
  const location = useLocation();
  const isScrolled = !isAtTop;

  useEffect(() => {
    setMobileOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    if (mobileOpen) {
      document.body.style.overflow = "hidden";
    } else {
      document.body.style.overflow = "";
    }
    return () => {
      document.body.style.overflow = "";
    };
  }, [mobileOpen]);

  return (
    <>
      <a href="#main-content" className="skip-to-content">
        Skip to content
      </a>

      <header
        style={{
          position: "fixed",
          top: 0,
          left: 0,
          right: 0,
          zIndex: 100,
          height: "var(--header-height)",
          display: "flex",
          alignItems: "center",
          background: isScrolled
            ? "rgba(10, 10, 15, 0.9)"
            : "rgba(10, 10, 15, 0.6)",
          backdropFilter: "blur(12px)",
          borderBottom: isScrolled
            ? "1px solid var(--border)"
            : "1px solid transparent",
          transition: "all var(--transition-base)",
          padding: "0 var(--content-padding)",
        }}
      >
        <div
          style={{
            maxWidth: "var(--max-width)",
            margin: "0 auto",
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          {/* Logo */}
          <Link
            to="/"
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
              textDecoration: "none",
              color: "var(--text-primary)",
            }}
          >
            <div
              style={{
                width: 28,
                height: 28,
                borderRadius: "var(--radius-sm)",
                background: "var(--bg-tertiary)",
                border: "1px solid var(--border)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                fontFamily: "var(--font-mono)",
                fontSize: 13,
                fontWeight: 700,
                color: "var(--accent)",
              }}
            >
              D
            </div>
            <span
              style={{
                fontFamily: "var(--font-mono)",
                fontWeight: 700,
                fontSize: 15,
                letterSpacing: "0.05em",
              }}
            >
              DASH
            </span>
          </Link>

          {/* Desktop Nav */}
          <nav
            style={{
              display: "flex",
              alignItems: "center",
              gap: 4,
            }}
            className="desktop-nav"
          >
            {NAV_ITEMS.map((item) => (
              <Link
                key={item.path}
                to={item.path}
                style={{
                  padding: "6px 12px",
                  fontSize: 13,
                  color:
                    location.pathname === item.path
                      ? "var(--text-primary)"
                      : "var(--text-secondary)",
                  textDecoration: "none",
                  borderRadius: "var(--radius-sm)",
                  transition: "all var(--transition-fast)",
                  fontWeight: location.pathname === item.path ? 500 : 400,
                  background:
                    location.pathname === item.path
                      ? "var(--bg-tertiary)"
                      : "transparent",
                }}
              >
                {item.label}
              </Link>
            ))}
          </nav>

          {/* Desktop Actions */}
          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: 8,
            }}
            className="desktop-actions"
          >
            <a
              href={config.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="btn btn--ghost btn--icon"
              aria-label="GitHub repository"
            >
              <Github size={16} />
            </a>
            <Link to="/download" className="btn btn--primary btn--sm">
              Download
            </Link>
          </div>

          {/* Mobile Toggle */}
          <button
            className="mobile-toggle"
            onClick={() => setMobileOpen(!mobileOpen)}
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            style={{
              display: "none",
              padding: 8,
              background: "none",
              border: "none",
              color: "var(--text-primary)",
              cursor: "pointer",
            }}
          >
            {mobileOpen ? <X size={20} /> : <Menu size={20} />}
          </button>
        </div>
      </header>

      {/* Mobile Menu Overlay */}
      <div
        className={`mobile-menu-overlay ${mobileOpen ? "mobile-menu-overlay--open" : ""}`}
        onClick={() => setMobileOpen(false)}
      />

      {/* Mobile Menu */}
      <div
        className={`mobile-menu ${mobileOpen ? "mobile-menu--open" : ""}`}
        role="dialog"
        aria-label="Navigation menu"
      >
        <button
          className="mobile-menu__close btn btn--ghost btn--icon"
          onClick={() => setMobileOpen(false)}
          aria-label="Close menu"
        >
          <X size={20} />
        </button>
        <nav className="mobile-menu__nav">
          {NAV_ITEMS.map((item) => (
            <Link
              key={item.path}
              to={item.path}
              className={`mobile-menu__link ${location.pathname === item.path ? "mobile-menu__link--active" : ""}`}
            >
              {item.label}
            </Link>
          ))}
          <hr className="divider" style={{ margin: "8px 0" }} />
          <Link to="/download" className="btn btn--primary" style={{ marginTop: 8 }}>
            Download DASH
          </Link>
          <a
            href={config.repoUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="btn btn--secondary"
            style={{ marginTop: 8 }}
          >
            <Github size={14} />
            GitHub
            <ExternalLink size={12} />
          </a>
        </nav>
      </div>

      <style>{`
        @media (max-width: 768px) {
          .desktop-nav, .desktop-actions { display: none !important; }
          .mobile-toggle { display: flex !important; }
        }
      `}</style>
    </>
  );
}
