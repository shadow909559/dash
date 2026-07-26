import { useState, FormEvent } from "react";
import { useAuthStore } from "@/stores/authStore";
import AnimatedBackground from "@/components/AnimatedBackground";

import TitleBar from "@/components/TitleBar";

export default function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [username, setUsername] = useState("");
  const { login, register, isLoading, error, clearError } = useAuthStore();

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    clearError();
    try {
      if (isRegister) {
        await register(email, password, username || undefined);
      } else {
        await login(email, password);
      }
    } catch {
      // error is set in store
    }
  }

  return (
    <>
    <TitleBar />
    <div
      style={{
        height: "100vh",
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: "var(--bg-primary)",
        position: "relative",
      }}
    >
      <AnimatedBackground />
      <div
        className="glass-card animate-fade-in"
        style={{
          width: 400,
          padding: "40px 32px",
          position: "relative",
          zIndex: 1,
        }}
      >
        <div style={{ textAlign: "center", marginBottom: 32 }}>
          <div
            style={{
              width: 48,
              height: 48,
              borderRadius: 12,
              background: "linear-gradient(135deg, var(--accent-primary), var(--accent-secondary))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              fontSize: 24,
              fontWeight: 700,
              color: "white",
              margin: "0 auto 16px",
            }}
          >
            D
          </div>
          <h1
            style={{
              fontSize: 22,
              fontWeight: 600,
              color: "var(--text-primary)",
              marginBottom: 4,
            }}
          >
            Welcome to DASH
          </h1>
          <p style={{ fontSize: 14, color: "var(--text-secondary)" }}>
            {isRegister ? "Create your account" : "Sign in to continue"}
          </p>
        </div>

        <form onSubmit={handleSubmit} style={{ display: "flex", flexDirection: "column", gap: 16 }}>
          {isRegister && (
            <div>
              <label
                style={{
                  display: "block",
                  fontSize: 13,
                  fontWeight: 500,
                  color: "var(--text-secondary)",
                  marginBottom: 6,
                }}
              >
                Name
              </label>
              <input
                className="input"
                type="text"
                placeholder="Your username"
                value={username}
                onChange={(e) => setUsername(e.target.value)}
              />
            </div>
          )}

          <div>
            <label
              style={{
                display: "block",
                fontSize: 13,
                fontWeight: 500,
                color: "var(--text-secondary)",
                marginBottom: 6,
              }}
            >
              Email
            </label>
            <input
              className="input"
              type="email"
              placeholder="you@example.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </div>

          <div>
            <label
              style={{
                display: "block",
                fontSize: 13,
                fontWeight: 500,
                color: "var(--text-secondary)",
                marginBottom: 6,
              }}
            >
              Password
            </label>
            <input
              className="input"
              type="password"
              placeholder="••••••••"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </div>

          {error && (
            <div
              style={{
                padding: "8px 12px",
                background: "rgba(225, 112, 85, 0.1)",
                border: "1px solid rgba(225, 112, 85, 0.3)",
                borderRadius: "var(--radius-sm)",
                color: "var(--danger)",
                fontSize: 13,
              }}
            >
              {error}
            </div>
          )}

          <button
            type="submit"
            className="btn btn-primary"
            disabled={isLoading}
            style={{
              width: "100%",
              padding: "10px 16px",
              fontSize: 14,
              fontWeight: 600,
              opacity: isLoading ? 0.7 : 1,
            }}
          >
            {isLoading ? "Loading..." : isRegister ? "Create Account" : "Sign In"}
          </button>
        </form>

        <div style={{ textAlign: "center", marginTop: 20 }}>
          <button
            className="btn-ghost"
            onClick={() => {
              setIsRegister(!isRegister);
              clearError();
            }}
            style={{ fontSize: 13, color: "var(--accent-secondary)" }}
          >
            {isRegister ? "Already have an account? Sign in" : "Don't have an account? Create one"}
          </button>
        </div>
      </div>
    </div>
    </>
  );
}