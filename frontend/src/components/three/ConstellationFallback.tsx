import { useMemo } from "react";

import type { CareerRole, CatalogueSkill } from "@/lib/types";
import { CATEGORY_COLOR } from "@/lib/utils";

import { constellationLayout } from "./constellationLayout";

/** 2D projection of the same data-driven layout (reduced motion / no WebGL). */
export function ConstellationFallback({ roles, skills }: { roles: CareerRole[]; skills: CatalogueSkill[] }) {
  const { nodes, edges } = useMemo(() => constellationLayout(roles, skills), [roles, skills]);
  const project = (p: [number, number, number]) => [250 + p[0] * 45, 210 + p[2] * 30 - p[1] * 22] as const;
  return (
    <svg viewBox="0 0 500 420" className="h-full w-full" role="img" aria-label="Map of career roles and the skills they require">
      {edges.map((e, i) => {
        const [x1, y1] = project(nodes[e.a]!.position);
        const [x2, y2] = project(nodes[e.b]!.position);
        return <line key={i} x1={x1} y1={y1} x2={x2} y2={y2} stroke="#5eead4" strokeOpacity={0.08 + e.importance * 0.12} />;
      })}
      {nodes.map((n) => {
        const [x, y] = project(n.position);
        return n.kind === "role" ? (
          <g key={n.id}>
            <circle cx={x} cy={y} r={7} fill="#e8edf6" />
            <text x={x} y={y - 12} textAnchor="middle" className="fill-fg font-display text-[11px]">
              {n.label}
            </text>
          </g>
        ) : (
          <circle key={n.id} cx={x} cy={y} r={2.5 + n.degree * 0.5} fill={CATEGORY_COLOR[n.category ?? ""] ?? "#a3b0c6"} opacity={0.85}>
            <title>{n.label}</title>
          </circle>
        );
      })}
    </svg>
  );
}
