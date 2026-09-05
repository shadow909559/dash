import React, { useState, useEffect, useCallback } from "react";
import { authFetch } from "@/lib/api";
import { FolderKanban, Plus, RefreshCw, FolderGit2, ExternalLink } from "lucide-react";
import { PageShell, PageHeader, EmptyState, GlassCard, SectionTitle } from "@/components/ultron";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface Project {
  id: string;
  name: string;
  description: string;
  status: string;
  path?: string;
  created_at: string;
}

export const ProjectsPage: React.FC = () => {
  const [projects, setProjects] = useState<Project[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [newName, setNewName] = useState("");
  const [newDesc, setNewDesc] = useState("");

  const fetchProjects = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/projects`);
      const data = await r.json();
      setProjects(data.projects || data || []);
    } catch {}
    setLoading(false);
  }, []);

  const createProject = async () => {
    if (!newName.trim()) return;
    try {
      await authFetch(`${API}/projects`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: newName, description: newDesc }),
      });
      setNewName("");
      setNewDesc("");
      setShowCreate(false);
      fetchProjects();
    } catch {}
  };

  useEffect(() => {
    fetchProjects();
  }, [fetchProjects]);

  const statusColor = (s: string) => {
    switch (s?.toLowerCase()) {
      case "active":
      case "completed":
        return "var(--dash-success)";
      case "paused":
      case "planning":
        return "var(--dash-warning)";
      case "error":
      case "failed":
        return "var(--dash-danger)";
      default:
        return "var(--dash-accent)";
    }
  };

  return (
    <PageShell glowColor="rgba(77, 148, 255, 0.06)">
      <PageHeader
        icon={<FolderKanban size={22} color="var(--dash-accent)" />}
        iconColor="var(--dash-accent)"
        title="Projects"
        subtitle="Local project environments and workspace repositories"
        badge={
          <span
            className="dash-badge-glow"
            style={{
              background: "var(--dash-accent-glow)",
              color: "var(--dash-accent)",
              border: "1px solid var(--dash-border-accent)",
            }}
          >
            <FolderGit2 size={10} />
            {projects.length} projects
          </span>
        }
        actions={
          <>
            <button
              onClick={() => setShowCreate(!showCreate)}
              className="dash-btn-primary"
            >
              <Plus size={14} /> New
            </button>
            <button onClick={fetchProjects} className="dash-btn-ghost" title="Refresh">
              <RefreshCw size={14} />
            </button>
          </>
        }
      />

      <div className="dash-page-content">
        {/* Create form */}
        {showCreate && (
          <GlassCard glow padding={18}>
            <SectionTitle>Create Project</SectionTitle>
            <div style={{ display: "flex", flexDirection: "column", gap: 10 }}>
              <input
                value={newName}
                onChange={(e) => setNewName(e.target.value)}
                placeholder="Project name"
                className="dash-input-ultron"
                style={{ width: "100%", boxSizing: "border-box" }}
              />
              <input
                value={newDesc}
                onChange={(e) => setNewDesc(e.target.value)}
                placeholder="Description (optional)"
                className="dash-input-ultron"
                style={{ width: "100%", boxSizing: "border-box" }}
              />
              <div style={{ display: "flex", gap: 8, justifyContent: "flex-end" }}>
                <button
                  onClick={() => setShowCreate(false)}
                  className="dash-btn-ghost"
                >
                  Cancel
                </button>
                <button onClick={createProject} className="dash-btn-primary">
                  <Plus size={12} /> Create Project
                </button>
              </div>
            </div>
          </GlassCard>
        )}

        {/* Projects list */}
        {loading ? (
          <div
            style={{
              textAlign: "center",
              padding: 48,
              color: "var(--dash-text-muted)",
            }}
          >
            <RefreshCw
              size={18}
              className="animate-rotate"
              style={{ marginBottom: 10 }}
            />
            <div>Loading projects...</div>
          </div>
        ) : projects.length === 0 ? (
          <EmptyState
            icon={
              <FolderKanban
                size={28}
                style={{ color: "var(--dash-accent)" }}
              />
            }
            title="No projects yet"
            description="Create a project to organize your workspaces and repositories."
            action={
              <button
                onClick={() => setShowCreate(true)}
                className="dash-btn-primary"
              >
                <Plus size={14} /> Create Project
              </button>
            }
          />
        ) : (
          <div className="dash-stagger">
            <SectionTitle count={projects.length}>Projects</SectionTitle>
            {projects.map((p) => (
              <GlassCard key={p.id} padding={0} className="dash-card-glow">
                <div
                  style={{
                    padding: "16px 20px",
                    display: "flex",
                    alignItems: "flex-start",
                    gap: 14,
                  }}
                >
                  <div
                    style={{
                      width: 36,
                      height: 36,
                      borderRadius: "var(--dash-radius-sm)",
                      background: "var(--dash-accent-glow)",
                      border: "1px solid var(--dash-border-accent)",
                      display: "flex",
                      alignItems: "center",
                      justifyContent: "center",
                      flexShrink: 0,
                    }}
                  >
                    <FolderKanban
                      size={16}
                      style={{ color: "var(--dash-accent)" }}
                    />
                  </div>
                  <div style={{ flex: 1, minWidth: 0 }}>
                    <div
                      style={{
                        display: "flex",
                        alignItems: "center",
                        gap: 10,
                        marginBottom: 4,
                      }}
                    >
                      <span
                        style={{
                          fontSize: 14,
                          fontWeight: 600,
                          color: "var(--dash-text)",
                        }}
                      >
                        {p.name}
                      </span>
                      <span
                        className="dash-badge-glow"
                        style={{
                          background: `${statusColor(p.status)}15`,
                          color: statusColor(p.status),
                          border: `1px solid ${statusColor(p.status)}30`,
                        }}
                      >
                        {p.status || "active"}
                      </span>
                    </div>
                    {p.description && (
                      <div
                        style={{
                          fontSize: 12,
                          color: "var(--dash-text-secondary)",
                          lineHeight: 1.5,
                          marginBottom: 4,
                        }}
                      >
                        {p.description}
                      </div>
                    )}
                    {p.path && (
                      <div
                        style={{
                          fontSize: 10,
                          color: "var(--dash-text-muted)",
                          fontFamily: "'JetBrains Mono', monospace",
                          display: "flex",
                          alignItems: "center",
                          gap: 4,
                        }}
                      >
                        <ExternalLink size={10} />
                        {p.path}
                      </div>
                    )}
                  </div>
                </div>
              </GlassCard>
            ))}
          </div>
        )}
      </div>
    </PageShell>
  );
};

export default ProjectsPage;
