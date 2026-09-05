import { Component, ReactNode } from "react";

interface ErrorBoundaryState {
  hasError: boolean;
  error: Error | null;
}

interface ErrorBoundaryProps {
  children: ReactNode;
}

export class ErrorBoundary extends Component<ErrorBoundaryProps, ErrorBoundaryState> {
  constructor(props: ErrorBoundaryProps) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error): ErrorBoundaryState {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error("[ErrorBoundary] Caught error:", error, errorInfo);
  }

  handleReset = () => {
    this.setState({ hasError: false, error: null });
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          style={{
            position: "fixed",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            background: "rgba(5, 6, 8, 0.95)",
            color: "rgba(255, 255, 255, 0.9)",
            zIndex: 9999,
            padding: 40,
          }}
        >
          <div
            style={{
              width: 80,
              height: 80,
              borderRadius: "50%",
              background: "radial-gradient(circle, rgba(63, 169, 245, 0.3), rgba(63, 169, 245, 0.1))",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              marginBottom: 24,
              fontSize: 32,
            }}
          >
            ⚠
          </div>
          <h2 style={{ fontSize: 24, fontWeight: 600, marginBottom: 16 }}>
            DASH Encountered an Error
          </h2>
          <p style={{ fontSize: 14, color: "rgba(255, 255, 255, 0.6)", marginBottom: 8, textAlign: "center" }}>
            {this.state.error?.message || "An unexpected error occurred"}
          </p>
          <p style={{ fontSize: 12, color: "rgba(255, 255, 255, 0.4)", marginBottom: 32, textAlign: "center" }}>
            The interface has been isolated to prevent further issues.
          </p>
          <button
            onClick={this.handleReset}
            style={{
              padding: "12px 32px",
              background: "radial-gradient(circle, rgba(96, 165, 250, 0.3), rgba(96, 165, 250, 0.1))",
              border: "1px solid rgba(96, 165, 250, 0.3)",
              borderRadius: 8,
              color: "#60a5fa",
              fontSize: 14,
              fontWeight: 500,
              cursor: "pointer",
              transition: "all 0.2s ease",
            }}
            onMouseEnter={(e) => (e.currentTarget.style.background = "radial-gradient(circle, rgba(96, 165, 250, 0.4), rgba(96, 165, 250, 0.15))")}
            onMouseLeave={(e) => (e.currentTarget.style.background = "radial-gradient(circle, rgba(96, 165, 250, 0.3), rgba(96, 165, 250, 0.1))")}
          >
            Reload Interface
          </button>
        </div>
      );
    }

    return this.props.children;
  }
}

export default ErrorBoundary;
