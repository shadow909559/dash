import React, { useState, useEffect, useCallback } from "react";
import { desktop, windows, files } from "@/lib/api";
import {
  Monitor,
  Volume2,
  VolumeX,
  Lock,
  Power,
  Moon,
  Maximize,
  Minimize,
  RefreshCw,
  Camera,
  Clipboard,
  ClipboardCheck,
  X,
  Focus,
  FolderOpen,
  Search,
  File,
  FileText,
  Image,
  ChevronRight,
  ArrowUp,
  AlertCircle,
} from "lucide-react";

export const DesktopControlPage: React.FC = () => {
  const [volume, setVolume] = useState(50);
  const [muted, setMuted] = useState(false);
  const [brightness, setBrightness] = useState(75);
  const [windowList, setWindowList] = useState<Array<{ hwnd: number; title: string }>>([]);
  const [screenshot, setScreenshot] = useState<string | null>(null);
  const [showScreenshot, setShowScreenshot] = useState(false);
  const [clipboard, setClipboard] = useState<string | null>(null);
  const [clipboardCopied, setClipboardCopied] = useState(false);
  const [currentPath, setCurrentPath] = useState("C:/Users");
  const [filesList, setFilesList] = useState<Array<{ name: string; type: string; size: number }>>([]);
  const [loadingFiles, setLoadingFiles] = useState(false);
  const [loadingScreenshot, setLoadingScreenshot] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const refreshVolume = useCallback(async () => {
    try {
      const r = await desktop.getVolume();
      setVolume(r.volume);
      setMuted(r.muted);
      setError(null);
    } catch { setError("Failed to get volume"); }
  }, []);

  const refreshWindows = useCallback(async () => {
    try {
      const r = await windows.list();
      setWindowList(r.details.windows || []);
      setError(null);
    } catch { setError("Failed to list windows"); }
  }, []);

  const refreshClipboard = useCallback(async () => {
    try {
      const r = await desktop.clipboardRead();
      setClipboard(r.text || "");
      setError(null);
    } catch { setError("Failed to read clipboard"); }
  }, []);

  const browsePath = useCallback(async (path: string) => {
    setLoadingFiles(true);
    try {
      const r = await files.browse(path);
      setFilesList(r.entries || []);
      setCurrentPath(path);
      setError(null);
    } catch { setError("Failed to browse directory"); }
    setLoadingFiles(false);
  }, []);

  const takeScreenshot = async () => {
    setLoadingScreenshot(true);
    try {
      const r = await desktop.screenshot();
      setScreenshot(r.details.image_base64);
      setShowScreenshot(true);
      setError(null);
    } catch { setError("Failed to capture screenshot"); }
    setLoadingScreenshot(false);
  };

  const copyClipboard = async () => {
    if (clipboard) {
      await navigator.clipboard.writeText(clipboard);
      setClipboardCopied(true);
      setTimeout(() => setClipboardCopied(false), 2000);
    }
  };

  const navigateUp = () => {
    const parts = currentPath.replace(/\\/g, "/").split("/").filter(Boolean);
    if (parts.length > 1) {
      parts.pop();
      browsePath(parts.join("/"));
    }
  };

  useEffect(() => { refreshVolume(); refreshWindows(); refreshClipboard(); browsePath("C:/Users"); }, [refreshVolume, refreshWindows, refreshClipboard, browsePath]);

  const getFileIcon = (name: string, type: string) => {
    if (type === "directory") return <FolderOpen size={14} style={{ color: "var(--dash-warning)" }} />;
    const ext = name.split(".").pop()?.toLowerCase();
    if (["png", "jpg", "jpeg", "gif", "bmp", "webp"].includes(ext || "")) return <Image size={14} style={{ color: "var(--dash-cyan)" }} />;
    if (["txt", "md", "json", "py", "ts", "tsx", "js", "jsx", "css", "html"].includes(ext || "")) return <FileText size={14} style={{ color: "var(--dash-accent)" }} />;
    return <File size={14} style={{ color: "var(--dash-text-muted)" }} />;
  };

  return (
    <div style={{ padding: "20px 28px", maxWidth: 1200, margin: "0 auto", height: "100%", overflowY: "auto" }}>
      {/* Header */}
      <div className="dash-card" style={{ padding: "20px 24px", display: "flex", alignItems: "center", gap: 16, marginBottom: 18 }}>
        <div style={{ width: 44, height: 44, borderRadius: "var(--dash-radius-md)", backgroundColor: "var(--dash-accent-glow)", border: "1px solid var(--dash-border-accent)", display: "flex", alignItems: "center", justifyContent: "center" }}>
          <Monitor size={22} style={{ color: "var(--dash-accent)" }} />
        </div>
        <div style={{ flex: 1 }}>
          <h1 style={{ fontSize: 18, fontWeight: 700, color: "var(--dash-text)", margin: 0 }}>Desktop Control</h1>
          <p style={{ fontSize: 12, color: "var(--dash-text-secondary)", margin: "3px 0 0" }}>Native Windows automation and management</p>
        </div>
        <button onClick={takeScreenshot} disabled={loadingScreenshot} style={{ padding: "8px 14px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 12, display: "flex", alignItems: "center", gap: 6 }}>
          <Camera size={14} /> {loadingScreenshot ? "Capturing..." : "Screenshot"}
        </button>
      </div>

      {error && (
        <div className="dash-card animate-slide-up" style={{ padding: 12, marginBottom: 16, borderLeft: "3px solid #3fa9f5", display: "flex", alignItems: "center", gap: 10 }}>
          <AlertCircle size={14} style={{ color: "#3fa9f5", flexShrink: 0 }} />
          <span style={{ fontSize: 12, color: "#3fa9f5" }}>{error}</span>
          <button onClick={() => setError(null)} style={{ marginLeft: "auto", background: "none", border: "none", color: "var(--dash-text-muted)", cursor: "pointer" }}><X size={12} /></button>
        </div>
      )}

      {/* Controls Grid */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr 1fr", gap: 14, marginBottom: 16 }}>
        {/* Volume Control */}
        <div className="dash-card" style={{ padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            {muted ? <VolumeX size={16} style={{ color: "var(--dash-text-muted)" }} /> : <Volume2 size={16} style={{ color: "var(--dash-accent)" }} />}
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>Volume</span>
            <span style={{ fontSize: 12, color: "var(--dash-text-muted)", marginLeft: "auto", fontFamily: "JetBrains Mono, monospace" }}>{volume}%</span>
          </div>
          <input type="range" min={0} max={100} value={volume}
            onChange={async (e) => { const v = parseInt(e.target.value); setVolume(v); await desktop.setVolume(v); }}
            style={{ width: "100%", accentColor: "var(--dash-accent)", height: 4 }} />
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            <button onClick={async () => { await desktop.setMute(!muted); setMuted(!muted); }}
              style={{ flex: 1, padding: "5px 8px", borderRadius: "var(--dash-radius-sm)", border: `1px solid ${muted ? "rgba(63,169,245,0.3)" : "var(--dash-border)"}`, background: muted ? "rgba(63,169,245,0.1)" : "var(--dash-surface)", color: muted ? "#3fa9f5" : "var(--dash-text-secondary)", cursor: "pointer", fontSize: 11 }}>
              {muted ? "Unmute" : "Mute"}
            </button>
            <button onClick={async () => { await desktop.volumeUp(); refreshVolume(); }}
              style={{ flex: 1, padding: "5px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 11 }}>+5</button>
            <button onClick={async () => { await desktop.volumeDown(); refreshVolume(); }}
              style={{ flex: 1, padding: "5px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 11 }}>-5</button>
          </div>
        </div>

        {/* Brightness Control */}
        <div className="dash-card" style={{ padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Monitor size={16} style={{ color: "var(--dash-warning)" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>Brightness</span>
            <span style={{ fontSize: 12, color: "var(--dash-text-muted)", marginLeft: "auto", fontFamily: "JetBrains Mono, monospace" }}>{brightness}%</span>
          </div>
          <input type="range" min={0} max={100} value={brightness}
            onChange={async (e) => { const v = parseInt(e.target.value); setBrightness(v); try { await desktop.setBrightness(v); } catch {} }}
            style={{ width: "100%", accentColor: "var(--dash-warning)", height: 4 }} />
          <div style={{ display: "flex", gap: 6, marginTop: 10 }}>
            <button onClick={async () => { setBrightness(Math.max(0, brightness - 10)); try { await desktop.setBrightness(Math.max(0, brightness - 10)); } catch {} }}
              style={{ flex: 1, padding: "5px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 11 }}>-10</button>
            <button onClick={async () => { setBrightness(Math.min(100, brightness + 10)); try { await desktop.setBrightness(Math.min(100, brightness + 10)); } catch {} }}
              style={{ flex: 1, padding: "5px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 11 }}>+10</button>
          </div>
        </div>

        {/* Power Controls */}
        <div className="dash-card" style={{ padding: "16px 18px" }}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
            <Power size={16} style={{ color: "var(--dash-danger)" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>Power</span>
          </div>
          <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
            {[
              { label: "Lock", icon: <Lock size={12} />, action: () => desktop.lock(), color: "var(--dash-accent)" },
              { label: "Sleep", icon: <Moon size={12} />, action: () => desktop.sleep(), color: "var(--dash-accent-secondary)" },
              { label: "Restart", icon: <Power size={12} />, action: () => desktop.restart(), color: "var(--dash-warning)" },
              { label: "Shutdown", icon: <Power size={12} />, action: () => desktop.shutdown(), color: "var(--dash-danger)" },
            ].map((b) => (
              <button key={b.label} onClick={b.action}
                style={{ padding: "5px 10px", borderRadius: "var(--dash-radius-sm)", border: `1px solid ${b.color}40`, background: `${b.color}12`, color: b.color, cursor: "pointer", fontSize: 11, fontWeight: 500, display: "flex", alignItems: "center", gap: 6 }}>
                {b.icon} {b.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Clipboard */}
      <div className="dash-card" style={{ padding: "14px 18px", marginBottom: 14, display: "flex", alignItems: "center", gap: 12 }}>
        <Clipboard size={16} style={{ color: "var(--dash-info)", flexShrink: 0 }} />
        <span style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)", flexShrink: 0 }}>Clipboard</span>
        <div style={{ flex: 1, fontSize: 12, color: "var(--dash-text-secondary)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap", fontFamily: "JetBrains Mono, monospace", padding: "4px 8px", background: "var(--dash-bg)", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border-subtle)" }}>
          {clipboard ? clipboard.substring(0, 120) : "Empty"}
        </div>
        <button onClick={copyClipboard} style={{ padding: "4px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "none", color: clipboardCopied ? "var(--dash-success)" : "var(--dash-text-muted)", cursor: "pointer", fontSize: 11, display: "flex", alignItems: "center", gap: 4 }}>
          {clipboardCopied ? <ClipboardCheck size={12} /> : <Clipboard size={12} />} {clipboardCopied ? "Copied" : "Copy"}
        </button>
      </div>

      {/* Windows List */}
      <div className="dash-card" style={{ padding: "16px 18px", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)", flex: 1 }}>Windows ({windowList.length})</span>
          <button onClick={refreshWindows} style={{ padding: 4, border: "none", background: "none", color: "var(--dash-text-muted)", cursor: "pointer" }}><RefreshCw size={12} /></button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4, maxHeight: 200, overflowY: "auto" }}>
          {windowList.slice(0, 15).map((w, i) => (
            <div key={i} style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 10px", borderRadius: "var(--dash-radius-sm)", background: "var(--dash-bg-subtle)", border: "1px solid var(--dash-border-subtle)" }}>
              <span style={{ fontSize: 12, color: "var(--dash-text)", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{w.title}</span>
              <button onClick={() => windows.focus(w.title)} style={{ padding: "2px 6px", border: "none", background: "none", color: "var(--dash-accent)", cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}><Focus size={10} /> Focus</button>
              <button onClick={() => windows.minimize(w.title)} style={{ padding: "2px 6px", border: "none", background: "none", color: "var(--dash-text-muted)", cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}><Minimize size={10} /> Min</button>
              <button onClick={() => windows.close(w.title)} style={{ padding: "2px 6px", border: "none", background: "none", color: "var(--dash-danger)", cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}><X size={10} /> Close</button>
            </div>
          ))}
        </div>
      </div>

      {/* File Browser */}
      <div className="dash-card" style={{ padding: "16px 18px" }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <FolderOpen size={16} style={{ color: "var(--dash-warning)" }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>File Browser</span>
          <span style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "JetBrains Mono, monospace", flex: 1, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{currentPath}</span>
          <button onClick={navigateUp} style={{ padding: "3px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 10, display: "flex", alignItems: "center", gap: 3 }}><ArrowUp size={10} /> Up</button>
          <button onClick={() => browsePath(currentPath)} style={{ padding: "3px 8px", borderRadius: "var(--dash-radius-sm)", border: "1px solid var(--dash-border)", background: "var(--dash-surface)", color: "var(--dash-text-secondary)", cursor: "pointer", fontSize: 10 }}><RefreshCw size={10} /></button>
        </div>
        <div style={{ maxHeight: 250, overflowY: "auto" }}>
          {loadingFiles ? (
            <div style={{ textAlign: "center", padding: 20, color: "var(--dash-text-muted)", fontSize: 12 }}>Loading...</div>
          ) : filesList.length === 0 ? (
            <div style={{ textAlign: "center", padding: 20, color: "var(--dash-text-muted)", fontSize: 12 }}>Empty directory</div>
          ) : (
            filesList.map((f, i) => (
              <div key={i} role="button" tabIndex={0} onClick={() => { if (f.type === "directory") browsePath(`${currentPath}/${f.name}`); }} onKeyDown={(e) => { if ((e.key === 'Enter' || e.key === ' ') && f.type === 'directory') { e.preventDefault(); browsePath(`${currentPath}/${f.name}`); } }}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "5px 10px", borderRadius: "var(--dash-radius-sm)", cursor: f.type === "directory" ? "pointer" : "default", background: "transparent", transition: "background var(--dash-transition-fast)" }}
                onMouseEnter={(e) => { e.currentTarget.style.background = "var(--dash-bg-subtle)"; }}
                onMouseLeave={(e) => { e.currentTarget.style.background = "transparent"; }}
              >
                {getFileIcon(f.name, f.type)}
                <span style={{ fontSize: 12, color: "var(--dash-text)", flex: 1 }}>{f.name}</span>
                {f.type !== "directory" && (
                  <span style={{ fontSize: 10, color: "var(--dash-text-muted)", fontFamily: "JetBrains Mono, monospace" }}>
                    {f.size > 1048576 ? `${(f.size / 1048576).toFixed(1)}MB` : f.size > 1024 ? `${(f.size / 1024).toFixed(0)}KB` : `${f.size}B`}
                  </span>
                )}
                {f.type === "directory" && <ChevronRight size={12} style={{ color: "var(--dash-text-muted)" }} />}
              </div>
            ))
          )}
        </div>
      </div>

      {/* Screenshot Overlay */}
      {showScreenshot && screenshot && (
        <div style={{ position: "fixed", inset: 0, background: "rgba(0,0,0,0.85)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 1000, backdropFilter: "blur(8px)" }} onClick={() => setShowScreenshot(false)} onKeyDown={(e) => { if (e.key === 'Escape') setShowScreenshot(false); }} role="dialog" aria-label="Screenshot preview" tabIndex={-1}>
          <div style={{ position: "relative" }}>
            <img src={`data:image/png;base64,${screenshot}`} alt="Screenshot" style={{ maxWidth: "90vw", maxHeight: "85vh", borderRadius: "var(--dash-radius-lg)", border: "1px solid var(--dash-border-accent)", boxShadow: "0 0 60px rgba(77,148,255,0.15)" }} />
            <button onClick={() => setShowScreenshot(false)} style={{ position: "absolute", top: 12, right: 12, width: 32, height: 32, borderRadius: "var(--dash-radius-sm)", background: "rgba(0,0,0,0.6)", border: "1px solid var(--dash-border)", color: "var(--dash-text)", cursor: "pointer", display: "flex", alignItems: "center", justifyContent: "center" }}><X size={16} /></button>
          </div>
        </div>
      )}
    </div>
  );
};
export default DesktopControlPage;
