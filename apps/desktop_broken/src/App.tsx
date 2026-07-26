import { useEffect } from "react";
import { Routes, Route, Navigate } from "react-router-dom";
import { useAuthStore } from "@/stores/authStore";
import Sidebar from "@/components/Sidebar";
import Header from "@/components/Header";
import Dashboard from "@/pages/Dashboard";
import Chat from "@/pages/Chat";
import Memory from "@/pages/Memory";
import Projects from "@/pages/Projects";
import Automation from "@/pages/Automation";
import Settings from "@/pages/Settings";
import Login from "@/pages/Login";
import AnimatedBackground from "@/components/AnimatedBackground";

function ProtectedLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="app-layout">
      <AnimatedBackground />
      <Sidebar />
      <div className="main-content">
        <Header />
        <div className="page-content">{children}</div>
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