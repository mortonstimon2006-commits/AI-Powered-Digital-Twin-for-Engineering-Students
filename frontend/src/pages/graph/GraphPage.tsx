import { useQuery } from "@tanstack/react-query";
import { ExternalLink, Lightbulb, Network, Search } from "lucide-react";
import { lazy, Suspense, useMemo, useState } from "react";

import { PageHeader } from "@/components/layout/AppShell";
import { Graph2D } from "@/components/three/Graph2D";
import { edgeColor, nodeColor, TYPE_COLOR } from "@/components/three/graphStyle";
import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader, StatusBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Skeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useProfile, useRoles } from "@/lib/queries";
import type { GraphEdge, GraphNode, GraphPayload } from "@/lib/types";
import { ACTION_META, CATEGORY_LABEL, cn, level, pct } from "@/lib/utils";
import { useCan3D } from "@/lib/visuals";

const Graph3D = lazy(() => import("@/components/three/Graph3D"));

const EDGE_TEXT: Record<string, (s: string, t: string, e: GraphEdge) => string> = {
  SKILL_PREREQUISITE_OF: (s, t, e) => `${s} is a prerequisite of ${t} (level ${e.min_level}+ expected first).`,
  SKILL_REQUIRED_FOR_ROLE: (s, t, e) => `${t} requires ${s} at level ${e.level} (importance ${e.importance}).`,
  ROLE_REQUIRES_TECHNOLOGY: (s, t, e) => `${s} requires the technology ${t} at level ${e.level}.`,
  RESOURCE_TEACHES_SKILL: (s, t) => `${s} teaches ${t}.`,
  ASSESSMENT_MEASURES_SKILL: (s, t) => `${s} measures ${t}.`,
  STUDENT_HAS_SKILL: (_s, t, e) => `You have ${t} at ${level(e.level ?? null)} (${String(e.status).replace("_", " ")}).`,
  STUDENT_LIKELY_HAS_SKILL: (_s, t, e) => `Inferred: you likely have ${t} at ≥${e.level}, because you demonstrated ${e.because}. Not recorded evidence.`,
  PROJECT_DEMONSTRATES_SKILL: (s, t, e) => `Project "${s}" demonstrates ${t} at level ${e.level}.`,
  STUDENT_BUILT_PROJECT: (_s, t) => `You built ${t}.`,
};

interface Insights {
  role_name: string;
  blocking_prerequisites: { blocked_skill: string; prerequisite: string; needed_level: number; current_level: number | null; path: string[] }[];
  resources_for_top_gaps: { skill: string; action: string; resources: { id: number; title: string; url: string; provider: string; verification_status: string }[] }[];
  alternative_roles: { role_id: number; role_name: string; match: number; match_upper: number; is_target: boolean; met_skills: string[] }[];
  multi_role_unlocks: { skill: string; role_count: number; roles: { role: string; required_level: number }[] }[];
}

export function GraphPage() {
  const profile = useProfile();
  const roles = useRoles();
  const [roleId, setRoleId] = useState<number | null>(null);
  const [include, setInclude] = useState({ resource: true, assessment: false, project: true });
  const [prov, setProv] = useState({ framework: true, evidence: true, self_reported: true, inferred: true });
  const [query, setQuery] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const { enabled, reason } = useCan3D();
  const [force2d, setForce2d] = useState(false);
  const active = roleId ?? profile.data?.target_role_id ?? null;
  const inc = Object.entries(include).filter(([, v]) => v).map(([k]) => k).join(",");
  const graph = useQuery({
    queryKey: ["graph", active, inc],
    queryFn: () => api<GraphPayload>("/knowledge-graph", { query: { role_id: active, include: inc } }),
    enabled: profile.isSuccess,
  });
  const insights = useQuery({ queryKey: ["graph", "insights", active], queryFn: () => api<Insights>("/knowledge-graph/insights", { query: { role_id: active } }), enabled: Boolean(active) });

  const { nodes, edges } = useMemo(() => {
    const g = graph.data;
    if (!g) return { nodes: [] as GraphNode[], edges: [] as GraphEdge[] };
    const es = g.edges.filter((e) => prov[e.provenance]);
    return { nodes: g.nodes, edges: es };
  }, [graph.data, prov]);
  const byId = useMemo(() => new Map(nodes.map((n) => [n.id, n])), [nodes]);
  const matches = query ? nodes.filter((n) => n.label.toLowerCase().includes(query.toLowerCase())).slice(0, 8) : [];
  const node = selected ? byId.get(selected) : undefined;
  const nodeEdges = selected ? edges.filter((e) => e.source === selected || e.target === selected) : [];

  return (
    <div>
      <PageHeader icon={Network} eyebrow="Knowledge graph" title="How your skills connect to roles"
        description="Built live from the role-skill catalogue and your recorded evidence. Dashed purple edges are inferences, not records." />
      <div className="grid gap-5 xl:grid-cols-[1fr_340px]">
        <Card className="overflow-hidden">
          <div className="flex flex-wrap items-center gap-2 border-b border-line p-3">
            <Select aria-label="Role focus" className="h-9 w-48 text-xs" value={active ?? ""} onChange={(e) => { setRoleId(Number(e.target.value)); setSelected(null); }}>
              <option value="" disabled>All skills</option>
              {roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
            </Select>
            {(["resource", "assessment", "project"] as const).map((k) => (
              <button key={k} type="button" aria-pressed={include[k]} onClick={() => setInclude((s) => ({ ...s, [k]: !s[k] }))}
                className={cn("rounded-full border px-2.5 py-1 text-xs capitalize transition", include[k] ? "border-aurora/50 text-aurora" : "border-line text-fg-faint")}>{k}s</button>
            ))}
            <span className="mx-1 h-5 w-px bg-line" aria-hidden />
            {(Object.keys(prov) as (keyof typeof prov)[]).map((k) => (
              <button key={k} type="button" aria-pressed={prov[k]} onClick={() => setProv((s) => ({ ...s, [k]: !s[k] }))}
                className={cn("flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition", prov[k] ? "border-line-strong text-fg" : "border-line text-fg-faint line-through")}>
                <span className="h-0.5 w-3" style={{ background: edgeColor({ provenance: k } as GraphEdge) }} />{k.replace("_", " ")}
              </button>
            ))}
            <div className="relative ml-auto">
              <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-fg-faint" />
              <Input aria-label="Find a node" className="h-9 w-44 pl-8 text-xs" placeholder="Find node" value={query} onChange={(e) => setQuery(e.target.value)} />
              {matches.length > 0 && (
                <ul className="absolute right-0 z-20 mt-1 w-56 rounded-lg border border-line-strong bg-ink-750 py-1 text-sm shadow-xl">
                  {matches.map((m) => <li key={m.id}><button type="button" className="w-full px-3 py-1.5 text-left hover:bg-white/[0.05]" onClick={() => { setSelected(m.id); setQuery(""); }}>{m.label} <span className="text-xs text-fg-faint">{m.type}</span></button></li>)}
                </ul>
              )}
            </div>
          </div>
          <div className="relative h-[560px] bg-ink-900">
            {graph.isLoading ? <Skeleton className="h-full w-full rounded-none" /> : graph.error ? <div className="p-6"><ErrorState error={graph.error} onRetry={() => graph.refetch()} /></div>
              : !nodes.length ? <div className="p-6"><EmptyState title="Nothing to show" /></div>
              : enabled && !force2d ? (
                <Suspense fallback={<Skeleton className="h-full w-full rounded-none" />}>
                  <Graph3D nodes={nodes} edges={edges} selected={selected} onSelect={setSelected} />
                </Suspense>
              ) : <Graph2D nodes={nodes} edges={edges} selected={selected} onSelect={setSelected} />}
            <div className="absolute bottom-3 left-3 flex flex-wrap gap-2 rounded-lg bg-ink-850/85 px-3 py-2 text-[0.7rem] text-fg-muted backdrop-blur">
              {Object.entries(TYPE_COLOR).map(([k, c]) => <span key={k} className="flex items-center gap-1"><span className="size-2 rounded-full" style={{ background: c }} />{k}</span>)}
              <span className="flex items-center gap-1"><span className="size-2 rounded-full bg-danger" />gap skill</span>
            </div>
            <div className="absolute right-3 top-3 flex items-center gap-2">
              {graph.data && <Badge tone="muted">{graph.data.counts.nodes} nodes · {edges.length} edges</Badge>}
              {enabled && <Button size="sm" variant="secondary" onClick={() => setForce2d((v) => !v)}>{force2d ? "3D view" : "2D view"}</Button>}
            </div>
          </div>
          {!enabled && <p className="px-4 py-2 text-xs text-fg-faint">{reason} Showing the 2D graph.</p>}
        </Card>

        <div className="space-y-5">
          <Card>
            <CardHeader title={node ? node.label : "Node details"} description={node ? `Type: ${node.type}` : "Select a node to see its relationships."} />
            <CardBody className="space-y-3 text-sm">
              {node ? (
                <>
                  {node.type === "skill" && (
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge tone="muted">{CATEGORY_LABEL[node.category ?? ""] ?? node.category}</Badge>
                      <StatusBadge status={node.status ?? "unknown"} />
                      <span className="metric">level {level(node.level ?? null)}{node.required_level ? ` / req ${node.required_level}` : ""}</span>
                      {node.action && <Badge tone={ACTION_META[node.action]?.tone ?? "muted"}>{ACTION_META[node.action]?.label}</Badge>}
                    </div>
                  )}
                  {node.type === "resource" && node.url && (
                    <a className="inline-flex items-center gap-1.5 text-aurora hover:underline" href={node.url} target="_blank" rel="noopener noreferrer nofollow"><ExternalLink className="size-3.5" />{node.provider} · link {node.verification}</a>
                  )}
                  <ul className="max-h-72 space-y-2 overflow-y-auto">
                    {nodeEdges.map((e, i) => {
                      const s = byId.get(e.source)?.label ?? e.source;
                      const t = byId.get(e.target)?.label ?? e.target;
                      return (
                        <li key={i} className="flex gap-2 text-xs">
                          <span className="mt-1 h-0.5 w-3 shrink-0" style={{ background: edgeColor(e) }} />
                          <span className={cn("text-fg-muted", e.provenance === "inferred" && "italic")}>{(EDGE_TEXT[e.type] ?? (() => `${s} → ${t}`))(s, t, e)}</span>
                        </li>
                      );
                    })}
                  </ul>
                  <span className="sr-only">{nodeColor(node)}</span>
                </>
              ) : <p className="text-fg-muted">Drag to rotate, scroll to zoom, click a node. In 2D, Tab through nodes and press Enter.</p>}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Graph insights" description={insights.data ? `Queries for ${insights.data.role_name}` : "Choose a role."} actions={<Lightbulb className="size-4 text-warn" />} />
            <CardBody className="space-y-5 text-sm">
              {insights.isLoading ? <LoadingBlock rows={2} /> : insights.data && (
                <>
                  <section>
                    <p className="eyebrow mb-2">Blocking prerequisites</p>
                    {insights.data.blocking_prerequisites.length ? insights.data.blocking_prerequisites.slice(0, 5).map((b, i) => (
                      <p key={i} className="text-xs text-fg-muted">{b.path.join(" → ")} <span className="text-fg-faint">(needs {b.prerequisite} ≥ {b.needed_level}, you: {level(b.current_level)})</span></p>
                    )) : <p className="text-xs text-fg-muted">None — prerequisites for your gaps are met.</p>}
                  </section>
                  <section>
                    <p className="eyebrow mb-2">Skills that unlock several roles</p>
                    {insights.data.multi_role_unlocks.slice(0, 5).map((u) => <p key={u.skill} className="text-xs"><span className="text-fg">{u.skill}</span> <span className="text-fg-muted">— needed by {u.role_count} roles</span></p>)}
                  </section>
                  <section>
                    <p className="eyebrow mb-2">Closest alternative roles</p>
                    {insights.data.alternative_roles.filter((r) => !r.is_target).slice(0, 3).map((r) => <p key={r.role_id} className="text-xs"><span className="text-fg">{r.role_name}</span> <span className="metric text-fg-muted">{pct(r.match)}</span></p>)}
                  </section>
                  <section>
                    <p className="eyebrow mb-2">Resources for top gaps</p>
                    {insights.data.resources_for_top_gaps.slice(0, 3).map((g) => (
                      <div key={g.skill} className="mb-2">
                        <p className="text-xs text-fg">{g.skill}</p>
                        {g.resources.slice(0, 2).map((r) => <a key={r.id} href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="block truncate text-xs text-aurora hover:underline">{r.title}</a>)}
                      </div>
                    ))}
                  </section>
                </>
              )}
            </CardBody>
          </Card>
        </div>
      </div>
    </div>
  );
}
