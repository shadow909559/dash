import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import {
  ShieldCheck,
  Download,
  Trash2,
  FileText,
  Eye,
  AlertTriangle,
  CheckCircle,
  RefreshCw,
  Database,
  Lock,
  ExternalLink,
} from "lucide-react";
import { GlassCard } from "@/components/ultron";

interface DataStore {
  name: string;
  description: string;
  storage: string;
  retention: string;
  exportable: boolean;
  deletable: boolean;
  synced: boolean;
  sent_external: boolean;
}

interface DataInventory {
  data_stores: DataStore[];
  summary: {
    total_stores: number;
    exportable_count: number;
    deletable_count: number;
    external_sharing: string;
  };
}

interface PrivacySectionProps {
  apiUrl: string;
}

export const PrivacySection: React.FC<PrivacySectionProps> = ({ apiUrl }) => {
  const [inventory, setInventory] = useState<DataInventory | null>(null);
  const [loading, setLoading] = useState(true);
  const [exporting, setExporting] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteConfirm, setDeleteConfirm] = useState(false);
  const [deleteResult, setDeleteResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const fetchInventory = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await authFetch(`${apiUrl}/privacy/data-inventory`);
      if (res.ok) {
        const data = await res.json();
        setInventory(data);
      } else {
        setError("Failed to load data inventory");
      }
    } catch {
      setError("Cannot connect to backend");
    }
    setLoading(false);
  }, [apiUrl]);

  useEffect(() => {
    fetchInventory();
  }, [fetchInventory]);

  const handleExport = async () => {
    setExporting(true);
    try {
      const res = await authFetch(`${apiUrl}/privacy/data-export`);
      if (res.ok) {
        const data = await res.json();
        const blob = new Blob([JSON.stringify(data, null, 2)], {
          type: "application/json",
        });
        const url = URL.createObjectURL(blob);
        const a = document.createElement("a");
        a.href = url;
        a.download = `dash-data-export-${new Date().toISOString().split("T")[0]}.json`;
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        URL.revokeObjectURL(url);
      } else {
        setError("Export failed");
      }
    } catch {
      setError("Export failed - cannot connect to backend");
    }
    setExporting(false);
  };

  const handleDelete = async () => {
    if (!deleteConfirm) {
      setDeleteConfirm(true);
      return;
    }
    setDeleting(true);
    setDeleteResult(null);
    try {
      const res = await authFetch(`${apiUrl}/privacy/data-delete?confirm=true`, {
        method: "DELETE",
      });
      if (res.ok) {
        const data = await res.json();
        setDeleteResult(
          `Deleted: ${Object.entries(data.counts || {})
            .map(([k, v]) => `${k} (${v})`)
            .join(", ")}`
        );
        setDeleteConfirm(false);
        fetchInventory();
      } else {
        setError("Delete failed");
      }
    } catch {
      setError("Delete failed - cannot connect to backend");
    }
    setDeleting(false);
  };

  if (loading) {
    return (
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, color: "var(--dash-text)", marginBottom: 4 }}>
          Privacy
        </h2>
        <div style={{ padding: 20, textAlign: "center", color: "var(--dash-text-muted)" }}>
          Loading data inventory...
        </div>
      </div>
    );
  }

  return (
    <div>
      <h2
        style={{
          fontSize: 18,
          fontWeight: 700,
          color: "var(--dash-text)",
          marginBottom: 4,
          display: "flex",
          alignItems: "center",
          gap: 8,
        }}
      >
        <ShieldCheck size={18} style={{ color: "var(--dash-accent)" }} />
        Privacy & Data Management
      </h2>
      <p style={{ fontSize: 12, color: "var(--dash-text-muted)", marginBottom: 20 }}>
        Control your data. Export, review, or delete everything DASH stores about you.
      </p>

      {error && (
        <div
          style={{
            padding: "10px 14px",
            background: "rgba(239, 68, 68, 0.1)",
            border: "1px solid rgba(239, 68, 68, 0.3)",
            borderRadius: "var(--dash-radius-sm)",
            fontSize: 12,
            color: "#ef4444",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <AlertTriangle size={14} />
          {error}
        </div>
      )}

      {deleteResult && (
        <div
          style={{
            padding: "10px 14px",
            background: "rgba(34, 197, 94, 0.1)",
            border: "1px solid rgba(34, 197, 94, 0.3)",
            borderRadius: "var(--dash-radius-sm)",
            fontSize: 12,
            color: "#22c55e",
            marginBottom: 16,
            display: "flex",
            alignItems: "center",
            gap: 8,
          }}
        >
          <CheckCircle size={14} />
          {deleteResult}
        </div>
      )}

      {/* Quick Actions */}
      <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12, marginBottom: 20 }}>
        <GlassCard padding={14}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Download size={14} style={{ color: "var(--dash-accent)" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>
              Export Data
            </span>
          </div>
          <p style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 10, lineHeight: 1.5 }}>
            Download all your data as a JSON file. Includes memories, conversations, goals, and settings.
          </p>
          <button
            onClick={handleExport}
            disabled={exporting}
            className="dash-btn"
            style={{
              width: "100%",
              justifyContent: "center",
              fontSize: 12,
              padding: "6px 12px",
            }}
          >
            {exporting ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : (
              <Download size={12} />
            )}
            {exporting ? "Exporting..." : "Export All Data"}
          </button>
        </GlassCard>

        <GlassCard padding={14}>
          <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 8 }}>
            <Trash2 size={14} style={{ color: "#ef4444" }} />
            <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>
              Delete Data
            </span>
          </div>
          <p style={{ fontSize: 11, color: "var(--dash-text-muted)", marginBottom: 10, lineHeight: 1.5 }}>
            Permanently delete all your data. This action cannot be undone.
          </p>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="dash-btn"
            style={{
              width: "100%",
              justifyContent: "center",
              fontSize: 12,
              padding: "6px 12px",
              background: deleteConfirm ? "rgba(239, 68, 68, 0.15)" : undefined,
              borderColor: deleteConfirm ? "#ef4444" : undefined,
              color: deleteConfirm ? "#ef4444" : undefined,
            }}
          >
            {deleting ? (
              <RefreshCw size={12} className="animate-spin" />
            ) : deleteConfirm ? (
              <AlertTriangle size={12} />
            ) : (
              <Trash2 size={12} />
            )}
            {deleting
              ? "Deleting..."
              : deleteConfirm
              ? "Click again to confirm deletion"
              : "Delete All Data"}
          </button>
        </GlassCard>
      </div>

      {/* Data Inventory */}
      <GlassCard padding={16}>
        <div
          style={{
            display: "flex",
            alignItems: "center",
            gap: 8,
            marginBottom: 14,
          }}
        >
          <Database size={14} style={{ color: "var(--dash-accent)" }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>
            Data Inventory
          </span>
          {inventory?.summary && (
            <span
              style={{
                marginLeft: "auto",
                fontSize: 11,
                color: "var(--dash-text-muted)",
                fontFamily: "'JetBrains Mono', monospace",
              }}
            >
              {inventory.summary.total_stores} stores ·{" "}
              {inventory.summary.exportable_count} exportable ·{" "}
              {inventory.summary.deletable_count} deletable
            </span>
          )}
        </div>

        {inventory?.data_stores && (
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            {inventory.data_stores.map((store) => (
              <div
                key={store.name}
                style={{
                  padding: "10px 14px",
                  background: "var(--dash-bg-subtle)",
                  border: "1px solid var(--dash-border-subtle)",
                  borderRadius: "var(--dash-radius-sm)",
                }}
              >
                <div
                  style={{
                    display: "flex",
                    alignItems: "center",
                    justifyContent: "space-between",
                    marginBottom: 4,
                  }}
                >
                  <span style={{ fontSize: 12, fontWeight: 600, color: "var(--dash-text)" }}>
                    {store.name}
                  </span>
                  <div style={{ display: "flex", gap: 6 }}>
                    {store.exportable && (
                      <span
                        style={{
                          fontSize: 9,
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: "rgba(34, 197, 94, 0.12)",
                          color: "#22c55e",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        EXPORT
                      </span>
                    )}
                    {store.deletable && (
                      <span
                        style={{
                          fontSize: 9,
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: "rgba(239, 68, 68, 0.12)",
                          color: "#ef4444",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        DELETE
                      </span>
                    )}
                    {store.sent_external && (
                      <span
                        style={{
                          fontSize: 9,
                          padding: "2px 6px",
                          borderRadius: 3,
                          background: "rgba(245, 158, 11, 0.12)",
                          color: "#f59e0b",
                          fontFamily: "'JetBrains Mono', monospace",
                        }}
                      >
                        EXTERNAL
                      </span>
                    )}
                  </div>
                </div>
                <p style={{ fontSize: 11, color: "var(--dash-text-muted)", margin: 0, lineHeight: 1.4 }}>
                  {store.description}
                </p>
                <div
                  style={{
                    display: "flex",
                    gap: 12,
                    marginTop: 6,
                    fontSize: 10,
                    color: "var(--dash-text-muted)",
                    fontFamily: "'JetBrains Mono', monospace",
                  }}
                >
                  <span>
                    <Lock size={9} style={{ verticalAlign: "middle", marginRight: 3 }} />
                    {store.storage}
                  </span>
                  <span>Retention: {store.retention}</span>
                </div>
              </div>
            ))}
          </div>
        )}

        {inventory?.summary?.external_sharing && (
          <div
            style={{
              marginTop: 12,
              padding: "8px 12px",
              background: "rgba(245, 158, 11, 0.08)",
              border: "1px solid rgba(245, 158, 11, 0.2)",
              borderRadius: "var(--dash-radius-sm)",
              fontSize: 11,
              color: "#f59e0b",
              display: "flex",
              alignItems: "center",
              gap: 6,
            }}
          >
            <Eye size={12} />
            {inventory.summary.external_sharing}
          </div>
        )}
      </GlassCard>

      {/* Privacy Info */}
      <GlassCard padding={16} style={{ marginTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <FileText size={14} style={{ color: "var(--dash-accent)" }} />
          <span style={{ fontSize: 13, fontWeight: 600, color: "var(--dash-text)" }}>
            Your Privacy Rights
          </span>
        </div>
        <div style={{ fontSize: 12, color: "var(--dash-text-secondary)", lineHeight: 1.6 }}>
          <p style={{ margin: "0 0 8px" }}>
            DASH is designed as a local-first application. Your data stays on your machine
            by default. No data is sent to external services unless you explicitly configure
            a cloud AI provider.
          </p>
          <p style={{ margin: 0 }}>
            You can export all your data at any time, or permanently delete everything.
            Audit log entries are retained for security compliance even after data deletion.
          </p>
        </div>
        <a
          href="https://github.com/shadow909559/dash/blob/main/DASH_REPORT.md"
          target="_blank"
          rel="noopener noreferrer"
          style={{
            display: "inline-flex",
            alignItems: "center",
            gap: 4,
            marginTop: 10,
            fontSize: 12,
            color: "var(--dash-accent)",
          }}
        >
          Read full privacy policy <ExternalLink size={10} />
        </a>
      </GlassCard>
    </div>
  );
};
