import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";

import DashboardLoading from "./DashboardLoading";

export default function Dashboard() {
  const navigate = useNavigate();
  const [healthData, setHealthData] = useState<{ status: string; version: string; uptime: number } | null>(null);
  const [conversationCount, setConversationCount] = useState(0);
  const [memoryCount, setMemoryCount] = useState(0);
  const [isBackendOnline, setIsBackendOnline] = useState(false);
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    async function fetchData() {
      try {
        const res = await fetch("http://127.0.0.1:8000/api/v1/health", { headers: { "Content-Type": "application/json" } });
        const h = await res.json();
        setHealthData(h);
        setIsBackendOnline(true);
      } catch {
        setIsBackendOnline(false);
      }

      // Load actual conversation and memory counts
      try {
        const token = localStorage.getItem("dash_access_token");
        const headers: Record<string, string> = { "Content-Type": "application/json" };
        if (token) headers["Authorization"] = `Bearer ${token}`;

        const convRes = await fetch("http://127.0.0.1:8000/api/v1/conversations?limit=1&offset=0", { headers });
        const convData = await convRes.json();
        setConversationCount(convData.total || 0);

        const memRes = await fetch("http://127.0.0.1:8000/api/v1/memory?limit=1&offset=0", { headers });
        const memData = await memRes.json();
        setMemoryCount(memData.total || 0);
      } catch {
        // Ignore errors for counts
      }
      setIsLoading(false);
    }
    fetchData();
  }, []);

  if (isLoading) {
    return <DashboardLoading />;
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Dashboard</h2>
          <p className="page-subtitle">Overview of your DASH assistant</p>
        </div>
      </div>

      <div className="grid-4" style={{ marginBottom: 24 }}>
        <div
          className="glass-card animate-fade-in"
          style={{ padding: 20, cursor: "pointer" }}
          onClick={() => navigate("/chat")}
        >
          <div style={{ fontSize: 24, marginBottom: 12 }}>💬</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            {conversationCount}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Conversations</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>🧠</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            {memoryCount}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Memories</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>{isBackendOnline ? "🟢" : "🔴"}</div>
          <div
            style={{
              fontSize: 28,
              fontWeight: 700,
              color: isBackendOnline ? "var(--success)" : "var(--danger)",
              marginBottom: 4,
            }}
          >
            {isBackendOnline ? "Online" : "Offline"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Backend Status</div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 20 }}>
          <div style={{ fontSize: 24, marginBottom: 12 }}>📦</div>
          <div style={{ fontSize: 28, fontWeight: 700, color: "var(--text-primary)", marginBottom: 4 }}>
            {healthData?.version || "---"}
          </div>
          <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>Version</div>
        </div>
      </div>

      <div className="grid-2">
        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            Quick Actions
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <button className="btn" style={{ justifyContent: "flex-start", padding: "12px 16px" }} onClick={() => navigate("/chat")}>
              💬 Start a conversation
            </button>
            <button className="btn" style={{ justifyContent: "flex-start", padding: "12px 16px" }} onClick={() => navigate("/memory")}>
              🧠 Browse memories
            </button>
            <button className="btn" style={{ justifyContent: "flex-start", padding: "12px 16px" }} onClick={() => navigate("/projects")}>
              📁 View projects
            </button>
            <button className="btn" style={{ justifyContent: "flex-start", padding: "12px 16px" }} onClick={() => navigate("/automation")}>
              ⚡ Configure automation
            </button>
          </div>
        </div>

        <div className="glass-card animate-fade-in" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            System Info
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span style={{ color: "var(--text-secondary)" }}>Backend</span>
              <span style={{ color: isBackendOnline ? "var(--success)" : "var(--danger)", fontWeight: 500 }}>
                {isBackendOnline ? "Connected" : "Disconnected"}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span style={{ color: "var(--text-secondary)" }}>Version</span>
              <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>{healthData?.version || "---"}</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span style={{ color: "var(--text-secondary)" }}>Uptime</span>
              <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                {healthData?.uptime
                  ? `${Math.floor(healthData.uptime / 60)}m ${Math.floor(healthData.uptime % 60)}s`
                  : "---"}
              </span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 14 }}>
              <span style={{ color: "var(--text-secondary)" }}>Platform</span>
              <span style={{ color: "var(--text-primary)", fontWeight: 500 }}>
                {(window as any).dash?.platform || "web"}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}