import { memo } from "react";
import { useLocation } from "react-router-dom";

const pageTitles: Record<string, string> = {
  "/": "Dashboard",
  "/chat": "Chat",
  "/memory": "Memory",
  "/projects": "Projects",
  "/automation": "Automation",
  "/settings": "Settings",
};

function Header() {
  const location = useLocation();
  const title = pageTitles[location.pathname] || "DASH";

  return (
    <header
      className="glass"
      style={{
        height: "var(--header-height)",
        display: "flex",
        alignItems: "center",
        justifyContent: "space-between",
        padding: "0 24px",
        borderBottom: "1px solid var(--border-glass)",
        borderTop: "none",
        borderRadius: 0,
        zIndex: 50,
      }}
    >
      <div>
        <h1
          style={{
            fontSize: 16,
            fontWeight: 600,
            color: "var(--text-primary)",
          }}
        >
          {title}
        </h1>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
        <span
          className="status-dot online"
          style={{ marginRight: 4 }}
        />
        <span style={{ fontSize: 12, color: "var(--text-secondary)" }}>
          Connected
        </span>
      </div>
    </header>
  );
}

export default memo(Header);