import type { CareerRole, CatalogueSkill } from "@/lib/types";

export interface CNode {
  id: string;
  label: string;
  kind: "role" | "skill";
  category?: string;
  position: [number, number, number];
  degree: number;
}

export interface CEdge {
  a: number;
  b: number;
  importance: number;
}

function hash(n: number): number {
  const x = Math.sin(n * 12.9898) * 43758.5453;
  return x - Math.floor(x);
}

/** Deterministic layout of the real role–skill framework: roles on a ring, each skill at the
 * centroid of the roles that require it, lifted by category so clusters stay readable. */
export function constellationLayout(roles: CareerRole[], skills: CatalogueSkill[]): { nodes: CNode[]; edges: CEdge[] } {
  const nodes: CNode[] = [];
  const edges: CEdge[] = [];
  const R = 4.2;
  const roleIdx = new Map<number, number>();
  roles.forEach((r, i) => {
    const t = (i / roles.length) * Math.PI * 2;
    roleIdx.set(r.id, nodes.length);
    nodes.push({ id: `role:${r.id}`, label: r.name, kind: "role", position: [Math.cos(t) * R, (i % 2 ? 0.6 : -0.6), Math.sin(t) * R], degree: r.requirements.length });
  });
  const cats = Array.from(new Set(skills.map((s) => s.category)));
  const skillIdx = new Map<number, number>();
  for (const s of skills) {
    const requiring = roles.filter((r) => r.requirements.some((q) => q.skill_id === s.id));
    if (!requiring.length) continue;
    let x = 0;
    let z = 0;
    for (const r of requiring) {
      const p = nodes[roleIdx.get(r.id)!]!.position;
      x += p[0];
      z += p[2];
    }
    x /= requiring.length;
    z /= requiring.length;
    const spread = 1.6 - Math.min(requiring.length, 5) * 0.22;
    const jx = (hash(s.id) - 0.5) * spread * 2;
    const jz = (hash(s.id + 99) - 0.5) * spread * 2;
    const y = ((cats.indexOf(s.category) / Math.max(cats.length - 1, 1)) - 0.5) * 3.2 + (hash(s.id + 7) - 0.5) * 0.5;
    skillIdx.set(s.id, nodes.length);
    nodes.push({ id: `skill:${s.id}`, label: s.name, kind: "skill", category: s.category, position: [x * 0.62 + jx, y, z * 0.62 + jz], degree: requiring.length });
  }
  for (const r of roles) {
    for (const q of r.requirements) {
      const b = skillIdx.get(q.skill_id);
      if (b !== undefined) edges.push({ a: roleIdx.get(r.id)!, b, importance: q.importance });
    }
  }
  return { nodes, edges };
}
