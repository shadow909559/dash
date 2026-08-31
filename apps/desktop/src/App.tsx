import { useState, useEffect, lazy, Suspense } from "react";
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import BootScreen from "@/components/BootScreen";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { NotificationProvider } from "@/components/NotificationProvider";
import { DASHSidebar } from "@/components/DASHSidebar";
import { DASHHeader } from "@/components/DASHHeader";
import { CommandPalette } from "@/components/CommandPalette";
import { initializeWebSocket } from "@/lib/ws";
import { resetWsClient } from "@/lib/wsClient";
import { resetAnimationController } from "@/lib/animationSystem";
import { startSystemStatsPolling } from "@/stores/aiStore";

// Lazy-loaded pages — each gets its own chunk (Performance: code splitting)
const HomePage = lazy(() => import("@/pages/HomePage"));
const ChatPage = lazy(() => import("@/pages/ChatPage"));
const ObsidianPage = lazy(() => import("@/pages/ObsidianPage"));
const MemoryPage = lazy(() => import("@/pages/MemoryPage"));
const KnowledgePage = lazy(() => import("@/pages/KnowledgePage"));
const ProjectsPage = lazy(() => import("@/pages/ProjectsPage"));
const CodingPage = lazy(() => import("@/pages/CodingPage"));
const ResearchPage = lazy(() => import("@/pages/ResearchPage"));
const BrowserPage = lazy(() => import("@/pages/BrowserPage"));
const DesktopControlPage = lazy(() => import("@/pages/DesktopControlPage"));
const PhonePage = lazy(() => import("@/pages/PhonePage"));
const AutomationPage = lazy(() => import("@/pages/AutomationPage"));
const PlannerPage = lazy(() => import("@/pages/PlannerPage"));
const AgentsPage = lazy(() => import("@/pages/AgentsPage"));
const NotificationsPage = lazy(() => import("@/pages/NotificationsPage"));
const ApprovalsPage = lazy(() => import("@/pages/ApprovalsPage"));
const PluginsPage = lazy(() => import("@/pages/PluginsPage"));
const AnalyticsPage = lazy(() => import("@/pages/AnalyticsPage"));
const SettingsPage = lazy(() => import("@/pages/SettingsPage"));
const SystemMonitorPage = lazy(() => import("@/pages/SystemMonitorPage"));
const VoicePage = lazy(() => import("@/pages/VoicePage"));

// Handle Electron IPC for audio stop (exposed via preload onAudioStopAll)
const onAudioStopAll = window.electronAPI?.onAudioStopAll ?? null;

/**
 * Lightweight loading skeleton shown while route chunks load.
 * Matches the crimson theme — no layout shift, pure CSS animation.
 */
function PageSkeleton() {
  return (
    <div
      style={{
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        height: "100%",
        width: "100%",
      }}
      role="status"
      aria-label="Loading page"
    >
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12 }}>
        {/* JARVIS-style spinning ring loader */}
        <div
          style={{
            width: 44,
            height: 44,
            borderRadius: "50%",
            border: "2.5px solid transparent",
            borderTop: "2.5px solid #3fa9f5",
            borderRight: "2.5px solid rgba(63,169,245,0.3)",
            animation: "bd-ring-spin 2s linear infinite",
            boxShadow: "0 0 15px rgba(63,169,245,0.2)",
          }}
        />
        <span
          style={{
            fontSize: 11,
            color: "var(--dash-text-muted)",
            fontFamily: "'Orbitron', 'JetBrains Mono', monospace",
            letterSpacing: "0.15em",
            textTransform: "uppercase",
          }}
        >
          LOADING
        </span>
      </div>
    </div>
  );
}

export function App() {
  const [booting, setBooting] = useState(true);
  const [sidebarExpanded, setSidebarExpanded] = useState(true);

  useEffect(() => {
    // Initialize background communication
    initializeWebSocket();
    const statsInterval = startSystemStatsPolling(5000);

    // Audio stop handler for clean window close/suspend
    const handleStopAllAudio = () => {
      const allAudio = document.querySelectorAll("audio");
      allAudio.forEach((audio) => {
        audio.pause();
        audio.currentTime = 0;
      });

      if ("speechSynthesis" in window) {
        window.speechSynthesis.cancel();
      }

      if ("mediaRecorder" in window) {
        // @ts-ignore
        if (window.mediaRecorder && window.mediaRecorder.isRecording()) {
          // @ts-ignore
          window.mediaRecorder.stop();
        }
      }
    };

    const removeAudioListener = onAudioStopAll?.(() => handleStopAllAudio());

    return () => {
      if (statsInterval) clearInterval(statsInterval);
      if (removeAudioListener) removeAudioListener();
      resetWsClient();
      resetAnimationController();
    };
  }, []);

  return (
    <ErrorBoundary>
      {booting && <BootScreen onComplete={() => setBooting(false)} duration={4000} />}
      <NotificationProvider>
        <Router>
          {/* Accessibility: skip link for keyboard users */}
          <a href="#main-content" className="skip-link">
            Skip to main content
          </a>
          {/* Command palette: Ctrl+K / Cmd+K */}
          <CommandPalette />
          {/* CSS Grid shell: sidebar (auto) + content area (1fr) */}
          <div
            style={{
              width: "100vw",
              height: "100vh",
              display: "grid",
              gridTemplateColumns: sidebarExpanded ? "240px 1fr" : "64px 1fr",
              backgroundColor: "var(--dash-bg)",
              color: "var(--dash-text)",
              overflow: "hidden",
              transition: "grid-template-columns var(--dash-transition-base)",
            }}
          >
            {/* Left: Responsive DASH Sidebar */}
            <DASHSidebar
              isExpanded={sidebarExpanded}
              onToggle={() => setSidebarExpanded((prev) => !prev)}
            />

            {/* Right: Primary Workspace Area */}
            <div
              style={{
                display: "grid",
                gridTemplateRows: "48px 1fr",
                minWidth: 0,
                height: "100%",
                overflow: "hidden",
                backgroundColor: "var(--dash-bg)",
              }}
            >
              {/* Top Navigation & Status Header */}
              <DASHHeader sidebarExpanded={sidebarExpanded} />

              {/* Main Content Viewport — JARVIS grid background */}
              <main
                id="main-content"
                aria-label="Main content"
                className="dash-jarvis-page"
                style={{
                  minWidth: 0,
                  minHeight: 0,
                  height: "100%",
                  overflow: "hidden",
                }}
              >
                <Routes>
                  <Route path="/" element={<Suspense fallback={<PageSkeleton />}><HomePage /></Suspense>} />
                  <Route path="/chat" element={<Suspense fallback={<PageSkeleton />}><ChatPage /></Suspense>} />
                  <Route path="/voice" element={<Suspense fallback={<PageSkeleton />}><VoicePage /></Suspense>} />
                  <Route path="/memory" element={<Suspense fallback={<PageSkeleton />}><MemoryPage /></Suspense>} />
                  <Route path="/knowledge" element={<Suspense fallback={<PageSkeleton />}><KnowledgePage /></Suspense>} />
                  <Route path="/obsidian" element={<Suspense fallback={<PageSkeleton />}><ObsidianPage /></Suspense>} />
                  <Route path="/projects" element={<Suspense fallback={<PageSkeleton />}><ProjectsPage /></Suspense>} />
                  <Route path="/coding" element={<Suspense fallback={<PageSkeleton />}><CodingPage /></Suspense>} />
                  <Route path="/research" element={<Suspense fallback={<PageSkeleton />}><ResearchPage /></Suspense>} />
                  <Route path="/browser" element={<Suspense fallback={<PageSkeleton />}><BrowserPage /></Suspense>} />
                  <Route path="/desktop" element={<Suspense fallback={<PageSkeleton />}><DesktopControlPage /></Suspense>} />
                  <Route path="/phone" element={<Suspense fallback={<PageSkeleton />}><PhonePage /></Suspense>} />
                  <Route path="/automation" element={<Suspense fallback={<PageSkeleton />}><AutomationPage /></Suspense>} />
                  <Route path="/planner" element={<Suspense fallback={<PageSkeleton />}><PlannerPage /></Suspense>} />
                  <Route path="/agents" element={<Suspense fallback={<PageSkeleton />}><AgentsPage /></Suspense>} />
                  <Route path="/notifications" element={<Suspense fallback={<PageSkeleton />}><NotificationsPage /></Suspense>} />
                  <Route path="/approvals" element={<Suspense fallback={<PageSkeleton />}><ApprovalsPage /></Suspense>} />
                  <Route path="/plugins" element={<Suspense fallback={<PageSkeleton />}><PluginsPage /></Suspense>} />
                  <Route path="/analytics" element={<Suspense fallback={<PageSkeleton />}><AnalyticsPage /></Suspense>} />
                  <Route path="/system-monitor" element={<Suspense fallback={<PageSkeleton />}><SystemMonitorPage /></Suspense>} />
                  <Route path="/settings" element={<Suspense fallback={<PageSkeleton />}><SettingsPage /></Suspense>} />
                  <Route path="*" element={<Suspense fallback={<PageSkeleton />}><HomePage /></Suspense>} />
                </Routes>
              </main>
            </div>
          {/* Screen reader announcements */}
          <div id="sr-announcements" aria-live="polite" aria-atomic="true" className="visually-hidden" />
        </div>
        </Router>
      </NotificationProvider>
    </ErrorBoundary>
  );
}

export default App;
