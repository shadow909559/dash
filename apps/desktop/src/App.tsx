import { useState, useEffect, lazy, Suspense } from "react";
import { HashRouter as Router, Routes, Route } from "react-router-dom";
import BootScreen from "@/components/BootScreen";
import { ErrorBoundary } from "@/components/ErrorBoundary";
import { NotificationProvider } from "@/components/NotificationProvider";
import { DASHSidebar } from "@/components/DASHSidebar";
import { TitleBar } from "@/components/TitleBar";
import { CommandPalette } from "@/components/CommandPalette";
import { initializeWebSocket } from "@/lib/ws";
import { resetWsClient } from "@/lib/wsClient";
import { resetAnimationController } from "@/lib/animationSystem";
import { startSystemStatsPolling } from "@/stores/aiStore";
import { startBadgePolling } from "@/stores/badgeStore";

// Lazy-loaded pages — each gets its own chunk (Performance: code splitting)
const CommandCenterPage = lazy(() => import("@/pages/CommandCenterPage"));
const HomePage = lazy(() => import("@/pages/HomePage"));
const ChatPage = lazy(() => import("@/pages/ChatPage"));
const ObsidianPage = lazy(() => import("@/pages/ObsidianPage"));
const MemoryPage = lazy(() => import("@/pages/MemoryPage"));
const KnowledgePage = lazy(() => import("@/pages/KnowledgePage"));
const ProjectsPage = lazy(() => import("@/pages/ProjectsPage"));
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
const WorkflowBuilderPage = lazy(() => import("@/pages/WorkflowBuilderPage"));
const TokenUsagePage = lazy(() => import("@/pages/TokenUsagePage"));
const SecurityHardeningPage = lazy(() => import("@/pages/SecurityHardeningPage"));
const EmailPage = lazy(() => import("@/pages/EmailPage"));
const CalendarPage = lazy(() => import("@/pages/CalendarPage"));
const VoiceCommandsPage = lazy(() => import("@/pages/VoiceCommandsPage"));
const CollaborationPage = lazy(() => import("@/pages/CollaborationPage"));
const PromptStudioPage = lazy(() => import("@/pages/PromptStudioPage"));
const InfrastructurePage = lazy(() => import("@/pages/InfrastructurePage"));
const CompliancePage = lazy(() => import("@/pages/CompliancePage"));
const FeatureFlagsPage = lazy(() => import("@/pages/FeatureFlagsPage"));
const DataManagementPage = lazy(() => import("@/pages/DataManagementPage"));
const PasswordManagerPage = lazy(() => import("@/pages/PasswordManagerPage"));
const CodeEditorPage = lazy(() => import("@/pages/CodeEditorPage"));
const TerminalPage = lazy(() => import("@/pages/TerminalPage"));
const ClipboardHistoryPage = lazy(() => import("@/pages/ClipboardHistoryPage"));
const FileBrowserPage = lazy(() => import("@/pages/FileBrowserPage"));
const BookmarkManagerPage = lazy(() => import("@/pages/BookmarkManagerPage"));
const ReadingListPage = lazy(() => import("@/pages/ReadingListPage"));
const MeetingNotesPage = lazy(() => import("@/pages/MeetingNotesPage"));
const ActionItemsPage = lazy(() => import("@/pages/ActionItemsPage"));
const TimeTrackingPage = lazy(() => import("@/pages/TimeTrackingPage"));
const SprintBoardPage = lazy(() => import("@/pages/SprintBoardPage"));
const ContactManagerPage = lazy(() => import("@/pages/ContactManagerPage"));
const ReminderSystemPage = lazy(() => import("@/pages/ReminderSystemPage"));
const ScreenshotCapturePage = lazy(() => import("@/pages/ScreenshotCapturePage"));
const SessionReplayPage = lazy(() => import("@/pages/SessionReplayPage"));
const BackupRestorePage = lazy(() => import("@/pages/BackupRestorePage"));
const UpdateCheckerPage = lazy(() => import("@/pages/UpdateCheckerPage"));
const PerformanceMonitorPage = lazy(() => import("@/pages/PerformanceMonitorPage"));
const DebugConsolePage = lazy(() => import("@/pages/DebugConsolePage"));

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
    const badgeInterval = startBadgePolling(60000);

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
      if (badgeInterval) clearInterval(badgeInterval);
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
          {/* Title bar for frameless window */}
          <TitleBar />
          {/* Command palette: Ctrl+K / Cmd+K */}
          <CommandPalette />
          {/* CSS Grid shell: sidebar (auto) + content area (1fr) */}
          <div
            style={{
              width: "100%",
              flex: 1,
              minHeight: 0,
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

            {/* Right: Primary Workspace Area — no toolbar/header */}
            <div
              style={{
                display: "flex",
                flexDirection: "column",
                minWidth: 0,
                height: "100%",
                overflow: "hidden",
                backgroundColor: "var(--dash-bg)",
              }}
            >
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
                  <Route path="/" element={<Suspense fallback={<PageSkeleton />}><CommandCenterPage /></Suspense>} />
                  <Route path="/orb" element={<Suspense fallback={<PageSkeleton />}><HomePage /></Suspense>} />
                  <Route path="/chat" element={<Suspense fallback={<PageSkeleton />}><ChatPage /></Suspense>} />
                  <Route path="/voice" element={<Suspense fallback={<PageSkeleton />}><VoicePage /></Suspense>} />
                  <Route path="/memory" element={<Suspense fallback={<PageSkeleton />}><MemoryPage /></Suspense>} />
                  <Route path="/knowledge" element={<Suspense fallback={<PageSkeleton />}><KnowledgePage /></Suspense>} />
                  <Route path="/obsidian" element={<Suspense fallback={<PageSkeleton />}><ObsidianPage /></Suspense>} />
                  <Route path="/projects" element={<Suspense fallback={<PageSkeleton />}><ProjectsPage /></Suspense>} />
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
                  <Route path="/workflows" element={<Suspense fallback={<PageSkeleton />}><WorkflowBuilderPage /></Suspense>} />
                  <Route path="/token-usage" element={<Suspense fallback={<PageSkeleton />}><TokenUsagePage /></Suspense>} />
                  <Route path="/security-hardening" element={<Suspense fallback={<PageSkeleton />}><SecurityHardeningPage /></Suspense>} />
                  <Route path="/email" element={<Suspense fallback={<PageSkeleton />}><EmailPage /></Suspense>} />
                  <Route path="/calendar" element={<Suspense fallback={<PageSkeleton />}><CalendarPage /></Suspense>} />
                  <Route path="/voice-commands" element={<Suspense fallback={<PageSkeleton />}><VoiceCommandsPage /></Suspense>} />
                  <Route path="/collaboration" element={<Suspense fallback={<PageSkeleton />}><CollaborationPage /></Suspense>} />
                  <Route path="/prompt-studio" element={<Suspense fallback={<PageSkeleton />}><PromptStudioPage /></Suspense>} />
                  <Route path="/infrastructure" element={<Suspense fallback={<PageSkeleton />}><InfrastructurePage /></Suspense>} />
                  <Route path="/compliance" element={<Suspense fallback={<PageSkeleton />}><CompliancePage /></Suspense>} />
                  <Route path="/feature-flags" element={<Suspense fallback={<PageSkeleton />}><FeatureFlagsPage /></Suspense>} />
                  <Route path="/data-management" element={<Suspense fallback={<PageSkeleton />}><DataManagementPage /></Suspense>} />
                  <Route path="/password-manager" element={<Suspense fallback={<PageSkeleton />}><PasswordManagerPage /></Suspense>} />
                  <Route path="/code-editor" element={<Suspense fallback={<PageSkeleton />}><CodeEditorPage /></Suspense>} />
                  <Route path="/terminal" element={<Suspense fallback={<PageSkeleton />}><TerminalPage /></Suspense>} />
                  <Route path="/clipboard" element={<Suspense fallback={<PageSkeleton />}><ClipboardHistoryPage /></Suspense>} />
                  <Route path="/files" element={<Suspense fallback={<PageSkeleton />}><FileBrowserPage /></Suspense>} />
                  <Route path="/bookmarks" element={<Suspense fallback={<PageSkeleton />}><BookmarkManagerPage /></Suspense>} />
                  <Route path="/reading-list" element={<Suspense fallback={<PageSkeleton />}><ReadingListPage /></Suspense>} />
                  <Route path="/meetings" element={<Suspense fallback={<PageSkeleton />}><MeetingNotesPage /></Suspense>} />
                  <Route path="/action-items" element={<Suspense fallback={<PageSkeleton />}><ActionItemsPage /></Suspense>} />
                  <Route path="/time-tracking" element={<Suspense fallback={<PageSkeleton />}><TimeTrackingPage /></Suspense>} />
                  <Route path="/sprint-board" element={<Suspense fallback={<PageSkeleton />}><SprintBoardPage /></Suspense>} />
                  <Route path="/contacts" element={<Suspense fallback={<PageSkeleton />}><ContactManagerPage /></Suspense>} />
                  <Route path="/reminders" element={<Suspense fallback={<PageSkeleton />}><ReminderSystemPage /></Suspense>} />
                  <Route path="/screenshots" element={<Suspense fallback={<PageSkeleton />}><ScreenshotCapturePage /></Suspense>} />
                  <Route path="/session-replay" element={<Suspense fallback={<PageSkeleton />}><SessionReplayPage /></Suspense>} />
                  <Route path="/backup-restore" element={<Suspense fallback={<PageSkeleton />}><BackupRestorePage /></Suspense>} />
                  <Route path="/updates" element={<Suspense fallback={<PageSkeleton />}><UpdateCheckerPage /></Suspense>} />
                  <Route path="/perf-monitor" element={<Suspense fallback={<PageSkeleton />}><PerformanceMonitorPage /></Suspense>} />
                  <Route path="/debug-console" element={<Suspense fallback={<PageSkeleton />}><DebugConsolePage /></Suspense>} />
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
