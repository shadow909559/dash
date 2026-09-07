import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  Bot,
  Brain,
  Code,
  Search,
  FolderOpen,
  Globe,
  Server,
  RefreshCw,
  Check,
  X,
  Zap,
  Activity,
  ChevronDown,
  ChevronRight,
  AlertCircle,
  Settings,
  Cpu,
} from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Agent {
  id: string;
  name: string;
  role: string;
  provider: string;
  model: string;
  status: string;
  current_task: string;
  tasks_completed: number;
  tasks_failed: number;
  uptime_seconds: number;
  error: string;
}

interface Provider {
  name: string;
  display_name: string;
  type: string;
  enabled: boolean;
  model: string;
  base_url: string;
  has_api_key: boolean;
}

interface AgentPanelProps {
  selectedAgentId?: string;
  onSelectAgent: (agentId: string) => void;
  collapsed?: boolean;
}

const ROLE_ICONS: Record<string, React.ReactNode> = {
  general: <Bot size={14} />,
  coder: <Code size={14} />,
  researcher: <Search size={14} />,
  planner: <Brain size={14} />,
  executor: <Zap size={14} />,
  browser: <Globe size={14} />,
  file_manager: <FolderOpen size={14} />,
  devops: <Server size={14} />,
};

const STATUS_COLORS: Record<string, string> = {
  idle: "rgba(148, 163, 184, 0.6)",
  thinking: "rgba(59, 130, 246, 0.8)",
  executing: "rgba(234, 179, 8, 0.8)",
  speaking: "rgba(34, 197, 94, 0.8)",
  error: "rgba(63, 169, 245, 0.8)",
  offline: "rgba(100, 116, 139, 0.4)",
};

const ROLE_COLORS: Record<string, string> = {
  general: "rgba(139, 92, 246, 0.7)",
  coder: "rgba(59, 130, 246, 0.7)",
  researcher: "rgba(34, 197, 94, 0.7)",
  planner: "rgba(234, 179, 8, 0.7)",
  executor: "rgba(63, 169, 245, 0.7)",
  browser: "rgba(6, 182, 212, 0.7)",
  file_manager: "rgba(168, 85, 247, 0.7)",
  devops: "rgba(20, 184, 166, 0.7)",
};

export const AgentPanel: React.FC<AgentPanelProps> = ({
  selectedAgentId,
  onSelectAgent,
  collapsed = false,
}) => {
  const [agents, setAgents] = useState<Agent[]>([]);
  const [providers, setProviders] = useState<Provider[]>([]);
  const [activeProvider, setActiveProvider] = useState("ollama");
  const [showProviders, setShowProviders] = useState(false);
  const [loading, setLoading] = useState(true);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [agentsRes, providersRes] = await Promise.all([
        authFetch(`${API}/ai-os/agents`),
        authFetch(`${API}/ai-os/providers/config`),
      ]);
      if (agentsRes.ok) {
        const data = await agentsRes.json();
        setAgents(data.agents || []);
      }
      if (providersRes.ok) {
        const data = await providersRes.json();
        setProviders(data.providers || []);
        setActiveProvider(data.active_provider || "ollama");
      }
    } catch (err) {
      console.error("Failed to fetch agents/providers:", err);
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 10000); // Refresh every 10s
    return () => clearInterval(interval);
  }, [fetchData]);

  const switchProvider = async (providerName: string) => {
    try {
      await authFetch(`${API}/ai-os/providers/config`, {
        method: "POST",
        body: JSON.stringify({ provider: providerName }),
      });
      setActiveProvider(providerName);
    } catch (err) {
      console.error("Failed to switch provider:", err);
    }
  };

  if (collapsed) return null;

  const activeCount = agents.filter(
    (a) => a.status !== "idle" && a.status !== "offline"
  ).length;

  return (
    <div
      style={{
        width: 260,
        background: "rgba(15, 15, 20, 0.95)",
        borderRight: "1px solid rgba(255, 255, 255, 0.06)",
        display: "flex",
        flexDirection: "column",
        overflow: "hidden",
        flexShrink: 0,
      }}
    >
      {/* Header */}
      <div
        style={{
          padding: "14px 16px 10px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        }}
      >
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
            <Bot size={16} color="var(--dash-accent)" />
            <span
              style={{
                fontSize: 13,
                fontWeight: 600,
                color: "var(--dash-text-primary)",
                letterSpacing: 0.3,
              }}
            >
              AGENTS
            </span>
            {activeCount > 0 && (
              <span
                style={{
                  fontSize: 10,
                  background: "rgba(34, 197, 94, 0.15)",
                  color: "#22c55e",
                  padding: "2px 6px",
                  borderRadius: 8,
                  fontFamily: "monospace",
                }}
              >
                {activeCount} active
              </span>
            )}
          </div>
          <button
            onClick={fetchData}
            aria-label="Refresh agent data"
            style={{
              background: "none",
              border: "none",
              color: "var(--dash-text-muted)",
              cursor: "pointer",
              padding: 4,
            }}
          >
            <RefreshCw size={13} />
          </button>
        </div>
      </div>

      {/* Provider Selector */}
      <div
        style={{
          padding: "8px 12px",
          borderBottom: "1px solid rgba(255, 255, 255, 0.06)",
        }}
      >
        <button
          onClick={() => setShowProviders(!showProviders)}
          aria-label="Toggle provider list"
          aria-expanded={showProviders}
          style={{
            width: "100%",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            background: "rgba(255, 255, 255, 0.04)",
            border: "1px solid rgba(255, 255, 255, 0.08)",
            borderRadius: 8,
            padding: "8px 10px",
            color: "var(--dash-text-primary)",
            fontSize: 12,
            cursor: "pointer",
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <Cpu size={13} color="var(--dash-accent)" />
            <span style={{ fontWeight: 500 }}>
              {providers.find((p) => p.name === activeProvider)?.display_name ||
                activeProvider}
            </span>
          </div>
          {showProviders ? (
            <ChevronDown size={12} color="var(--dash-text-muted)" />
          ) : (
            <ChevronRight size={12} color="var(--dash-text-muted)" />
          )}
        </button>

        {showProviders && (
          <div style={{ marginTop: 6, display: "flex", flexDirection: "column", gap: 4 }}>
            {providers.map((p) => (
              <button
                key={p.name}
                onClick={() => switchProvider(p.name)}
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  background:
                    p.name === activeProvider
                      ? "rgba(139, 92, 246, 0.12)"
                      : "rgba(255, 255, 255, 0.02)",
                  border:
                    p.name === activeProvider
                      ? "1px solid rgba(139, 92, 246, 0.3)"
                      : "1px solid rgba(255, 255, 255, 0.05)",
                  borderRadius: 6,
                  padding: "6px 10px",
                  color: "var(--dash-text-primary)",
                  fontSize: 11,
                  cursor: "pointer",
                  textAlign: "left",
                }}
              >
                <div style={{ flex: 1 }}>
                  <div style={{ fontWeight: 500 }}>{p.display_name}</div>
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      fontFamily: "monospace",
                    }}
                  >
                    {p.model}
                  </div>
                </div>
                <div style={{ display: "flex", alignItems: "center", gap: 4 }}>
                  {p.type === "cloud" && (
                    <span
                      style={{
                        fontSize: 9,
                        background: p.has_api_key
                          ? "rgba(34, 197, 94, 0.15)"
                          : "rgba(63, 169, 245, 0.15)",
                        color: p.has_api_key ? "#22c55e" : "#3fa9f5",
                        padding: "1px 5px",
                        borderRadius: 4,
                      }}
                    >
                      {p.has_api_key ? "KEY SET" : "NO KEY"}
                    </span>
                  )}
                  {p.name === activeProvider && (
                    <Check size={12} color="var(--dash-accent)" />
                  )}
                </div>
              </button>
            ))}
          </div>
        )}
      </div>

      {/* Agent List */}
      <div
        style={{
          flex: 1,
          overflow: "auto",
          padding: "8px",
        }}
      >
        {loading && agents.length === 0 ? (
          <div
            style={{
              padding: 20,
              textAlign: "center",
              color: "var(--dash-text-muted)",
              fontSize: 11,
            }}
          >
            Loading agents...
          </div>
        ) : agents.length === 0 ? (
          <div
            style={{
              padding: 20,
              textAlign: "center",
              color: "var(--dash-text-muted)",
              fontSize: 11,
            }}
          >
            No agents registered
          </div>
        ) : (
          agents.map((agent) => {
            const isSelected = agent.id === selectedAgentId;
            return (
              <button
                key={agent.id}
                onClick={() => onSelectAgent(agent.id)}
                style={{
                  width: "100%",
                  display: "flex",
                  flexDirection: "column",
                  gap: 4,
                  background: isSelected
                    ? "rgba(139, 92, 246, 0.1)"
                    : "rgba(255, 255, 255, 0.02)",
                  border: isSelected
                    ? "1px solid rgba(139, 92, 246, 0.3)"
                    : "1px solid rgba(255, 255, 255, 0.04)",
                  borderRadius: 8,
                  padding: "8px 10px",
                  marginBottom: 4,
                  color: "var(--dash-text-primary)",
                  fontSize: 12,
                  cursor: "pointer",
                  textAlign: "left",
                  transition: "all 0.15s ease",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 8,
                  }}
                >
                  <div
                    style={{
                      color: ROLE_COLORS[agent.role] || "var(--dash-accent)",
                    }}
                  >
                    {ROLE_ICONS[agent.role] || <Bot size={14} />}
                  </div>
                  <span style={{ fontWeight: 500, flex: 1, fontSize: 11 }}>
                    {agent.name}
                  </span>
                  <div
                    style={{
                      width: 7,
                      height: 7,
                      borderRadius: "50%",
                      background: STATUS_COLORS[agent.status] || "#64748b",
                      boxShadow:
                        agent.status !== "idle" && agent.status !== "offline"
                          ? `0 0 6px ${STATUS_COLORS[agent.status]}`
                          : "none",
                    }}
                  />
                </div>

                {/* Current task */}
                {agent.current_task && (
                  <div
                    style={{
                      fontSize: 10,
                      color: STATUS_COLORS[agent.status] || "var(--dash-text-muted)",
                      fontFamily: "monospace",
                      whiteSpace: "nowrap",
                      overflow: "hidden",
                      textOverflow: "ellipsis",
                      paddingLeft: 22,
                    }}
                  >
                    {agent.status === "thinking" && "⏳ "}
                    {agent.status === "executing" && "⚡ "}
                    {agent.status === "speaking" && "🔊 "}
                    {agent.current_task}
                  </div>
                )}

                {/* Stats row */}
                <div
                  style={{
                    display: "flex",
                    gap: 8,
                    paddingLeft: 22,
                    fontSize: 9,
                    color: "var(--dash-text-muted)",
                    fontFamily: "monospace",
                  }}
                >
                  <span>{agent.provider}</span>
                  <span>✓{agent.tasks_completed}</span>
                  {agent.tasks_failed > 0 && (
                    <span style={{ color: "#3fa9f5" }}>
                      ✗{agent.tasks_failed}
                    </span>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>

      {/* Footer stats */}
      <div
        style={{
          padding: "8px 12px",
          borderTop: "1px solid rgba(255, 255, 255, 0.06)",
          fontSize: 10,
          color: "var(--dash-text-muted)",
          display: "flex",
          justifyContent: "space-between",
          fontFamily: "monospace",
        }}
      >
        <span>{agents.length} agents</span>
        <span>{activeCount} active</span>
      </div>
    </div>
  );
};

export default AgentPanel;
