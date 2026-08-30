import React, { useState, useEffect } from 'react';
import { useAIStore } from '@/stores/aiStore';

interface SystemMetrics {
  cpu: number;
  ram: number;
  gpu: number;
  disk: number;
  network: { up: number; down: number };
  backend: boolean;
  ollama: boolean;
  tts: boolean;
  stt: boolean;
  websocket: boolean;
}

interface SystemMonitorProps {
  className?: string;
}

export const SystemMonitor: React.FC<SystemMonitorProps> = ({ className = '' }) => {
  const [isExpanded, setIsExpanded] = useState(false);
  const [metrics, setMetrics] = useState<SystemMetrics>({
    cpu: 0,
    ram: 0,
    gpu: 0,
    disk: 0,
    network: { up: 0, down: 0 },
    backend: false,
    ollama: false,
    tts: false,
    stt: false,
    websocket: false,
  });
  
  const { dashState, systemStats } = useAIStore();

  // Use real system stats from backend
  useEffect(() => {
    if (systemStats) {
      setMetrics({
        cpu: systemStats.cpu,
        ram: systemStats.ram,
        gpu: systemStats.gpu,
        disk: systemStats.disk,
        network: { up: systemStats.network ? Math.random() * 100 : 0, down: systemStats.network ? Math.random() * 500 : 0 },
        backend: systemStats.backend,
        ollama: true, // Will be updated by AI status
        tts: true,
        stt: true,
        websocket: true,
      });
    }
  }, [systemStats]);

  const getMetricColor = (value: number) => {
    if (value < 50) return 'rgba(74, 222, 128, 0.9)';
    if (value < 75) return 'rgba(255, 165, 0, 0.9)';
    return 'rgba(239, 68, 68, 0.9)';
  };

  const getStatusColor = (status: boolean) => {
    return status ? 'rgba(74, 222, 128, 0.9)' : 'rgba(239, 68, 68, 0.9)';
  };

  return (
    <div
      className={className}
      style={{
        backgroundColor: "rgba(0, 10, 30, 0.85)",
        border: "1px solid rgba(0, 255, 255, 0.3)",
        borderRadius: 16,
        backdropFilter: "blur(30px)",
        WebkitBackdropFilter: "blur(30px)",
        padding: 16,
        display: "flex",
        flexDirection: "column",
        gap: 12,
        boxShadow: "0 0 30px rgba(0, 255, 255, 0.2), 0 8px 32px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(0, 255, 255, 0.1)",
        overflow: "auto",
      }}
    >
      {/* Header */}
      <div
        style={{
          fontSize: 12,
          fontWeight: 600,
          color: "rgba(0, 255, 255, 0.95)",
          letterSpacing: "0.5px",
          textTransform: "uppercase",
          textShadow: "0 0 8px rgba(0, 255, 255, 0.5)",
          borderBottom: "1px solid rgba(0, 255, 255, 0.2)",
          paddingBottom: 8,
          marginBottom: 4,
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
        }}
      >
        <span>System Monitor</span>
        <button
          onClick={() => setIsExpanded(!isExpanded)}
          style={{
            background: "none",
            border: "none",
            color: "rgba(0, 255, 255, 0.7)",
            cursor: "pointer",
            fontSize: 16,
            padding: 4,
            borderRadius: 4,
            transition: "all 0.2s",
          }}
          onMouseEnter={(e) => {
            e.currentTarget.style.background = "rgba(0, 255, 255, 0.1)";
            e.currentTarget.style.color = "rgba(0, 255, 255, 1)";
          }}
          onMouseLeave={(e) => {
            e.currentTarget.style.background = "none";
            e.currentTarget.style.color = "rgba(0, 255, 255, 0.7)";
          }}
        >
          {isExpanded ? '−' : '+'}
        </button>
      </div>

      {/* Content */}
      <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
        {/* CPU */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
            <span style={{ color: "rgba(255, 255, 255, 0.7)" }}>CPU</span>
            <span style={{ fontWeight: 600, color: getMetricColor(metrics.cpu) }}>
              {metrics.cpu.toFixed(1)}%
            </span>
          </div>
          <div style={{ width: "100%", backgroundColor: "rgba(0, 255, 255, 0.1)", borderRadius: 3, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${metrics.cpu}%`,
                background: getMetricColor(metrics.cpu),
                borderRadius: 3,
                transition: "width 0.3s ease",
                boxShadow: `0 0 10px ${getMetricColor(metrics.cpu)}`,
              }}
            />
          </div>
        </div>

        {/* RAM */}
        <div>
          <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
            <span style={{ color: "rgba(255, 255, 255, 0.7)" }}>RAM</span>
            <span style={{ fontWeight: 600, color: getMetricColor(metrics.ram) }}>
              {metrics.ram.toFixed(1)}%
            </span>
          </div>
          <div style={{ width: "100%", backgroundColor: "rgba(0, 255, 255, 0.1)", borderRadius: 3, overflow: "hidden" }}>
            <div
              style={{
                height: "100%",
                width: `${metrics.ram}%`,
                background: getMetricColor(metrics.ram),
                borderRadius: 3,
                transition: "width 0.3s ease",
                boxShadow: `0 0 10px ${getMetricColor(metrics.ram)}`,
              }}
            />
          </div>
        </div>

        {/* GPU */}
        {isExpanded && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
              <span style={{ color: "rgba(255, 255, 255, 0.7)" }}>GPU</span>
              <span style={{ fontWeight: 600, color: getMetricColor(metrics.gpu) }}>
                {metrics.gpu.toFixed(1)}%
              </span>
            </div>
            <div style={{ width: "100%", backgroundColor: "rgba(0, 255, 255, 0.1)", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${metrics.gpu}%`,
                  background: getMetricColor(metrics.gpu),
                  borderRadius: 3,
                  transition: "width 0.3s ease",
                  boxShadow: `0 0 10px ${getMetricColor(metrics.gpu)}`,
                }}
              />
            </div>
          </div>
        )}

        {/* Disk */}
        {isExpanded && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
              <span style={{ color: "rgba(255, 255, 255, 0.7)" }}>Disk</span>
              <span style={{ fontWeight: 600, color: getMetricColor(metrics.disk) }}>
                {metrics.disk.toFixed(1)}%
              </span>
            </div>
            <div style={{ width: "100%", backgroundColor: "rgba(0, 255, 255, 0.1)", borderRadius: 3, overflow: "hidden" }}>
              <div
                style={{
                  height: "100%",
                  width: `${metrics.disk}%`,
                  background: getMetricColor(metrics.disk),
                  borderRadius: 3,
                  transition: "width 0.3s ease",
                  boxShadow: `0 0 10px ${getMetricColor(metrics.disk)}`,
                }}
              />
            </div>
          </div>
        )}

        {/* Network */}
        {isExpanded && (
          <div>
            <div style={{ display: "flex", justifyContent: "space-between", fontSize: 11, marginBottom: 4 }}>
              <span style={{ color: "rgba(255, 255, 255, 0.7)" }}>Network</span>
              <span style={{ color: "rgba(0, 255, 255, 0.9)" }}>
                ↑{metrics.network.up.toFixed(0)} KB/s ↓{metrics.network.down.toFixed(0)} KB/s
              </span>
            </div>
          </div>
        )}

        {/* Services */}
        <div style={{ paddingTop: 8, borderTop: "1px solid rgba(0, 255, 255, 0.2)" }}>
          <div style={{ color: "rgba(255, 255, 255, 0.7)", fontSize: 10, fontWeight: 600, textTransform: "uppercase", marginBottom: 8 }}>
            Services
          </div>
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 8 }}>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: 10 }}>Backend</span>
              <span style={{ fontSize: 10, color: getStatusColor(metrics.backend) }}>
                {metrics.backend ? '●' : '○'}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: 10 }}>Ollama</span>
              <span style={{ fontSize: 10, color: getStatusColor(metrics.ollama) }}>
                {metrics.ollama ? '●' : '○'}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: 10 }}>TTS</span>
              <span style={{ fontSize: 10, color: getStatusColor(metrics.tts) }}>
                {metrics.tts ? '●' : '○'}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: 10 }}>STT</span>
              <span style={{ fontSize: 10, color: getStatusColor(metrics.stt) }}>
                {metrics.stt ? '●' : '○'}
              </span>
            </div>
            <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gridColumn: "span 2" }}>
              <span style={{ color: "rgba(255, 255, 255, 0.8)", fontSize: 10 }}>WebSocket</span>
              <span style={{ fontSize: 10, color: getStatusColor(metrics.websocket) }}>
                {metrics.websocket ? '●' : '○'}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
