import { useEffect, lazy, Suspense } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import Login from "@/pages/Login";
import AnimatedBackground from "@/components/AnimatedBackground";

// Lazy load all heavy pages to reduce initial bundle size and improve startup time
const Dashboard = lazy(() => import("@/pages/Dashboard"));
const Chat = lazy(() => import("@/pages/Chat"));
const Memory = lazy(() => import("@/pages/Memory"));
const Projects = lazy(() => import("@/pages/Projects"));
const Automation = lazy(() => import("@/pages/Automation"));
const Settings = lazy(() => import("@/pages/Settings"));

// Loading fallback for lazy loaded pages - lightweight to avoid impact
const PageLoader = () => (
  <div
    style={{
      height: "100%",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
    }}
  >
    <div
      style={{
        width: 30,
        height: 30,
        borderRadius: "50%",
        border: "3px solid var(--border-glass)",
        borderTopColor: "var(--accent-primary)",
        animation: "spin 0.8s linear infinite",
      }}
    />
  </div>
);

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <AnimatedBackground />
      <Sidebar />
      <div className="main-content">
        <Header />
        <div className="page-content">
          <Suspense fallback={<PageLoader />}>{children}</Suspense>
        </div>
      </div>
    </div>
  );
}

function App() {
  const { isAuthenticated, isLoading, checkAuth } = useAuthStore();

  useEffect(() => {
    checkAuth();
  }, [checkAuth]);

  if (isLoading) {
    return (
      <div
        style={{
          height: "100vh",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          background: "var(--bg-primary)",
        }}
      >
        <div className="glass-card" style={{ padding: "32px 48px", textAlign: "center" }}>
          <div
            style={{
              width: 40,
              height: 40,
              borderRadius: "50%",
              border: "3px solid var(--border-glass)",
              borderTopColor: "var(--accent-primary)",
              animation: "spin 0.8s linear infinite",
              margin: "0 auto 16px",
            }}
          />
          <p style={{ color: "var(--text-secondary)", fontSize: 14 }}>Loading DASH...</p>
        </div>
        <style>{`@keyframes spin { to { transform: rotate(360deg); } }`}</style>
      </div>
    );
  }

  if (!isAuthenticated) {
    return (
      <Routes>
        <Route path="*" element={<Login />} />
      </Routes>
    );
  }

  return (
    <Routes>
      <Route
        path="/"
        element={
          <ProtectedLayout>
            <Dashboard />
          </ProtectedLayout>
        }
      />
      <Route
        path="/chat"
        element={
          <ProtectedLayout>
            <Chat />
          </ProtectedLayout>
        }
      />
      <Route
        path="/chat/:id"
        element={
          <ProtectedLayout>
            <Chat />
          </ProtectedLayout>
        }
      />
      <Route
        path="/memory"
        element={
          <ProtectedLayout>
            <Memory />
          </ProtectedLayout>
        }
      />
      <Route
        path="/projects"
        element={
          <ProtectedLayout>
            <Projects />
          </ProtectedLayout>
        }
      />
      <Route
        path="/automation"
        element={
          <ProtectedLayout>
            <Automation />
          </ProtectedLayout>
        }
      />
      <Route
        path="/settings"
        element={
          <ProtectedLayout>
            <Settings />
          </ProtectedLayout>
        }
      />
      <Route path="*" element={<Navigate to="/" replace />} />
    </Routes>
  );
}

export default App;