import React, { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { GitBranch, Play, Clock, Zap, Trash2, X } from "lucide-react";
import type { WorkflowEdge, WorkflowNode } from "@/lib/api";

// ── Constants ───────────────────────────────────────────────────────────────

export const NODE_W = 172;
export const NODE_H = 64;
const PORT_R = 7;
const GRID = 20;

export const NODE_META: Record<
  WorkflowNode["type"],
  { color: string; label: string; Icon: typeof Zap }
> = {
  trigger: { color: "#22c55e", label: "Trigger", Icon: Zap },
  action: { color: "#3b82f6", label: "Action", Icon: Play },
  condition: { color: "#f59e0b", label: "If / Else", Icon: GitBranch },
  delay: { color: "#8b5cf6", label: "Delay", Icon: Clock },
};

export const PORT_IN = { x: 0, y: NODE_H / 2 };
export const PORT_OUT = { x: NODE_W, y: NODE_H / 2 };
export const PORT_TRUE = { x: NODE_W / 2, y: 0 };
export const PORT_FALSE = { x: NODE_W / 2, y: NODE_H };

interface Port {
  nodeId: string;
  kind: "in" | "out" | "true" | "false";
  x: number;
  y: number;
}

// ── Helpers ─────────────────────────────────────────────────────────────────

function edgePath(x1: number, y1: number, x2: number, y2: number): string {
  const dx = Math.max(40, Math.abs(x2 - x1) * 0.5);
  return `M ${x1} ${y1} C ${x1 + dx} ${y1}, ${x2 - dx} ${y2}, ${x2} ${y2}`;
}

function snap(v: number): number {
  return Math.round(v / GRID) * GRID;
}

function newId(prefix: string): string {
  return `${prefix}${Date.now().toString(36)}${Math.random().toString(36).slice(2, 6)}`;
}

// ── Props ───────────────────────────────────────────────────────────────────

export interface WorkflowCanvasProps {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  onChange: (nodes: WorkflowNode[], edges: WorkflowEdge[]) => void;
  selectedNodeId: string | null;
  onSelectNode: (id: string | null) => void;
  /** false = read-only preview (templates): no drag/wire/drop/delete. */
  editable?: boolean;
}

// ── Component ───────────────────────────────────────────────────────────────

export const WorkflowCanvas: React.FC<WorkflowCanvasProps> = ({
  nodes,
  edges,
  onChange,
  selectedNodeId,
  onSelectNode,
  editable = true,
}) => {
  const canvasRef = useRef<HTMLDivElement>(null);
  const [pan, setPan] = useState({ x: 24, y: 16 });
  const [drag, setDrag] = useState<{
    nodeId: string;
    offX: number;
    offY: number;
  } | null>(null);
  const [panning, setPanning] = useState<{ sx: number; sy: number; px: number; py: number } | null>(null);
  const [connect, setConnect] = useState<Port | null>(null);
  const [ghost, setGhost] = useState<{ x: number; y: number } | null>(null);

  const nodeById = useMemo(() => {
    const m = new Map<string, WorkflowNode>();
    for (const n of nodes) m.set(n.id, n);
    return m;
  }, [nodes]);

  // World-space port coordinates for every node/edge endpoint
  const ports = useMemo(() => {
    const map = new Map<string, Port>();
    for (const n of nodes) {
      map.set(`${n.id}:in`, { nodeId: n.id, kind: "in", x: n.x + PORT_IN.x, y: n.y + PORT_IN.y });
      map.set(`${n.id}:out`, { nodeId: n.id, kind: "out", x: n.x + PORT_OUT.x, y: n.y + PORT_OUT.y });
      map.set(`${n.id}:true`, { nodeId: n.id, kind: "true", x: n.x + PORT_TRUE.x, y: n.y + PORT_TRUE.y });
      map.set(`${n.id}:false`, { nodeId: n.id, kind: "false", x: n.x + PORT_FALSE.x, y: n.y + PORT_FALSE.y });
    }
    return map;
  }, [nodes]);

  const toWorld = useCallback(
    (clientX: number, clientY: number) => {
      const rect = canvasRef.current?.getBoundingClientRect();
      if (!rect) return { x: 0, y: 0 };
      return { x: clientX - rect.left - pan.x, y: clientY - rect.top - pan.y };
    },
    [pan]
  );

  // ── Node dragging ────────────────────────────────────────────────────────

  const startNodeDrag = (e: React.PointerEvent, node: WorkflowNode) => {
    if (e.button !== 0) return;
    e.stopPropagation();
    if (!editable) {
      // Read-only preview: selection allowed, movement is not.
      onSelectNode(node.id);
      return;
    }
    try {
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    } catch {
      // Pointer may already be released — capture is only a hit-test
      // nicety; canvas-level pointermove still drives the drag.
    }
    const w = toWorld(e.clientX, e.clientY);
    onSelectNode(node.id);
    setDrag({ nodeId: node.id, offX: w.x - node.x, offY: w.y - node.y });
  };

  const onPointerMove = (e: React.PointerEvent) => {
    if (drag) {
      const w = toWorld(e.clientX, e.clientY);
      const nx = snap(w.x - drag.offX);
      const ny = snap(w.y - drag.offY);
      onChange(
        nodes.map((n) => (n.id === drag.nodeId ? { ...n, x: Math.max(0, nx), y: Math.max(0, ny) } : n)),
        edges
      );
    } else if (panning) {
      setPan({ x: panning.px + (e.clientX - panning.sx), y: panning.py + (e.clientY - panning.sy) });
    }
  };

  const endInteractions = () => {
    setDrag(null);
    setPanning(null);
  };

  // ── Panning ──────────────────────────────────────────────────────────────

  const startPan = (e: React.PointerEvent) => {
    if (e.button !== 0 && e.button !== 1) return;
    onSelectNode(null);
    setPanning({ sx: e.clientX, sy: e.clientY, px: pan.x, py: pan.y });
  };

  // ── Edge wiring ──────────────────────────────────────────────────────────

  const startConnect = (e: React.PointerEvent, port: Port) => {
    if (!editable) return;
    e.stopPropagation();
    try {
      (e.target as HTMLElement).setPointerCapture?.(e.pointerId);
    } catch {
      // Same guard as node drag — capture is best-effort.
    }
    setConnect(port);
    setGhost({ x: port.x, y: port.y });
  };

  const moveConnect = (e: React.PointerEvent) => {
    if (!connect) return;
    const w = toWorld(e.clientX, e.clientY);
    setGhost({ x: w.x, y: w.y });
  };

  const finishConnect = (e: React.PointerEvent) => {
    if (!connect) return;
    const w = toWorld(e.clientX, e.clientY);

    // Resolution order (both bugs found in live preview):
    // 1. Body hit — release point inside a node rect wires the edge. The
    //    old port-distance-only check silently ignored drops on a node's
    //    body center (86px from the left-edge input port, beyond the 64px
    //    threshold), so the most natural gesture did nothing.
    // 2. Nearest visible port within threshold — for precise port-to-port
    //    wiring. Reverse-wiring (dragging FROM an input port) only binds to
    //    the target's visible out port: condition nodes' true/false ports
    //    sit at invisible top/bottom-center positions and used to win the
    //    nearest-port contest, creating accidental branch edges.
    const hitNode = nodes.find(
      (n) =>
        n.id !== connect.nodeId &&
        w.x >= n.x &&
        w.x <= n.x + NODE_W &&
        w.y >= n.y &&
        w.y <= n.y + NODE_H
    );

    let best: { nodeId: string; kind: Port["kind"]; dist: number } | null = null;
    if (!hitNode) {
      for (const n of nodes) {
        if (n.id === connect.nodeId) continue;
        const candidates: Port["kind"][] = connect.kind === "in" ? ["out"] : ["in"];
        for (const kind of candidates) {
          const p = ports.get(`${n.id}:${kind}`);
          if (!p) continue;
          const d = Math.hypot(p.x - w.x, p.y - w.y);
          if (d < NODE_H && (!best || d < best.dist)) best = { nodeId: n.id, kind, dist: d };
        }
      }
    }

    const reverse = connect.kind === "in";
    let from = connect.nodeId;
    let to: string | null = null;
    let condition =
      !reverse && (connect.kind === "true" || connect.kind === "false")
        ? connect.kind
        : undefined;

    if (hitNode) {
      if (reverse) {
        from = hitNode.id;
        to = connect.nodeId;
        condition = undefined;
      } else {
        to = hitNode.id;
      }
    } else if (best) {
      if (reverse) {
        from = best.nodeId;
        to = connect.nodeId;
      } else {
        to = best.nodeId;
      }
    }

    if (to) {
      // One outgoing edge per output port/branch (replace existing):
      // branch ports replace only the same branch; a plain out port replaces
      // the previous unconditional edge.
      const cleaned = edges.filter(
        (ed) => !(ed.from === from && (ed.condition ?? null) === (condition ?? null))
      );
      onChange(nodes, [...cleaned, { from, to, condition }]);
    }
    setConnect(null);
    setGhost(null);
  };

  // ── Drop from palette ────────────────────────────────────────────────────

  const onDrop = (e: React.DragEvent) => {
    e.preventDefault();
    if (!editable) return;
    const type = e.dataTransfer.getData("application/dash-node-type") as WorkflowNode["type"] | "";
    if (!type || !(type in NODE_META)) return;
    const w = toWorld(e.clientX, e.clientY);
    const node: WorkflowNode = {
      id: newId(type.slice(0, 2) + "_"),
      type,
      config: type === "condition" ? { field: "", op: "eq", value: "" } : {},
      x: snap(w.x - NODE_W / 2),
      y: snap(w.y - NODE_H / 2),
    };
    onChange([...nodes, node], edges);
    onSelectNode(node.id);
  };

  // ── Keyboard delete ──────────────────────────────────────────────────────

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (!selectedNodeId) return;
      const target = e.target as HTMLElement;
      if (target.tagName === "INPUT" || target.tagName === "TEXTAREA" || target.isContentEditable) return;
      if (e.key === "Delete" || e.key === "Backspace") {
        e.preventDefault();
        const nextNodes = nodes.filter((n) => n.id !== selectedNodeId);
        const nextEdges = edges.filter((ed) => ed.from !== selectedNodeId && ed.to !== selectedNodeId);
        onChange(nextNodes, nextEdges);
        onSelectNode(null);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [selectedNodeId, nodes, edges, onChange, onSelectNode]);

  // ── Render ───────────────────────────────────────────────────────────────

  const viewW = 1400;
  const viewH = 900;

  return (
    <div
      ref={canvasRef}
      role="application"
      aria-label="Workflow canvas — drag nodes, connect ports to wire the flow"
      onDragOver={(e) => {
        e.preventDefault();
        e.dataTransfer.dropEffect = "copy";
      }}
      onDrop={onDrop}
      onPointerDown={startPan}
      onPointerMove={(e) => {
        onPointerMove(e);
        moveConnect(e);
      }}
      onPointerUp={(e) => {
        endInteractions();
        finishConnect(e);
      }}
      onPointerLeave={() => {
        endInteractions();
        setConnect(null);
        setGhost(null);
      }}
      style={{
        position: "relative",
        height: "100%",
        minHeight: 380,
        overflow: "hidden",
        borderRadius: "var(--dash-radius-md)",
        border: "1px solid var(--dash-border)",
        background:
          "radial-gradient(circle at 12px 12px, rgba(63,169,245,0.10) 1px, transparent 1px)",
        backgroundSize: `${GRID * 2}px ${GRID * 2}px`,
        cursor: panning ? "grabbing" : "default",
        touchAction: "none",
      }}
    >
      <div
        style={{
          position: "absolute",
          inset: 0,
          transform: `translate(${pan.x}px, ${pan.y}px)`,
          transformOrigin: "0 0",
        }}
      >
        {/* Edges */}
        <svg
          width="100%"
          height="100%"
          style={{ position: "absolute", inset: 0, width: viewW, height: viewH, overflow: "visible", pointerEvents: "none" }}
        >
          <defs>
            <marker id="wf-arrow" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" orient="auto-start-reverse">
              <path d="M 0 0 L 10 5 L 0 10 z" fill="rgba(63,169,245,0.55)" />
            </marker>
          </defs>
          {edges.map((ed, i) => {
            const from = ports.get(`${ed.from}:${ed.condition ?? "out"}`);
            const to = ports.get(`${ed.to}:in`);
            if (!from || !to) return null;
            const active = selectedNodeId === ed.from || selectedNodeId === ed.to;
            const branchColor =
              ed.condition === "true"
                ? "var(--dash-success)"
                : ed.condition === "false"
                  ? "var(--dash-danger)"
                  : undefined;
            return (
              <g key={`${ed.from}-${ed.to}-${ed.condition ?? "out"}-${i}`}>
                <path
                  d={edgePath(from.x, from.y, to.x, to.y)}
                  fill="none"
                  stroke={branchColor ?? (active ? "var(--dash-accent)" : "rgba(63,169,245,0.4)")}
                  strokeWidth={active ? 2.5 : 1.8}
                  strokeDasharray={ed.condition ? "6 4" : undefined}
                  markerEnd="url(#wf-arrow)"
                />
                {ed.condition && (
                  <text
                    x={(from.x + to.x) / 2}
                    y={(from.y + to.y) / 2 - 6}
                    textAnchor="middle"
                    fontSize="10"
                    fontFamily="'JetBrains Mono', monospace"
                    fill={branchColor}
                  >
                    {ed.condition === "true" ? "TRUE" : "FALSE"}
                  </text>
                )}
              </g>
            );
          })}

          {/* In-progress connection ghost */}
          {connect && ghost && (
            <path
              d={edgePath(connect.x, connect.y, ghost.x, ghost.y)}
              fill="none"
              stroke="var(--dash-accent)"
              strokeWidth={2}
              strokeDasharray="4 4"
              opacity={0.8}
            />
          )}
        </svg>

        {/* Nodes */}
        {nodes.map((n) => {
          const meta = NODE_META[n.type] ?? NODE_META.action;
          const { Icon } = meta;
          const selected = selectedNodeId === n.id;
          const summary =
            Object.entries(n.config)
              .filter(([, v]) => v !== "" && v !== null && v !== undefined)
              .map(([k, v]) => `${k}: ${v}`)
              .slice(0, 2)
              .join("  ") || meta.label;
          return (
            <div
              key={n.id}
              role="button"
              tabIndex={0}
              aria-label={`${meta.label} node${Object.keys(n.config).length ? ` (${summary})` : ""}. Arrow keys move, Delete removes.`}
              onPointerDown={(e) => startNodeDrag(e, n)}
              onKeyDown={(e) => {
                // Keyboard access: arrows nudge by one grid cell (matches
                // pointer-drag snapping), Enter/Space select.
                if (e.key === "Enter" || e.key === " ") {
                  e.preventDefault();
                  onSelectNode(n.id);
                  return;
                }
                const deltas: Record<string, [number, number]> = {
                  ArrowLeft: [-GRID, 0],
                  ArrowRight: [GRID, 0],
                  ArrowUp: [0, -GRID],
                  ArrowDown: [0, GRID],
                };
                const d = deltas[e.key];
                if (d && editable) {
                  e.preventDefault();
                  onChange(
                    nodes.map((m) =>
                      m.id === n.id
                        ? { ...m, x: Math.max(0, m.x + d[0]), y: Math.max(0, m.y + d[1]) }
                        : m
                    ),
                    edges
                  );
                }
              }}
              style={{
                position: "absolute",
                left: n.x,
                top: n.y,
                width: NODE_W,
                height: NODE_H,
                borderRadius: "var(--dash-radius-md)",
                background: "var(--dash-elevated)",
                border: `1.5px solid ${selected ? meta.color : `${meta.color}55`}`,
                boxShadow: selected
                  ? `0 0 0 3px ${meta.color}30, 0 4px 16px rgba(0,0,0,0.4)`
                  : "0 2px 10px rgba(0,0,0,0.35)",
                display: "flex",
                alignItems: "center",
                gap: 10,
                padding: "0 12px",
                cursor: drag?.nodeId === n.id ? "grabbing" : "grab",
                userSelect: "none",
              }}
            >
              <div
                style={{
                  width: 32,
                  height: 32,
                  flexShrink: 0,
                  borderRadius: "var(--dash-radius-sm)",
                  background: `${meta.color}22`,
                  display: "flex",
                  alignItems: "center",
                  justifyContent: "center",
                }}
              >
                <Icon size={15} color={meta.color} />
              </div>
              <div style={{ minWidth: 0 }}>
                <div
                  style={{
                    fontSize: 12,
                    fontWeight: 600,
                    color: "var(--dash-text)",
                    textTransform: "capitalize",
                    lineHeight: 1.2,
                  }}
                >
                  {n.config.label as string | undefined ?? meta.label}
                </div>
                <div
                  style={{
                    fontSize: 10,
                    color: "var(--dash-text-muted)",
                    fontFamily: "'JetBrains Mono', monospace",
                    whiteSpace: "nowrap",
                    overflow: "hidden",
                    textOverflow: "ellipsis",
                    maxWidth: 110,
                    marginTop: 2,
                  }}
                >
                  {summary}
                </div>
              </div>

              {/* Input port (all types) */}
              <PortDot
                port={ports.get(`${n.id}:in`)!}
                color={meta.color}
                side="left"
                onStart={(p, e) => startConnect(e, p)}
              />
              {/* Output ports */}
              {n.type === "condition" ? (
                <>
                  <PortDot port={ports.get(`${n.id}:true`)!} color="var(--dash-success)" side="top" onStart={(p, e) => startConnect(e, p)} />
                  <PortDot port={ports.get(`${n.id}:false`)!} color="var(--dash-danger)" side="bottom" onStart={(p, e) => startConnect(e, p)} />
                </>
              ) : (
                <PortDot port={ports.get(`${n.id}:out`)!} color={meta.color} side="right" onStart={(p, e) => startConnect(e, p)} />
              )}
            </div>
          );
        })}
      </div>

      {/* Toolbar */}
      <div
        onPointerDown={(e) => e.stopPropagation()}
        style={{
          position: "absolute",
          top: 8,
          right: 8,
          display: "flex",
          gap: 6,
          alignItems: "center",
        }}
      >
        <span
          style={{
            fontSize: 10,
            fontFamily: "'JetBrains Mono', monospace",
            color: "var(--dash-text-muted)",
            background: "var(--dash-glass-bg)",
            border: "1px solid var(--dash-border)",
            borderRadius: "var(--dash-radius-full)",
            padding: "3px 8px",
          }}
        >
          {nodes.length} nodes · {edges.length} links
        </span>
        {editable && selectedNodeId && (
          <button
            onClick={() => {
              const nextNodes = nodes.filter((n) => n.id !== selectedNodeId);
              const nextEdges = edges.filter((ed) => ed.from !== selectedNodeId && ed.to !== selectedNodeId);
              onChange(nextNodes, nextEdges);
              onSelectNode(null);
            }}
            className="dash-btn-ghost"
            aria-label="Delete selected node"
            style={{ background: "var(--dash-glass-bg)", border: "1px solid var(--dash-border)" }}
          >
            <Trash2 size={12} color="var(--dash-danger)" />
          </button>
        )}
        {editable && nodes.length > 0 && (
          <button
            onClick={() => {
              onChange([], []);
              onSelectNode(null);
            }}
            className="dash-btn-ghost"
            aria-label="Clear canvas"
            style={{ background: "var(--dash-glass-bg)", border: "1px solid var(--dash-border)" }}
          >
            <X size={12} />
          </button>
        )}
      </div>

      {nodes.length === 0 && (
        <div
          style={{
            position: "absolute",
            inset: 0,
            display: "flex",
            flexDirection: "column",
            alignItems: "center",
            justifyContent: "center",
            pointerEvents: "none",
            color: "var(--dash-text-muted)",
            gap: 8,
          }}
        >
          <GitBranch size={26} opacity={0.4} />
          <div style={{ fontSize: 13 }}>Drag nodes from the palette to start</div>
          <div style={{ fontSize: 11, opacity: 0.7 }}>
            Trigger → actions. Use If/Else to branch TRUE/FALSE paths.
          </div>
        </div>
      )}
    </div>
  );
};

// ── Port dot ────────────────────────────────────────────────────────────────

function PortDot({
  port,
  color,
  side,
  onStart,
}: {
  port: Port;
  color: string;
  side: "left" | "right" | "top" | "bottom";
  onStart: (port: Port, e: React.PointerEvent) => void;
}) {
  const pos: React.CSSProperties =
    side === "left"
      ? { left: -PORT_R - 2, top: `calc(50% - ${PORT_R}px)` }
      : side === "right"
        ? { right: -PORT_R - 2, top: `calc(50% - ${PORT_R}px)` }
        : side === "top"
          ? { top: -PORT_R - 2, left: `calc(50% - ${PORT_R}px)` }
          : { bottom: -PORT_R - 2, left: `calc(50% - ${PORT_R}px)` };
  return (
    <div
      onPointerDown={(e) => onStart(port, e)}
      title={`${side} port`}
      style={{
        position: "absolute",
        width: PORT_R * 2,
        height: PORT_R * 2,
        borderRadius: "50%",
        background: "var(--dash-bg)",
        border: `2px solid ${color}`,
        cursor: "crosshair",
        zIndex: 3,
        ...pos,
      }}
    />
  );
}

export default WorkflowCanvas;
