import { useState } from "react";
import { useAuthStore } from "@/stores/authStore";

export default function Settings() {
  const { user } = useAuthStore();
  const [apiUrl, setApiUrl] = useState("http://127.0.0.1:8000/api/v1");

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Settings</h2>
          <p className="page-subtitle">Configure your DASH assistant</p>
        </div>
      </div>

      <div style={{ display: "flex", flexDirection: "column", gap: 16, maxWidth: 600 }}>
        {/* Account */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Account
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 4 }}>
                Email
              </label>
              <input className="input" type="email" value={user?.email || ""} readOnly style={{ opacity: 0.6 }} />
            </div>
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 4 }}>
                User ID
              </label>
              <input className="input" type="text" value={user?.id || ""} readOnly style={{ opacity: 0.6 }} />
            </div>
          </div>
        </div>

        {/* Connection */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Connection
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 4 }}>
                Backend API URL
              </label>
              <input className="input" type="text" value={apiUrl} onChange={(e) => setApiUrl(e.target.value)} />
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="status-dot online" />
              <span style={{ fontSize: 13, color: "var(--text-secondary)" }}>
                Backend connection is configured
              </span>
            </div>
          </div>
        </div>

        {/* Appearance */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Appearance
          </h3>
          <p style={{ fontSize: 14, color: "var(--text-secondary)", marginBottom: 12 }}>
            DASH uses a dark glassmorphism theme by default.
          </p>
          <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
            <div style={{ width: 32, height: 32, borderRadius: 8, background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))" }} />
            <div>
              <div style={{ fontSize: 13, fontWeight: 500, color: "var(--text-primary)" }}>DASH Dark</div>
              <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Current theme</div>
            </div>
          </div>
        </div>

        {/* About */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            About
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8, fontSize: 14 }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-secondary)" }}>Version</span>
              <span style={{ color: "var(--text-primary)" }}>{window.dash?.version || "0.1.0"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-secondary)" }}>Platform</span>
              <span style={{ color: "var(--text-primary)" }}>{window.dash?.platform || "web"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span style={{ color: "var(--text-secondary)" }}>Electron</span>
              <span style={{ color: "var(--text-primary)" }}>{navigator.userAgent.includes("Electron") ? "Yes" : "No"}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}