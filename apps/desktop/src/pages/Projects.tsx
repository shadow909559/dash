import { useEffect, useState, FormEvent } from "react";
import { projects as projectsApi } from "@/lib/api";

interface Project {
  id: string;
  name: string;
  description?: string;
  status: string;
  created_at: string;
}

export default function Projects() {
  const [items, setItems] = useState<Project[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");

  useEffect(() => {
    loadProjects();
  }, []);

  async function loadProjects() {
    setIsLoading(true);
    try {
      const result = await projectsApi.getAll();
      setItems(result);
    } catch {
      // ignore
    } finally {
      setIsLoading(false);
    }
  }

  async function handleCreate(e: FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    try {
      await projectsApi.create({ name: name.trim(), description: description.trim() || undefined });
      setName("");
      setDescription("");
      setShowCreate(false);
      loadProjects();
    } catch {
      // ignore
    }
  }

  return (
    <div>
      <div className="page-header">
        <div>
          <h2 className="page-title">Projects</h2>
          <p className="page-subtitle">Manage your DASH projects</p>
        </div>
        <button className="btn btn-primary" onClick={() => setShowCreate(!showCreate)}>
          + New Project
        </button>
      </div>

      {showCreate && (
        <form
          onSubmit={handleCreate}
          className="glass-card animate-fade-in"
          style={{ padding: 20, marginBottom: 20 }}
        >
          <h3 style={{ fontSize: 15, fontWeight: 600, marginBottom: 16, color: "var(--text-primary)" }}>
            Create Project
          </h3>
          <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
            <input
              className="input"
              type="text"
              placeholder="Project name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <input
              className="input"
              type="text"
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
            <div style={{ display: "flex", gap: 8 }}>
              <button type="submit" className="btn btn-primary">Create</button>
              <button type="button" className="btn" onClick={() => setShowCreate(false)}>Cancel</button>
            </div>
          </div>
        </form>
      )}

      <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
        {isLoading && <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>Loading...</div>}
        {!isLoading && items.length === 0 && (
          <div style={{ textAlign: "center", padding: 40, color: "var(--text-muted)" }}>
            No projects yet
          </div>
        )}
        {!isLoading && items.map((project, i) => (
          <div
            key={project.id}
            className="glass-card animate-fade-in"
            style={{ padding: "16px 20px", animationDelay: `${i * 0.03}s` }}
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
              <div>
                <h3 style={{ fontSize: 15, fontWeight: 600, color: "var(--text-primary)", marginBottom: 4 }}>
                  {project.name}
                </h3>
                {project.description && (
                  <p style={{ fontSize: 13, color: "var(--text-secondary)", marginBottom: 8 }}>
                    {project.description}
                  </p>
                )}
                <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
                  <span className={`status-dot ${project.status === "active" ? "online" : "offline"}`} />
                  <span style={{ fontSize: 12, color: "var(--text-muted)", textTransform: "capitalize" }}>
                    {project.status}
                  </span>
                  <span style={{ fontSize: 11, color: "var(--text-muted)" }}>
                    {new Date(project.created_at).toLocaleDateString()}
                  </span>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}