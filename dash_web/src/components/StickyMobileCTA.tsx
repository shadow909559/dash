import { Link } from "react-router-dom";
import { Download } from "lucide-react";
import { useScrollPosition } from "@/hooks/useScrollPosition";

export function StickyMobileCTA() {
  const { scrollY } = useScrollPosition();
  const isVisible = scrollY > 300;

  return (
    <div
      className="sticky-mobile-cta"
      style={{
        position: "fixed",
        bottom: 0,
        left: 0,
        right: 0,
        zIndex: 98,
        padding: "12px 16px",
        background: "rgba(10, 10, 15, 0.95)",
        backdropFilter: "blur(12px)",
        borderTop: "1px solid var(--border)",
        transform: isVisible ? "translateY(0)" : "translateY(100%)",
        transition: "transform var(--transition-base)",
        display: "none",
      }}
    >
      <Link
        to="/download"
        className="btn btn--primary"
        style={{ width: "100%", justifyContent: "center" }}
      >
        <Download size={14} />
        Download DASH
      </Link>
      <style>{`
        @media (max-width: 768px) {
          .sticky-mobile-cta { display: block !important; }
        }
      `}</style>
    </div>
  );
}
