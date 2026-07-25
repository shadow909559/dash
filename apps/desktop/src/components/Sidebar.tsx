import { useLocation, useNavigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";

const navItems = [
  { path: "/", label: "Dashboard", icon: "◈" },
  { path: "/chat", label: "Chat", icon: "💬" },
  { path: "/memory", label: "Memory", icon: "🧠" },
  { path: "/projects", label: "Projects", icon: "📁" },
  { path: "/automation", label: "Automation", icon: "⚡" },
  { path: "/settings", label: "Settings", icon: "⚙" },
];

export default function Sidebar() {
  const location = useLocation();
  const navigate = useNavigate();
  const { user, logout } = useAuthStore();

  return (
    <aside
      className="glass"
      style={{
        position: "fixed",
        left: 0,
        top: 0,
        bottom: 0,
        width: "var(--sidebar-width)",
        display: "flex",
        flexDirection: "column",
        zIndex: 100,
        borderRight: "1px solid var(--border-glass)",
        borderLeft: "none",
        borderRadius: 0,
      }}
    >
      {/* Logo */}
      <div
        style={{
          padding: "20px 20px 16px",
          borderBottom: "1px solid var(--border-glass)",
        }}
      >
        <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
          <div
            style={{
              width: 32,
              height: 32,
              borderRadius: 8,
              background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 16,
              fontWeight: 700,
              color: "white",
            }}
          >
            D
          </div>
          <span style={{ fontSize: 18, fontWeight: 600 }}>DASH</span>
        </div>
      </div>

      {/* Navigation */}
      <nav style={{ flex: 1, padding: "12px 8px", display: "flex", flexDirection: "column", gap: 2 }}>
        {navItems.map((item) => {
          const isActive =
            item.path === "/" ? location.pathname === "/" : location.pathname.startsWith(item.path);
          return (
            <button
              key={item.path}
              onClick={() => navigate(item.path)}
              className="btn-ghost"
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "10px 12px",
                borderRadius: "var(--radius-sm)",
                background: isActive ? "var(--bg-glass-hover)" : "transparent",
                border: isActive ? "1px solid var(--border-glass)" : "1px solid transparent",
                color: isActive ? "var(--text-primary)" : "var(--text-secondary)",
                fontSize: 14,
                fontWeight: isActive ? 500 : 400,
                transition: "all var(--transition-fast)",
                width: "100%",
                textAlign: "left",
              }}
            >
              <span style={{ fontSize: 16, width: 20, textAlign: "center" }}>{item.icon}</span>
              <span>{item.label}</span>
            </button>
          );
        })}
      </nav>

      {/* User section */}
      <div
        style={{
          padding: "12px 12px",
          borderTop: "1px solid var(--border-glass)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 10,
            padding: "8px 4px",
          }}
        >
          <div
            style={{
              width: 28,
              height: 28,
              borderRadius: "50%",
              background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 12,
              fontWeight: 600,
              color: "white",
            }}
          >
            {user?.email?.charAt(0).toUpperCase() || "U"}
          </div>
          <div style={{ flex: 1, minWidth: 0 }}>
            <div
              style={{
                fontSize: 13,
                fontWeight: 500,
                color: "var(--text-primary)",
                overflow: "hidden",
                textOverflow: "ellipsis",
                whiteSpace: "nowrap",
              }}
            >
              {user?.email || "User"}
            </div>
          </div>
          <button
            className="btn-ghost"
            onClick={logout}
            style={{ padding: "4px 8px", fontSize: 12, color: "var(--text-muted)" }}
            title="Sign out"
          >
            ✕
          </button>
        </div>
      </div>
    </aside>
  );
}