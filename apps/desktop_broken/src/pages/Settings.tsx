import { useState, useEffect } from "react";
import { useAuthStore } from "@/stores/authStore";
import { useSettingsStore } from "@/stores/settingsStore";
import { useSidebarStore } from "@/stores/sidebarStore";
import { notify } from "@/components/Toast";
import { ipcRenderer } from "electron";

export default function Settings() {
  const { user } = useAuthStore();
  const { 
    theme, fontSize, sidebarState, startupPage, notificationPreferences, 
    autoLaunch, startMinimized, minimizeToTray, apiUrl, updateSettings 
  } = useSettingsStore();
  const { isCollapsed, toggleSidebar } = useSidebarStore();
  
  // Local state for all settings
  const [localApiUrl, setLocalApiUrl] = useState(apiUrl);
  const [localAutoLaunch, setLocalAutoLaunch] = useState(autoLaunch);
  const [localNotificationsEnabled, setLocalNotificationsEnabled] = useState(notificationPreferences.enabled);
  const [localNotificationsSound, setLocalNotificationsSound] = useState(notificationPreferences.sound);
  const [localMinToTray, setLocalMinToTray] = useState(minimizeToTray);
  const [localStartMin, setLocalStartMin] = useState(startMinimized);
  const [localTheme, setLocalTheme] = useState(theme);
  const [localFontSize, setLocalFontSize] = useState(fontSize);
  const [localStartupPage, setLocalStartupPage] = useState(startupPage);
  
  // Sync sidebar state with settings store
  useEffect(() => {
    if (sidebarState !== isCollapsed) {
      if (sidebarState && !isCollapsed) toggleSidebar();
      if (!sidebarState && isCollapsed) toggleSidebar();
    }
  }, [sidebarState, isCollapsed, toggleSidebar]);
  
  // Apply font size to document when it changes
  useEffect(() => {
    document.documentElement.style.fontSize = `${localFontSize}px`;
  }, [localFontSize]);
  
  const saveSettings = async () => {
    updateSettings({
      apiUrl: localApiUrl,
      autoLaunch: localAutoLaunch,
      notificationPreferences: { 
        enabled: localNotificationsEnabled, 
        sound: localNotificationsSound 
      },
      minimizeToTray: localMinToTray,
      startMinimized: localStartMin,
      sidebarState: isCollapsed,
      theme: localTheme,
      fontSize: localFontSize,
      startupPage: localStartupPage,
    });
    
    // Send to main process
    if (ipcRenderer) {
      try {
        await ipcRenderer.invoke('settings:setAutoLaunch', localAutoLaunch);
        if (localMinToTray) {
          ipcRenderer.send('tray:enableMinToTray');
        }
        if (localStartMin) {
          ipcRenderer.send('window:setStartMinimized');
        }
      } catch (err) {
        console.error('Failed to send settings to main process:', err);
      }
    }
    
    notify({
      title: "Settings saved",
      message: "Your preferences have been updated",
      type: "success"
    });
  };
  
  const resetSettings = () => {
    useSettingsStore.getState().resetSettings();
    const defaultSettings = useSettingsStore.getState();
    
    setLocalApiUrl(defaultSettings.apiUrl);
    setLocalAutoLaunch(defaultSettings.autoLaunch);
    setLocalNotificationsEnabled(defaultSettings.notificationPreferences.enabled);
    setLocalNotificationsSound(defaultSettings.notificationPreferences.sound);
    setLocalMinToTray(defaultSettings.minimizeToTray);
    setLocalStartMin(defaultSettings.startMinimized);
    setLocalTheme(defaultSettings.theme);
    setLocalFontSize(defaultSettings.fontSize);
    setLocalStartupPage(defaultSettings.startupPage);
    
    notify({
      title: "Settings reset",
      message: "All preferences have been reset to defaults",
      type: "info"
    });
  };

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Settings</h2>
          <p className="page-subtitle">Configure your DASH assistant</p>
        </div>
        <div className="flex gap-3">
          <button 
            onClick={resetSettings}
            className="px-4 py-2 rounded-lg text-sm font-medium text-gray-300 hover:text-white bg-gray-800 hover:bg-gray-700 transition-colors"
          >
            Reset to Defaults
          </button>
          <button 
            onClick={saveSettings}
            className="px-4 py-2 rounded-lg text-sm font-medium text-white bg-blue-600 hover:bg-blue-500 transition-colors"
          >
            Save Changes
          </button>
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
              <input 
                className="input" 
                type="text" 
                value={localApiUrl} 
                onChange={(e) => setLocalApiUrl(e.target.value)} 
              />
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
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>
                Theme
              </label>
              <div className="flex gap-3">
                <button
                  onClick={() => setLocalTheme('dark')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    localTheme === 'dark' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Dark
                </button>
                <button
                  onClick={() => setLocalTheme('light')}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    localTheme === 'light' 
                      ? 'bg-blue-600 text-white' 
                      : 'bg-gray-800 text-gray-300 hover:bg-gray-700'
                  }`}
                >
                  Light
                </button>
              </div>
            </div>
            
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>
                Font Size: {localFontSize}px
              </label>
              <input
                type="range"
                min="12"
                max="18"
                value={localFontSize}
                onChange={(e) => setLocalFontSize(Number(e.target.value))}
                className="w-full h-2 bg-gray-700 rounded-lg appearance-none cursor-pointer accent-blue-600"
              />
              <div className="flex justify-between text-xs text-gray-500 mt-1">
                <span>12px</span>
                <span>18px</span>
              </div>
            </div>
            
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>
                Sidebar
              </label>
              <div className="flex items-center gap-3">
                <button
                  onClick={toggleSidebar}
                  className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                    isCollapsed 
                      ? 'bg-gray-800 text-gray-300 hover:bg-gray-700' 
                      : 'bg-blue-600 text-white'
                  }`}
                >
                  {isCollapsed ? 'Collapsed' : 'Expanded'}
                </button>
                <span className="text-xs text-gray-500">
                  Click to toggle sidebar state
                </span>
              </div>
            </div>
          </div>
        </div>

        {/* Startup Settings */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Startup
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div>
              <label style={{ display: "block", fontSize: 13, fontWeight: 500, color: "var(--text-secondary)", marginBottom: 8 }}>
                Default Startup Page
              </label>
              <select
                value={localStartupPage}
                onChange={(e) => setLocalStartupPage(e.target.value)}
                className="w-full p-2 rounded-lg bg-gray-800 text-white border border-gray-700 focus:outline-none focus:border-blue-500"
              >
                <option value="/">Dashboard</option>
                <option value="/projects">Projects</option>
                <option value="/automation">Automation</option>
                <option value="/chat">Chat</option>
              </select>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Launch on system startup</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Automatically start DASH when you log in</div>
              </div>
              <button
                onClick={() => setLocalAutoLaunch(!localAutoLaunch)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  localAutoLaunch ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${
                  localAutoLaunch ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Start minimized</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Start DASH minimized to tray</div>
              </div>
              <button
                onClick={() => setLocalStartMin(!localStartMin)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  localStartMin ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${
                  localStartMin ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        </div>

        {/* Notifications */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            Notifications
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="flex items-center justify-between">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Enable notifications</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Show desktop notifications for important events</div>
              </div>
              <button
                onClick={() => setLocalNotificationsEnabled(!localNotificationsEnabled)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  localNotificationsEnabled ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${
                  localNotificationsEnabled ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
            
            <div className="flex items-center justify-between">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Notification sounds</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Play a sound when notifications arrive</div>
              </div>
              <button
                onClick={() => setLocalNotificationsSound(!localNotificationsSound)}
                disabled={!localNotificationsEnabled}
                className={`w-12 h-6 rounded-full transition-colors ${
                  localNotificationsEnabled 
                    ? (localNotificationsSound ? 'bg-blue-600' : 'bg-gray-700')
                    : 'bg-gray-800 opacity-50 cursor-not-allowed'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${
                  localNotificationsSound ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
            </div>
          </div>
        </div>

        {/* System Tray */}
        <div className="glass-card" style={{ padding: 24 }}>
          <h3 style={{ fontSize: 16, fontWeight: 600, color: "var(--text-primary)", marginBottom: 16 }}>
            System Tray
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
            <div className="flex items-center justify-between">
              <div>
                <div style={{ fontSize: 14, fontWeight: 500, color: "var(--text-primary)" }}>Minimize to tray</div>
                <div style={{ fontSize: 12, color: "var(--text-muted)" }}>Keep DASH running in the system tray when minimized</div>
              </div>
              <button
                onClick={() => setLocalMinToTray(!localMinToTray)}
                className={`w-12 h-6 rounded-full transition-colors ${
                  localMinToTray ? 'bg-blue-600' : 'bg-gray-700'
                }`}
              >
                <div className={`w-5 h-5 rounded-full bg-white transform transition-transform ${
                  localMinToTray ? 'translate-x-6' : 'translate-x-0.5'
                }`} />
              </button>
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