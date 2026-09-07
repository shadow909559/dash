import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { Eye, EyeOff, Lock, Mail, AlertTriangle } from "lucide-react";
import { useToast } from "@/hooks/useToast";

interface LoginFormData {
  email: string;
  password: string;
}

interface FormErrors {
  email?: string;
  password?: string;
  general?: string;
}

export function LoginPage() {
  const navigate = useNavigate();
  const { addToast } = useToast();
  const [formData, setFormData] = useState<LoginFormData>({
    email: "",
    password: "",
  });
  const [errors, setErrors] = useState<FormErrors>({});
  const [showPassword, setShowPassword] = useState(false);
  const [isLoading, setIsLoading] = useState(false);

  const validate = (): boolean => {
    const newErrors: FormErrors = {};

    if (!formData.email) {
      newErrors.email = "Email is required";
    } else if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(formData.email)) {
      newErrors.email = "Enter a valid email address";
    }

    if (!formData.password) {
      newErrors.password = "Password is required";
    } else if (formData.password.length < 8) {
      newErrors.password = "Password must be at least 8 characters";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!validate()) return;

    setIsLoading(true);
    setErrors({});

    try {
      // Simulated auth - in production this calls the DASH backend
      const response = await fetch(
        `${import.meta.env.VITE_DASH_API_URL || "http://127.0.0.1:8000/api/v1"}/auth/login`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(formData),
        }
      );

      if (response.ok) {
        const data = await response.json();
        localStorage.setItem("dash_auth_token", data.access_token);
        addToast("Login successful", "success");
        navigate("/");
      } else {
        const err = await response.json().catch(() => ({}));
        setErrors({
          general: err.detail || "Invalid email or password",
        });
      }
    } catch {
      setErrors({
        general: "Unable to connect to server. Make sure DASH backend is running.",
      });
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <PageLayout title="Sign in to DASH">
      <section className="section" style={{ display: "flex", justifyContent: "center" }}>
        <div className="container" style={{ maxWidth: 420 }}>
          <div
            className="card"
            style={{ padding: 32 }}
          >
            <div style={{ textAlign: "center", marginBottom: 24 }}>
              <Lock
                size={32}
                style={{ color: "var(--accent)", marginBottom: 12 }}
              />
              <h2 style={{ marginBottom: 4 }}>Welcome back</h2>
              <p style={{ fontSize: 14, color: "var(--text-muted)" }}>
                Sign in to your DASH account
              </p>
            </div>

            {errors.general && (
              <div
                style={{
                  padding: "10px 14px",
                  background: "rgba(239, 68, 68, 0.1)",
                  border: "1px solid rgba(239, 68, 68, 0.3)",
                  borderRadius: "var(--radius-md)",
                  fontSize: 13,
                  color: "var(--danger)",
                  marginBottom: 16,
                  display: "flex",
                  alignItems: "center",
                  gap: 8,
                }}
              >
                <AlertTriangle size={14} />
                {errors.general}
              </div>
            )}

            <form onSubmit={handleSubmit}>
              {/* Email */}
              <div style={{ marginBottom: 16 }}>
                <label
                  htmlFor="email"
                  style={{
                    display: "block",
                    fontSize: 13,
                    fontWeight: 500,
                    marginBottom: 6,
                    color: "var(--text-secondary)",
                  }}
                >
                  Email
                </label>
                <div style={{ position: "relative" }}>
                  <Mail
                    size={14}
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                    }}
                  />
                  <input
                    id="email"
                    type="email"
                    value={formData.email}
                    onChange={(e) =>
                      setFormData({ ...formData, email: e.target.value })
                    }
                    style={{
                      width: "100%",
                      padding: "10px 12px 10px 36px",
                      background: "var(--bg-tertiary)",
                      border: `1px solid ${errors.email ? "var(--danger)" : "var(--border)"}`,
                      borderRadius: "var(--radius-md)",
                      color: "var(--text-primary)",
                      fontSize: 14,
                      fontFamily: "var(--font-sans)",
                    }}
                    placeholder="you@example.com"
                    autoComplete="email"
                  />
                </div>
                {errors.email && (
                  <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>
                    {errors.email}
                  </p>
                )}
              </div>

              {/* Password */}
              <div style={{ marginBottom: 24 }}>
                <label
                  htmlFor="password"
                  style={{
                    display: "block",
                    fontSize: 13,
                    fontWeight: 500,
                    marginBottom: 6,
                    color: "var(--text-secondary)",
                  }}
                >
                  Password
                </label>
                <div style={{ position: "relative" }}>
                  <Lock
                    size={14}
                    style={{
                      position: "absolute",
                      left: 12,
                      top: "50%",
                      transform: "translateY(-50%)",
                      color: "var(--text-muted)",
                    }}
                  />
                  <input
                    id="password"
                    type={showPassword ? "text" : "password"}
                    value={formData.password}
                    onChange={(e) =>
                      setFormData({ ...formData, password: e.target.value })
                    }
                    style={{
                      width: "100%",
                      padding: "10px 40px 10px 36px",
                      background: "var(--bg-tertiary)",
                      border: `1px solid ${errors.password ? "var(--danger)" : "var(--border)"}`,
                      borderRadius: "var(--radius-md)",
                      color: "var(--text-primary)",
                      fontSize: 14,
                      fontFamily: "var(--font-sans)",
                    }}
                    placeholder="Enter your password"
                    autoComplete="current-password"
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    style={{
                      position: "absolute",
                      right: 8,
                      top: "50%",
                      transform: "translateY(-50%)",
                      background: "none",
                      border: "none",
                      color: "var(--text-muted)",
                      cursor: "pointer",
                      padding: 4,
                    }}
                    aria-label={showPassword ? "Hide password" : "Show password"}
                  >
                    {showPassword ? <EyeOff size={14} /> : <Eye size={14} />}
                  </button>
                </div>
                {errors.password && (
                  <p style={{ fontSize: 12, color: "var(--danger)", marginTop: 4 }}>
                    {errors.password}
                  </p>
                )}
              </div>

              <button
                type="submit"
                className="btn btn--primary"
                disabled={isLoading}
                style={{ width: "100%", justifyContent: "center" }}
              >
                {isLoading ? (
                  <span style={{ display: "flex", alignItems: "center", gap: 8 }}>
                    <span className="skeleton" style={{ width: 14, height: 14, borderRadius: "50%" }} />
                    Signing in...
                  </span>
                ) : (
                  "Sign in"
                )}
              </button>
            </form>

            <p
              style={{
                textAlign: "center",
                fontSize: 13,
                color: "var(--text-muted)",
                marginTop: 16,
              }}
            >
              DASH uses device-token authentication.{" "}
              <a href="https://github.com/shadow909559/dash" target="_blank" rel="noopener noreferrer">
                Learn more
              </a>
            </p>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
