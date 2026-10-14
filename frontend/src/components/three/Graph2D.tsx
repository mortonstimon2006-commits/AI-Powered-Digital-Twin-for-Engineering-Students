import { useMemo } from "react";

import type { GraphEdge, GraphNode } from "@/lib/types";

import { edgeColor, nodeColor, nodeSize } from "./graphStyle";

/** Accessible 2D graph (fallback for no-WebGL / reduced motion / user preference). Nodes are
 * focusable buttons; Enter/Space selects. */
export function Graph2D({ nodes, edges, selected, onSelect }: { nodes: GraphNode[]; edges: GraphEdge[]; selected: string | null; onSelect: (id: string | null) => void }) {
  const pos = useMemo(() => {
    const xs = nodes.map((n) => n.position[0]);
    const ys = nodes.map((n) => n.position[1] + n.position[2] * 0.35);
    const [minX, maxX, minY, maxY] = [Math.min(...xs), Math.max(...xs), Math.min(...ys), Math.max(...ys)];
    const m = new Map<string, [number, number]>();
    nodes.forEach((n, i) => m.set(n.id, [40 + ((xs[i]! - minX) / (maxX - minX || 1)) * 820, 30 + ((ys[i]! - minY) / (maxY - minY || 1)) * 520]));
    return m;
  }, [nodes]);
  return (
    <svg viewBox="0 0 900 580" className="h-full w-full" role="group" aria-label="Knowledge graph (2D)">
      {edges.map((e, i) => {
        const a = pos.get(e.source);
        const b = pos.get(e.target);
        if (!a || !b) return null;
        const on = selected !== null && (e.source === selected || e.target === selected);
        return <line key={i} x1={a[0]} y1={a[1]} x2={b[0]} y2={b[1]} stroke={edgeColor(e)} strokeOpacity={selected === null ? 0.45 : on ? 1 : 0.1}
          strokeDasharray={e.provenance === "inferred" ? "5 4" : undefined} strokeWidth={on ? 1.6 : 1} />;
      })}
      {nodes.map((n) => {
        const p = pos.get(n.id)!;
        const r = nodeSize(n) * 26;
        const active = n.id === selected;
        return (
          <g key={n.id} role="button" tabIndex={0} aria-label={`${n.type} ${n.label}`} aria-pressed={active} className="cursor-pointer focus:outline-none"
            onClick={() => onSelect(n.id)} onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onSelect(n.id); } }}>
            <circle cx={p[0]} cy={p[1]} r={r} fill={n.type === "skill" && n.status === "unknown" ? "transparent" : nodeColor(n)} stroke={nodeColor(n)}
              strokeWidth={active ? 3 : 1.5} strokeDasharray={n.type === "skill" && n.status === "unknown" ? "3 2" : undefined} />
            {(active || n.type === "role" || n.type === "student" || r > 5) && (
              <text x={p[0]} y={p[1] - r - 4} textAnchor="middle" className="fill-fg-muted text-[10px]">{n.label}</text>
            )}
          </g>
        );
      })}
    </svg>
  );
}
