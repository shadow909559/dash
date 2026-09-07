import { Link } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { ArrowLeft, Home } from "lucide-react";

export function NotFoundPage() {
  return (
    <PageLayout title="404 — Page not found">
      <section className="section" style={{ textAlign: "center" }}>
        <div className="container">
          <div
            style={{
              fontFamily: "var(--font-mono)",
              fontSize: "clamp(4rem, 10vw, 8rem)",
              fontWeight: 700,
              color: "var(--bg-tertiary)",
              lineHeight: 1,
              marginBottom: 16,
            }}
          >
            404
          </div>
          <h2 style={{ marginBottom: 12 }}>Page not found</h2>
          <p style={{ marginBottom: 32, maxWidth: 400, margin: "0 auto 32px" }}>
            The page you're looking for doesn't exist or has been moved.
          </p>
          <div style={{ display: "flex", gap: 12, justifyContent: "center" }}>
            <Link to="/" className="btn btn--primary">
              <Home size={14} />
              Go home
            </Link>
            <button onClick={() => window.history.back()} className="btn btn--secondary">
              <ArrowLeft size={14} />
              Go back
            </button>
          </div>
        </div>
      </section>
    </PageLayout>
  );
}
