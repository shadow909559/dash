import React, { useCallback, useEffect, useRef, useState } from "react";
import { authFetch } from "@/lib/api";
import { RefreshCw, Search, ZoomIn, ZoomOut, Crosshair, X, Loader2 } from "lucide-react";

const API = import.meta.env.VITE_API_URL || "http://127.0.0.1:8000/api/v1";

interface GraphNode {
  id: string;
  name: string;
  type: string;
  mention_count: number;
  properties: Record<string, unknown>;
}
interface GraphEdge {
  source: string;
  target: string;
  relationship: string;
  weight: number;
}

const TYPE_COLORS: Record<string, string> = {
  person: "#f472b6",
  project: "#22c55e",
  technology: "#3b82f6",
  concept: "#a78bfa",
  location: "#f59e0b",
  organization: "#06b6d4",
  date: "#94a3b8",
  file: "#e2e8f0",
  tag: "#f97316",
  unknown: "#64748b",
};

const ALPHA_DECAY = 0.985;
const REPULSION = 2400;
const SPRING = 0.03;
const SPRING_LEN = 100;
const CENTER_PULL = 0.012;

interface SimNode extends GraphNode {
  x: number;
  y: number;
  vx: number;
  vy: number;
  fixed: boolean;
}

export const KnowledgeGraphView: React.FC = () => {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const wrapRef = useRef<HTMLDivElement | null>(null);
  const simRef = useRef<SimNode[]>([]);
  const edgesRef = useRef<GraphEdge[]>([]);
  const viewRef = useRef({ x: 0, y: 0, scale: 1 });
  const alphaRef = useRef(1);
  const dragRef = useRef<{ node: SimNode | null; panning: boolean; lastX: number; lastY: number; moved: boolean }>({
    node: null,
    panning: false,
    lastX: 0,
    lastY: 0,
    moved: false,
  });

  const [loading, setLoading] = useState(true);
  const [rebuilding, setRebuilding] = useState(false);
  const [types, setTypes] = useState<string[]>([]);
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [selected, setSelected] = useState<{ node: GraphNode; neighbors: GraphNode[] } | null>(null);
  const [query, setQuery] = useState("");

  // Mutable mirrors for the render loop (avoid re-render per frame)
  const hiddenRef = useRef<Set<string>>(hidden);
  const queryRef = useRef<string>(query);
  const selectedIdRef = useRef<string | null>(null);
  hiddenRef.current = hidden;
  queryRef.current = query;
  selectedIdRef.current = selected?.node.id ?? null;

  const fetchGraph = useCallback(async () => {
    setLoading(true);
    try {
      const r = await authFetch(`${API}/enhanced/knowledge-graph?max_nodes=250`);
      if (r?.ok) {
        const d = await r.json();
        const nodes: GraphNode[] = d.nodes || [];
        const w = wrapRef.current?.clientWidth || 800;
        const h = wrapRef.current?.clientHeight || 520;
        simRef.current = nodes.map((n, i) => {
          const angle = (i / Math.max(1, nodes.length)) * Math.PI * 2;
          return {
            ...n,
            x: w / 2 + Math.cos(angle) * Math.min(w, h) * 0.35,
            y: h / 2 + Math.sin(angle) * Math.min(w, h) * 0.35,
            vx: 0,
            vy: 0,
            fixed: false,
          };
        });
        edgesRef.current = d.edges || [];
        setTypes([...new Set(nodes.map((n) => n.type))].sort());
        setHidden(new Set());
        alphaRef.current = 1;
      }
    } catch {
      /* backend unreachable — keep whatever is on screen */
    }
    setLoading(false);
  }, []);

  useEffect(() => {
    fetchGraph();
  }, [fetchGraph]);

  const rebuild = async () => {
    setRebuilding(true);
    try {
      await authFetch(`${API}/enhanced/knowledge-graph/rebuild`, { method: "POST" });
      await fetchGraph();
    } catch {
      /* ignore */
    }
    setRebuilding(false);
  };

  const selectNode = useCallback(async (id: string) => {
    const local = simRef.current.find((n) => n.id === id);
    try {
      const r = await authFetch(`${API}/enhanced/knowledge-graph/node/${encodeURIComponent(id)}`);
      if (r?.ok) {
        const d = await r.json();
        if (d.ok === false) {
          setSelected(local ? { node: local, neighbors: [] } : null);
          return;
        }
        setSelected({ node: d.node, neighbors: (d.neighbors?.neighbors || []).filter(Boolean) });
        selectedIdRef.current = id;
        return;
      }
    } catch {
      /* fall back to local data */
    }
    setSelected(local ? { node: local, neighbors: [] } : null);
  }, []);

  // ── Physics + render loop ────────────────────────────────────────
  useEffect(() => {
    let raf = 0;
    const step = () => {
      const canvas = canvasRef.current;
      const ctx = canvas?.getContext("2d");
      if (canvas && ctx) {
        const dpr = window.devicePixelRatio || 1;
        const w = canvas.width / dpr;
        const h = canvas.height / dpr;
        const nodes = simRef.current;
        const edges = edgesRef.current;
        const byId = new Map(nodes.map((n) => [n.id, n]));

        if (alphaRef.current > 0.005) {
          const visible = nodes.filter((n) => !hiddenRef.current.has(n.type));
          // Repulsion (O(n²) is fine for ≤250 nodes)
          for (let i = 0; i < visible.length; i++) {
            for (let j = i + 1; j < visible.length; j++) {
              const a = visible[i];
              const b = visible[j];
              let dx = a.x - b.x;
              let dy = a.y - b.y;
              let d2 = dx * dx + dy * dy;
              if (d2 < 1) {
                dx = Math.random() - 0.5;
                dy = Math.random() - 0.5;
                d2 = 1;
              }
              const d = Math.sqrt(d2);
              const f = REPULSION / d2;
              const fx = (dx / d) * f;
              const fy = (dy / d) * f;
              if (!a.fixed) {
                a.vx += fx;
                a.vy += fy;
              }
              if (!b.fixed) {
                b.vx -= fx;
                b.vy -= fy;
              }
            }
          }
          // Springs along edges
          for (const e of edges) {
            const a = byId.get(e.source);
            const b = byId.get(e.target);
            if (!a || !b || a.fixed || b.fixed) continue;
            if (hiddenRef.current.has(a.type) || hiddenRef.current.has(b.type)) continue;
            const dx = b.x - a.x;
            const dy = b.y - a.y;
            const d = Math.sqrt(dx * dx + dy * dy) || 1;
            const f = (d - SPRING_LEN) * SPRING;
            const fx = (dx / d) * f;
            const fy = (dy / d) * f;
            a.vx += fx;
            a.vy += fy;
            b.vx -= fx;
            b.vy -= fy;
          }
          // Centering + integration + damping
          for (const n of visible) {
            if (n.fixed) continue;
            n.vx += (w / 2 - n.x) * CENTER_PULL;
            n.vy += (h / 2 - n.y) * CENTER_PULL;
            n.vx *= 0.85;
            n.vy *= 0.85;
            n.x += n.vx;
            n.y += n.vy;
          }
          alphaRef.current *= ALPHA_DECAY;
        }

        // Draw
        ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
        ctx.clearRect(0, 0, w, h);
        const view = viewRef.current;
        ctx.save();
        ctx.translate(view.x, view.y);
        ctx.scale(view.scale, view.scale);
        const q = queryRef.current.trim().toLowerCase();
        for (const e of edges) {
          const a = byId.get(e.source);
          const b = byId.get(e.target);
          if (!a || !b) continue;
          if (hiddenRef.current.has(a.type) || hiddenRef.current.has(b.type)) continue;
          const dimmed = q && !a.name.toLowerCase().includes(q) && !b.name.toLowerCase().includes(q);
          ctx.strokeStyle = dimmed ? "rgba(148,163,184,0.08)" : "rgba(148,163,184,0.25)";
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.moveTo(a.x, a.y);
          ctx.lineTo(b.x, b.y);
          ctx.stroke();
        }
        for (const n of simRef.current) {
          if (hiddenRef.current.has(n.type)) continue;
          const color = TYPE_COLORS[n.type] || TYPE_COLORS.unknown;
          const dimmed = q && !n.name.toLowerCase().includes(q);
          const radius = 6 + Math.min(10, Math.sqrt(n.mention_count) * 2.2);
          ctx.globalAlpha = dimmed ? 0.15 : 1;
          // selection halo
          if (n.id === selectedIdRef.current) {
            ctx.beginPath();
            ctx.arc(n.x, n.y, radius + 5, 0, Math.PI * 2);
            ctx.strokeStyle = color;
            ctx.lineWidth = 2;
            ctx.stroke();
          }
          ctx.beginPath();
          ctx.arc(n.x, n.y, radius, 0, Math.PI * 2);
          ctx.fillStyle = color;
          ctx.fill();
          ctx.globalAlpha = dimmed ? 0.2 : 0.9;
          ctx.fillStyle = "#e2e8f0";
          ctx.font = "10px system-ui, sans-serif";
          ctx.textAlign = "center";
          ctx.fillText(n.name, n.x, n.y + radius + 12);
          ctx.globalAlpha = 1;
        }
        ctx.restore();
      }
      raf = requestAnimationFrame(step);
    };
    raf = requestAnimationFrame(step);
    return () => cancelAnimationFrame(raf);
  }, []);

  // ── Canvas sizing ───────────────────────────────────────────────
  useEffect(() => {
    const canvas = canvasRef.current;
    const wrap = wrapRef.current;
    if (!canvas || !wrap) return;
    const resize = () => {
      const dpr = window.devicePixelRatio || 1;
      canvas.width = wrap.clientWidth * dpr;
      canvas.height = wrap.clientHeight * dpr;
      canvas.style.width = `${wrap.clientWidth}px`;
      canvas.style.height = `${wrap.clientHeight}px`;
    };
    resize();
    const ro = new ResizeObserver(resize);
    ro.observe(wrap);
    return () => ro.disconnect();
  }, []);

  // ── Mouse interactions ──────────────────────────────────────────
  const toWorld = (mx: number, my: number) => {
    const view = viewRef.current;
    return { x: (mx - view.x) / view.scale, y: (my - view.y) / view.scale };
  };

  const nodeAt = (mx: number, my: number): SimNode | null => {
    const { x, y } = toWorld(mx, my);
    for (const n of simRef.current) {
      if (hiddenRef.current.has(n.type)) continue;
      const radius = 6 + Math.min(10, Math.sqrt(n.mention_count) * 2.2) + 4;
      const dx = n.x - x;
      const dy = n.y - y;
      if (dx * dx + dy * dy <= radius * radius) return n;
    }
    return null;
  };

  const onMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const node = nodeAt(mx, my);
    dragRef.current = { node, panning: !node, lastX: mx, lastY: my, moved: false };
    if (node) node.fixed = true;
  };

  const onMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const d = dragRef.current;
    if (!d.node && !d.panning) return;
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    if (Math.abs(mx - d.lastX) > 2 || Math.abs(my - d.lastY) > 2) d.moved = true;
    if (d.node) {
      const { x, y } = toWorld(mx, my);
      d.node.x = x;
      d.node.y = y;
      d.node.vx = 0;
      d.node.vy = 0;
      alphaRef.current = Math.max(alphaRef.current, 0.3);
    } else if (d.panning) {
      viewRef.current.x += mx - d.lastX;
      viewRef.current.y += my - d.lastY;
    }
    d.lastX = mx;
    d.lastY = my;
  };

  const onMouseUp = (e: React.MouseEvent<HTMLCanvasElement>) => {
    const d = dragRef.current;
    if (d.node) {
      d.node.fixed = false;
      if (!d.moved) void selectNode(d.node.id);
    } else if (!d.moved) {
      setSelected(null);
      selectedIdRef.current = null;
    }
    dragRef.current = { node: null, panning: false, lastX: 0, lastY: 0, moved: false };
  };

  const onWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const rect = e.currentTarget.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;
    const view = viewRef.current;
    const factor = e.deltaY < 0 ? 1.12 : 1 / 1.12;
    const newScale = Math.min(4, Math.max(0.25, view.scale * factor));
    view.x = mx - ((mx - view.x) / view.scale) * newScale;
    view.y = my - ((my - view.y) / view.scale) * newScale;
    view.scale = newScale;
  };

  const zoomBy = (factor: number) => {
    const view = viewRef.current;
    const canvas = canvasRef.current;
    const mx = (canvas?.width || 800) / (window.devicePixelRatio || 1) / 2;
    const my = (canvas?.height || 520) / (window.devicePixelRatio || 1) / 2;
    const newScale = Math.min(4, Math.max(0.25, view.scale * factor));
    view.x = mx - ((mx - view.x) / view.scale) * newScale;
    view.y = my - ((my - view.y) / view.scale) * newScale;
    view.scale = newScale;
  };

  const resetView = () => {
    viewRef.current = { x: 0, y: 0, scale: 1 };
  };

  const selectByName = (name: string) => {
    const n = simRef.current.find((s) => s.name.toLowerCase().includes(name.toLowerCase()));
    if (n) void selectNode(n.id);
  };

  const toggleType = (t: string) => {
    setHidden((prev) => {
      const next = new Set(prev);
      if (next.has(t)) next.delete(t);
      else next.add(t);
      return next;
    });
    alphaRef.current = Math.max(alphaRef.current, 0.5);
  };

  const chipStyle = (t: string): React.CSSProperties => ({
    display: "inline-flex",
    alignItems: "center",
    gap: 6,
    padding: "3px 10px",
    borderRadius: 999,
    fontSize: 11,
    cursor: "pointer",
    border: `1px solid ${hidden.has(t) ? "rgba(148,163,184,0.25)" : TYPE_COLORS[t] || "#64748b"}`,
    color: hidden.has(t) ? "var(--text-muted, #64748b)" : TYPE_COLORS[t] || "#e2e8f0",
    background: hidden.has(t) ? "transparent" : "rgba(255,255,255,0.04)",
    userSelect: "none",
  });

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 12 }}>
      {/* Toolbar */}
      <div style={{ display: "flex", flexWrap: "wrap", alignItems: "center", gap: 8 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, flex: 1, minWidth: 200, position: "relative" }}>
          <Search size={14} style={{ position: "absolute", left: 10, color: "var(--text-muted, #64748b)", pointerEvents: "none" }} />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && query.trim() && selectByName(query.trim())}
            placeholder="Search entities… (Enter to select)"
            aria-label="Search entities in the knowledge graph"
            style={{
              width: "100%",
              padding: "7px 10px 7px 30px",
              borderRadius: 8,
              border: "1px solid rgba(148,163,184,0.25)",
              background: "var(--bg-secondary, #1a1a2e)",
              color: "var(--text-primary, #e2e8f0)",
              fontSize: 12,
              outline: "none",
            }}
          />
        </div>
        <button
          onClick={rebuild}
          disabled={rebuilding || loading}
          aria-label="Rebuild graph from memories"
          style={{ display: "inline-flex", alignItems: "center", gap: 6, padding: "7px 12px", borderRadius: 8, border: "1px solid rgba(148,163,184,0.25)", background: "rgba(159,122,250,0.12)", color: "#a78bfa", fontSize: 12, cursor: "pointer" }}
        >
          {rebuilding ? <Loader2 size={13} className="spin" /> : <RefreshCw size={13} />}
          Rebuild from memories
        </button>
        <div style={{ display: "inline-flex", gap: 4 }}>
          <button onClick={() => zoomBy(1.25)} aria-label="Zoom in" style={zoomBtn}><ZoomIn size={14} /></button>
          <button onClick={() => zoomBy(0.8)} aria-label="Zoom out" style={zoomBtn}><ZoomOut size={14} /></button>
          <button onClick={resetView} aria-label="Reset view" style={zoomBtn}><Crosshair size={14} /></button>
        </div>
      </div>

      {/* Type filters */}
      <div style={{ display: "flex", flexWrap: "wrap", gap: 6 }}>
        {types.map((t) => (
          <span key={t} role="button" tabIndex={0} style={chipStyle(t)} onClick={() => toggleType(t)}
            onKeyDown={(e) => (e.key === "Enter" || e.key === " ") && toggleType(t)}>
            <span style={{ width: 8, height: 8, borderRadius: "50%", background: TYPE_COLORS[t] || "#64748b", display: "inline-block" }} />
            {t}
          </span>
        ))}
      </div>

      {/* Canvas + detail panel */}
      <div style={{ display: "flex", gap: 12, minHeight: 480 }}>
        <div ref={wrapRef} style={{ flex: 1, position: "relative", borderRadius: 12, border: "1px solid rgba(148,163,184,0.15)", background: "rgba(10,10,20,0.35)", overflow: "hidden" }}>
          {loading && (
            <div style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center", justifyContent: "center", gap: 8, color: "var(--text-muted, #64748b)", fontSize: 13 }}>
              <Loader2 size={16} className="spin" /> Loading graph…
            </div>
          )}
          <canvas
            ref={canvasRef}
            onMouseDown={onMouseDown}
            onMouseMove={onMouseMove}
            onMouseUp={onMouseUp}
            onMouseLeave={onMouseUp}
            onWheel={onWheel}
            style={{ display: "block", cursor: "grab", touchAction: "none" }}
            aria-label="Interactive knowledge graph. Drag nodes to rearrange, scroll to zoom, click a node for details."
            role="img"
          />
        </div>

        {selected && (
          <aside
            style={{ width: 260, flexShrink: 0, borderRadius: 12, border: "1px solid rgba(148,163,184,0.2)", background: "var(--bg-secondary, #141428)", padding: 14, display: "flex", flexDirection: "column", gap: 10, maxHeight: 480, overflowY: "auto" }}
            aria-label="Node details"
          >
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "start" }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 600 }}>{selected.node.name}</div>
                <span style={{ fontSize: 11, color: TYPE_COLORS[selected.node.type] || "#64748b" }}>{selected.node.type}</span>
              </div>
              <button onClick={() => { setSelected(null); selectedIdRef.current = null; }} aria-label="Close details" style={{ background: "none", border: "none", color: "var(--text-muted, #64748b)", cursor: "pointer", padding: 2 }}><X size={14} /></button>
            </div>
            <div style={{ fontSize: 11, color: "var(--text-muted, #64748b)" }}>
              Mentioned {selected.node.mention_count}× · {selected.neighbors.length} connections
            </div>
            {Object.keys(selected.node.properties || {}).length > 0 && (
              <pre style={{ fontSize: 10, color: "var(--text-muted, #64748b)", whiteSpace: "pre-wrap", margin: 0 }}>
                {JSON.stringify(selected.node.properties, null, 2)}
              </pre>
            )}
            <div style={{ fontSize: 11, fontWeight: 600, color: "var(--text-muted, #64748b)", textTransform: "uppercase", letterSpacing: 0.5 }}>Connected to</div>
            {selected.neighbors.length === 0 && <div style={{ fontSize: 12, color: "var(--text-muted, #64748b)" }}>No connections</div>}
            {selected.neighbors.map((n) => (
              <button
                key={n.id}
                onClick={() => void selectNode(n.id)}
                style={{ display: "flex", alignItems: "center", gap: 8, padding: "6px 8px", borderRadius: 8, border: "1px solid rgba(148,163,184,0.15)", background: "rgba(255,255,255,0.03)", color: "var(--text-primary, #e2e8f0)", fontSize: 12, cursor: "pointer", textAlign: "left" }}
              >
                <span style={{ width: 8, height: 8, borderRadius: "50%", flexShrink: 0, background: TYPE_COLORS[n.type] || "#64748b" }} />
                {n.name}
                <span style={{ marginLeft: "auto", fontSize: 10, color: "var(--text-muted, #64748b)" }}>{n.type}</span>
              </button>
            ))}
          </aside>
        )}
      </div>
    </div>
  );
};

const zoomBtn: React.CSSProperties = {
  padding: 7,
  borderRadius: 8,
  border: "1px solid rgba(148,163,184,0.25)",
  background: "rgba(255,255,255,0.03)",
  color: "var(--text-primary, #e2e8f0)",
  cursor: "pointer",
  display: "inline-flex",
  minHeight: 24,
  minWidth: 24,
  alignItems: "center",
  justifyContent: "center",
};
