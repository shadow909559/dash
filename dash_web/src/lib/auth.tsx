import { createContext, useContext, useState, useCallback, useEffect } from "react";
import { useLocalStorage } from "@/hooks/useLocalStorage";

interface AuthUser {
  email: string;
  username: string;
}

interface AuthLog {
  timestamp: string;
  action: string;
  detail: string;
  ip?: string;
}

interface AuthContextType {
  user: AuthUser | null;
  token: string | null;
  logs: AuthLog[];
  login: (email: string, password: string) => Promise<boolean>;
  logout: () => void;
  isAuthenticated: boolean;
}

const AuthContext = createContext<AuthContextType | null>(null);

const LOG_KEY = "dash_auth_logs";

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [user, setUser] = useLocalStorage<AuthUser | null>("dash_user", null);
  const [token, setToken] = useLocalStorage<string | null>("dash_auth_token", null);
  const [logs, setLogs] = useState<AuthLog[]>(() => {
    try {
      return JSON.parse(localStorage.getItem(LOG_KEY) || "[]");
    } catch {
      return [];
    }
  });

  const addLog = useCallback((action: string, detail: string) => {
    const entry: AuthLog = {
      timestamp: new Date().toISOString(),
      action,
      detail,
    };
    setLogs((prev) => {
      const next = [...prev, entry].slice(-100); // keep last 100
      localStorage.setItem(LOG_KEY, JSON.stringify(next));
      return next;
    });
  }, []);

  const login = useCallback(
    async (email: string, password: string): Promise<boolean> => {
      try {
        const apiUrl = import.meta.env.VITE_DASH_API_URL || "http://127.0.0.1:8000/api/v1";
        const res = await fetch(`${apiUrl}/auth/login`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ email, password }),
        });

        if (res.ok) {
          const data = await res.json();
          const userData: AuthUser = { email, username: email.split("@")[0] };
          setUser(userData);
          setToken(data.access_token);
          addLog("LOGIN_SUCCESS", `User ${email} logged in`);
          return true;
        } else {
          addLog("LOGIN_FAILED", `Failed login attempt for ${email}`);
          return false;
        }
      } catch {
        addLog("LOGIN_ERROR", `Connection error for ${email}`);
        return false;
      }
    },
    [setUser, setToken, addLog]
  );

  const logout = useCallback(() => {
    const email = user?.email || "unknown";
    setUser(null);
    setToken(null);
    addLog("LOGOUT", `User ${email} logged out`);
  }, [user, setUser, setToken, addLog]);

  // Auto-save logs every 30 seconds
  useEffect(() => {
    const interval = setInterval(() => {
      localStorage.setItem(LOG_KEY, JSON.stringify(logs));
    }, 30000);
    return () => clearInterval(interval);
  }, [logs]);

  return (
    <AuthContext.Provider
      value={{
        user,
        token,
        logs,
        login,
        logout,
        isAuthenticated: !!user && !!token,
      }}
    >
      {children}
    </AuthContext.Provider>
  );
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used within AuthProvider");
  return ctx;
}
