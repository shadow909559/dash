import { Link } from "react-router-dom";
import { PageLayout } from "@/components/PageLayout";
import { CheckCircle, ArrowRight } from "lucide-react";

export function ThankYouPage() {
  return (
    <PageLayout title="Thank you">
      <section className="section" style={{ textAlign: "center" }}>
        <div className="container" style={{ maxWidth: 500 }}>
          <CheckCircle
            size={48}
            style={{ color: "var(--accent)", marginBottom: 20 }}
          />
          <h2 style={{ marginBottom: 12 }}>Message received</h2>
          <p style={{ marginBottom: 32 }}>
            Thank you for reaching out. We'll get back to you as soon as
            possible.
          </p>
          <Link to="/" className="btn btn--primary">
            Back to home
            <ArrowRight size={14} />
          </Link>
        </div>
      </section>
    </PageLayout>
  );
}
