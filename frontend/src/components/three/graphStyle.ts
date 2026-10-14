import type { GraphEdge, GraphNode } from "@/lib/types";
import { CATEGORY_COLOR } from "@/lib/utils";

export const TYPE_COLOR: Record<string, string> = {
  student: "#5eead4",
  role: "#e8edf6",
  resource: "#fbbf24",
  assessment: "#34d399",
  project: "#f9a8d4",
};

export function nodeColor(n: GraphNode): string {
  if (n.type === "skill") {
    if (n.action === "learn" || n.action === "prerequisite") return "#fb7185";
    return CATEGORY_COLOR[n.category ?? ""] ?? "#a3b0c6";
  }
  return TYPE_COLOR[n.type] ?? "#a3b0c6";
}

export function nodeSize(n: GraphNode): number {
  switch (n.type) {
    case "student":
      return 0.42;
    case "role":
      return 0.36;
    case "skill":
      return 0.16 + (n.required_level ?? 0) * 0.025;
    default:
      return 0.11;
  }
}

export function edgeColor(e: GraphEdge): string {
  switch (e.provenance) {
    case "evidence":
      return "#34d399";
    case "self_reported":
      return "#fbbf24";
    case "inferred":
      return "#a78bfa";
    default:
      return "#4b5d80";
  }
}
