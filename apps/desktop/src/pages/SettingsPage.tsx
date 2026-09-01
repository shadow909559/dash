import React, { useState, useEffect, useCallback } from "react";
import { aiOs, health } from "@/lib/api";
import {
  Settings,
  RefreshCw,
  Server,
  Cpu,
  CheckCircle,
  XCircle,
  Mic,
  Palette,
  Shield,
  Info,
  Wifi,
  Database,
  Monitor,
  Smartphone,
  Globe,
  Sliders,
} from "lucide-react";
import { GlassCard, StatusIndicator } from "@/components/ultron";

export const SettingsPage: React.FC = () => {
  const [providers, setProviders] = useState<any[]>([]);
  const [healthStatus, setHealthStatus] = useState<any>(null);
  const [apiUrl] = useState(
    import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1"
  );
  const [loading, setLoading] = useState(true);
  const [activeSection, setActiveSection] = useState("connection");

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const [p, h] = await Promise.all([
        aiOs.listProviders(),
        health.check(),
      ]);
      setProviders(p.providers || []);
      setHealthStatus(h);
    } catch {}
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  const sections = [
    { id: "connection", label: "Connection", icon: Server },
    { id: "ai", label: "AI Providers", icon: Cpu },
    { id: "voice", label: "Voice", icon: Mic },
    { id: "appearance", label: "Appearance", icon: Palette },
    { id: "security", label: "Security", icon: Shield },
    { id: "integrations", label: "Integrations", icon: Globe },
    { id: "about", label: "About", icon: Info },
  ];

  return (
    <div style={{ display: "flex", height: "100%", overflow: "hidden" }}>
      {/* Left: Section Navigation */}
      <div
        style={{
          width: 200,
          borderRight: "1px solid var(--dash-border)",
          backgroundColor: "var(--dash-surface)",
          padding: "16px 10px",
          display: "flex",
          flexDirection: "column",
          gap: 2,
        }}
      >
        <div
          style={{
            padding: "4px 10px 12px",
            fontSize: 11,
            fontWeight: 600,
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            color: "var(--dash-text-muted)",
            display: "flex",
            alignItems: "center",
            gap: 6,
          }}
        >
          <Sliders size={12} />
          Settings
        </div>
        {sections.map((s) => {
          const Icon = s.icon;
          const isActive = activeSection === s.id;
          return (
            <button
              key={s.id}
              onClick={() => setActiveSection(s.id)}
              style={{
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "8px 12px",
                borderRadius: "var(--dash-radius-sm)",
                border: "none",
                cursor: "pointer",
                background: isActive
                  ? "var(--ultron-surface)"
                  : "transparent",
                color: isActive
                  ? "var(--ultron-text)"
                  : "var(--dash-text-secondary)",
                borderLeft: isActive
                  ? "2px solid var(--dash-accent)"
                  : "2px solid transparent",
                fontSize: 12,
                fontWeight: isActive ? 600 : 400,
                textAlign: "left",
                transition: "all var(--dash-transition-fast)",
                width: "100%",
              }}
            >
              <Icon
                size={14}
                style={{
                  color: isActive
                    ? "var(--dash-accent)"
                    : "var(--dash-text-muted)",
                }}
              />
              {s.label}
            </button>
          );
        })}
      </div>

      {/* Right: Content */}
      <div
        style={{
          flex: 1,
          overflowY: "auto",
          padding: "24px 32px",
        }}
      >
        {activeSection === "connection" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              Connection
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              Backend connectivity and API endpoint configuration
            </p>

            <GlassCard glow padding={18}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Server size={16} style={{ color: "var(--dash-accent)" }} />
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                  }}
                >
                  Backend Status
                </span>
                {healthStatus && (
                  <StatusIndicator
                    status={
                      healthStatus.status === "ok" ? "online" : "offline"
                    }
                    label={
                      healthStatus.status === "ok"
                        ? "Connected"
                        : "Disconnected"
                    }
                  />
                )}
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                }}
              >
                {[
                  { label: "Endpoint", value: apiUrl },
                  {
                    label: "Version",
                    value: healthStatus?.version || "--",
                  },
                  {
                    label: "Uptime",
                    value: healthStatus?.uptime
                      ? `${Math.floor(healthStatus.uptime / 60)}m ${Math.floor(healthStatus.uptime % 60)}s`
                      : "--",
                  },
                  {
                    label: "Environment",
                    value: healthStatus?.environment || "development",
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      padding: "10px 14px",
                      borderRadius: "var(--dash-radius-sm)",
                      background: "var(--dash-bg-subtle)",
                      border: "1px solid var(--dash-border-subtle)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        marginBottom: 3,
                        fontFamily: "'JetBrains Mono', monospace",
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.label}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        )}

        {activeSection === "ai" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              AI Providers
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              Configured language models and their health status
            </p>
            {loading ? (
              <div
                style={{
                  fontSize: 12,
                  color: "var(--dash-text-muted)",
                  textAlign: "center",
                  padding: 32,
                }}
              >
                <RefreshCw
                  size={16}
                  className="animate-rotate"
                  style={{ display: "inline", marginRight: 8 }}
                />
                Loading providers...
              </div>
            ) : providers.length === 0 ? (
              <GlassCard padding={24} style={{ textAlign: "center" }}>
                <Cpu
                  size={32}
                  style={{
                    color: "var(--dash-text-muted)",
                    marginBottom: 12,
                    opacity: 0.5,
                  }}
                />
                <div
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                    marginBottom: 6,
                  }}
                >
                  No AI providers configured
                </div>
                <div
                  style={{ fontSize: 12, color: "var(--dash-text-muted)" }}
                >
                  Install and start Ollama to enable local AI capabilities.
                </div>
              </GlassCard>
            ) : (
              providers.map((p: any, i: number) => (
                <GlassCard key={i} padding={14} className="dash-card-glow">
                  <div
                    style={{
                      display: "flex",
                      alignItems: "center",
                      gap: 12,
                    }}
                  >
                    {p.healthy ? (
                      <CheckCircle size={16} color="var(--dash-success)" />
                    ) : (
                      <XCircle size={16} color="var(--dash-danger)" />
                    )}
                    <div style={{ flex: 1 }}>
                      <div
                        style={{
                          fontSize: 13,
                          fontWeight: 600,
                          color: "var(--dash-text)",
                        }}
                      >
                        {p.name || p.provider}
                      </div>
                      <div
                        style={{
                          fontSize: 11,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                          marginTop: 2,
                        }}
                      >
                        {p.model}
                      </div>
                    </div>
                    <span
                      className={`dash-badge ${p.healthy ? "dash-badge-success" : "dash-badge-danger"}`}
                    >
                      {p.healthy ? "Healthy" : "Unhealthy"}
                    </span>
                  </div>
                </GlassCard>
              ))
            )}
          </div>
        )}

        {activeSection === "voice" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              Voice
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              Speech-to-text and text-to-speech configuration
            </p>
            <GlassCard padding={18}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Mic size={16} style={{ color: "var(--dash-accent)" }} />
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                  }}
                >
                  Voice System
                </span>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--dash-text-secondary)",
                  lineHeight: 1.6,
                }}
              >
                Voice input is available through the Chat and dedicated Voice
                pages. Speech recognition uses the browser's built-in Web Speech
                API when available, or routes through the backend STT service
                via WebSocket.
              </div>
              <div
                style={{
                  marginTop: 14,
                  padding: "10px 14px",
                  borderRadius: "var(--dash-radius-sm)",
                  background: "var(--dash-bg-subtle)",
                  border: "1px solid var(--dash-border-subtle)",
                  fontSize: 11,
                  color: "var(--dash-text-muted)",
                  fontFamily: "'JetBrains Mono', monospace",
                }}
              >
                Supported: Web Speech API, Backend STT, Ollama Whisper (when
                configured)
              </div>
            </GlassCard>
          </div>
        )}

        {activeSection === "appearance" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              Appearance
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              Visual theme and display preferences
            </p>
            <GlassCard padding={18}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Palette size={16} style={{ color: "var(--dash-accent)" }} />
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                  }}
                >
                  Theme
                </span>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--dash-text-secondary)",
                  marginBottom: 14,
                }}
              >
                DASH uses a dark-first cyan-blue design with glowing elements.
                The theme adapts to system state with dynamic Orb animations
                and status indicators.
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                }}
              >
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--ultron-surface)",
                    border: "2px solid var(--dash-accent)",
                    boxShadow: "0 0 16px var(--dash-accent-glow)",
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--dash-accent)",
                    }}
                  >
                    JARVIS Cyan
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      marginTop: 2,
                    }}
                  >
                    Active theme
                  </div>
                </div>
                <div
                  style={{
                    padding: "12px 14px",
                    borderRadius: "var(--dash-radius-sm)",
                    background: "var(--dash-bg-subtle)",
                    border: "1px solid var(--dash-border-subtle)",
                    opacity: 0.5,
                  }}
                >
                  <div
                    style={{
                      fontSize: 12,
                      fontWeight: 600,
                      color: "var(--dash-text-muted)",
                    }}
                  >
                    Light Mode
                  </div>
                  <div
                    style={{
                      fontSize: 10,
                      color: "var(--dash-text-muted)",
                      marginTop: 2,
                    }}
                  >
                    Coming soon
                  </div>
                </div>
              </div>
            </GlassCard>
          </div>
        )}

        {activeSection === "security" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              Security
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              Device authentication and access control
            </p>
            <GlassCard glow padding={18}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                  marginBottom: 12,
                }}
              >
                <Shield size={16} style={{ color: "var(--dash-success)" }} />
                <span
                  style={{
                    fontSize: 14,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                  }}
                >
                  Device Authentication
                </span>
                <span
                  className="dash-badge dash-badge-success"
                  style={{ marginLeft: "auto" }}
                >
                  Active
                </span>
              </div>
              <div
                style={{
                  fontSize: 12,
                  color: "var(--dash-text-secondary)",
                  lineHeight: 1.6,
                  marginBottom: 14,
                }}
              >
                DASH uses device-token authentication for all API and WebSocket
                connections. Tokens are stored locally and never exposed to
                external services.
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: 10,
                }}
              >
                {[
                  {
                    label: "REST Auth",
                    value: "Bearer Token",
                    icon: <Database size={12} />,
                  },
                  {
                    label: "WebSocket Auth",
                    value: "Query Token",
                    icon: <Wifi size={12} />,
                  },
                  {
                    label: "Device Pairing",
                    value: "Code + Token",
                    icon: <Smartphone size={12} />,
                  },
                  {
                    label: "File Access",
                    value: "Path Allowlist",
                    icon: <Monitor size={12} />,
                  },
                ].map((item) => (
                  <div
                    key={item.label}
                    style={{
                      padding: "10px 14px",
                      borderRadius: "var(--dash-radius-sm)",
                      background: "var(--dash-bg-subtle)",
                      border: "1px solid var(--dash-border-subtle)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        marginBottom: 3,
                        display: "flex",
                        alignItems: "center",
                        gap: 4,
                        fontFamily: "'JetBrains Mono', monospace",
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.icon} {item.label}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        )}

        {activeSection === "integrations" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              Integrations
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              External service connections and cloud infrastructure
            </p>
            {[
              {
                name: "Obsidian",
                desc: "Vault integration for note-taking and knowledge management",
                status: "active",
                color: "var(--dash-accent)",
              },
              {
                name: "Supabase",
                desc: "Cloud database and authentication (optional)",
                status: "available",
                color: "var(--dash-success)",
              },
              {
                name: "AWS",
                desc: "Cloud storage, monitoring, and infrastructure (optional)",
                status: "available",
                color: "var(--dash-warning)",
              },
              {
                name: "GitHub",
                desc: "Repository integration for code management (optional)",
                status: "available",
                color: "var(--dash-text-secondary)",
              },
            ].map((int) => (
              <GlassCard
                key={int.name}
                padding={16}
                className="dash-card-glow"
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    gap: 14,
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "var(--dash-radius-sm)",
                      background: `color-mix(in srgb, ${int.color} 8%, transparent)`,
                      border: `1px solid color-mix(in srgb, ${int.color} 15%, transparent)`,
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                    }}
                  >
                    <Globe size={18} style={{ color: int.color }} />
                  </div>
                  <div style={{ flex: 1 }}>
                    <div
                      style={{
                        fontSize: 13,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                      }}
                    >
                      {int.name}
                    </div>
                    <div
                      style={{
                        fontSize: 11,
                        color: "var(--dash-text-muted)",
                        marginTop: 2,
                      }}
                    >
                      {int.desc}
                    </div>
                  </div>
                  <span
                    className={`dash-badge ${int.status === "active" ? "dash-badge-success" : "dash-badge-neutral"}`}
                  >
                    {int.status}
                  </span>
                </div>
              </GlassCard>
            ))}
          </div>
        )}

        {activeSection === "about" && (
          <div>
            <h2
              style={{
                fontSize: 18,
                fontWeight: 700,
                color: "var(--dash-text)",
                marginBottom: 4,
              }}
            >
              About DASH
            </h2>
            <p
              style={{
                fontSize: 12,
                color: "var(--dash-text-secondary)",
                marginBottom: 20,
              }}
            >
              System information and version details
            </p>
            <GlassCard glow padding={20}>
              <div
                style={{
                  display: "flex",
                  alignItems: "center",
                  gap: 14,
                  marginBottom: 20,
                }}
              >
                <div
                  style={{
                    width: 52,
                    height: 52,
                    borderRadius: "var(--dash-radius-md)",
                    background:
                      "linear-gradient(135deg, var(--dash-accent), var(--dash-accent-secondary))",
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "center",
                    boxShadow: "0 0 24px var(--dash-accent-glow)",
                  }}
                >
                  <Shield size={24} color="white" />
                </div>
                <div>
                  <div
                    style={{
                      fontSize: 20,
                      fontWeight: 700,
                      color: "var(--dash-text)",
                    }}
                  >
                    DASH OS
                  </div>
                  <div
                    style={{
                      fontSize: 12,
                      color: "var(--dash-text-muted)",
                      fontFamily: "'JetBrains Mono', monospace",
                    }}
                  >
                    AI Operating System v{healthStatus?.version || "0.1.0"}
                  </div>
                </div>
              </div>
              <div
                style={{
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr 1fr",
                  gap: 10,
                }}
              >
                {[
                  {
                    label: "Version",
                    value: healthStatus?.version || "0.1.0",
                  },
                  {
                    label: "Backend",
                    value:
                      healthStatus?.status === "ok" ? "Online" : "Offline",
                  },
                  {
                    label: "Providers",
                    value: `${providers.length} configured`,
                  },
                  {
                    label: "Healthy",
                    value: `${providers.filter((p: any) => p.healthy).length}/${providers.length}`,
                  },
                  { label: "Desktop", value: "Electron + React" },
                  { label: "Backend", value: "FastAPI + Python" },
                ].map((item) => (
                  <div
                    key={item.label + item.value}
                    style={{
                      padding: "10px 14px",
                      borderRadius: "var(--dash-radius-sm)",
                      background: "var(--dash-bg-subtle)",
                      border: "1px solid var(--dash-border-subtle)",
                    }}
                  >
                    <div
                      style={{
                        fontSize: 10,
                        color: "var(--dash-text-muted)",
                        marginBottom: 3,
                        fontFamily: "'JetBrains Mono', monospace",
                        letterSpacing: "0.05em",
                        textTransform: "uppercase",
                      }}
                    >
                      {item.label}
                    </div>
                    <div
                      style={{
                        fontSize: 12,
                        fontWeight: 600,
                        color: "var(--dash-text)",
                        fontFamily: "'JetBrains Mono', monospace",
                      }}
                    >
                      {item.value}
                    </div>
                  </div>
                ))}
              </div>
            </GlassCard>
          </div>
        )}
      </div>
    </div>
  );
};

export default SettingsPage;
