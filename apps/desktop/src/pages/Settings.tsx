import React, { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import UpdateModal from "@/components/UpdateModal";

export default function Settings() {
  const { user } = useAuthStore();
  const [apiUrl, setApiUrl] = useState("http://127.0.0.1:8000/api/v1");
  const [autoCheckUpdates, setAutoCheckUpdates] = useState(true);
  const [autoDownloadUpdates, setAutoDownloadUpdates] = useState(false);
  const [installOnExit, setInstallOnExit] = useState(false);
  const [showUpdateModal, setShowUpdateModal] = useState(false);

  useEffect(() => {
    // Load saved settings from localStorage
    const savedAutoCheck = localStorage.getItem("dash_auto_check_updates");
    const savedAutoDownload = localStorage.getItem("dash_auto_download_updates");
    const savedInstallOnExit = localStorage.getItem("dash_install_on_exit");
    
    if (savedAutoCheck !== null) setAutoCheckUpdates(JSON.parse(savedAutoCheck));
    if (savedAutoDownload !== null) setAutoDownloadUpdates(JSON.parse(savedAutoDownload));
    if (savedInstallOnExit !== null) setInstallOnExit(JSON.parse(savedInstallOnExit));
  }, []);

  useEffect(() => {
    localStorage.setItem("dash_auto_check_updates", JSON.stringify(autoCheckUpdates));
  }, [autoCheckUpdates]);

  useEffect(() => {
    localStorage.setItem("dash_auto_download_updates", JSON.stringify(autoDownloadUpdates));
    const dash = window.dash as any;
    if (dash?.updater?.setAutoDownload) {
      dash.updater.setAutoDownload(autoDownloadUpdates);
    }
  }, [autoDownloadUpdates]);

  useEffect(() => {
    localStorage.setItem("dash_install_on_exit", JSON.stringify(installOnExit));
    const dash = window.dash as any;
    if (dash?.updater?.setAutoInstallOnQuit) {
      dash.updater.setAutoInstallOnQuit(installOnExit);
    }
  }, [installOnExit]);

  const handleManualCheck = () => {
    setShowUpdateModal(true);
    const dash = window.dash as any;
    if (dash?.updater?.checkForUpdates) {
      dash.updater.checkForUpdates();
    }
  };

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

        {/* Updates */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Software Updates
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Automatically check for updates</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Periodically check GitHub for new versions</div>
              </div>
              <input
                type="checkbox"
                checked={autoCheckUpdates}
                onChange={(e) => setAutoCheckUpdates(e.target.checked)}
                style={{ width: 20, height: 20, cursor: "pointer" }}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Automatically download updates</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Download updates in the background when available</div>
              </div>
              <input
                type="checkbox"
                checked={autoDownloadUpdates}
                onChange={(e) => setAutoDownloadUpdates(e.target.checked)}
                style={{ width: 20, height: 20, cursor: "pointer" }}
              />
            </label>
            <label style={{ display: "flex", alignItems: "center", justifyContent: "space-between", cursor: "pointer" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Install updates on exit</div>
                <div style={{ fontSize: 12, color: "var(--text-secondary)" }}>Automatically install updates when closing the app</div>
              </div>
              <input
                type="checkbox"
                checked={installOnExit}
                onChange={(e) => setInstallOnExit(e.target.checked)}
                style={{ width: 20, height: 20, cursor: "pointer" }}
              />
            </label>
            <button
              onClick={handleManualCheck}
              className="px-4 py-2 bg-blue-600 hover:bg-blue-500 text-white font-medium rounded-lg transition-colors text-sm"
              style={{ alignSelf: "flex-start" }}
            >
              Check for Updates
            </button>
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
      
      <UpdateModal isOpen={showUpdateModal} onClose={() => setShowUpdateModal(false)} />
    </div>
  );
}