import { useQuery } from "@tanstack/react-query";
import { ChartSpline } from "lucide-react";
import { useMemo, useState } from "react";
import { CartesianGrid, Legend, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/layout/AppShell";
import { Select } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api } from "@/lib/api";
import { qk } from "@/lib/queries";
import { BAND_META, CATEGORY_COLOR, CATEGORY_LABEL, dateOnly, dateTime, pct } from "@/lib/utils";

interface Timeline {
  snapshots: { version: number; reason: string; created_at: string; features: Record<string, number | null> }[];
  predictions: { created_at: string; band: string; probability: number | null; model_version: string }[];
  roadmap_events: { occurred_at: string; event: string; from: string | null; to: string | null }[];
  note: string;
}

const CATS = ["programming", "dsa", "databases", "web", "ml_ai", "data", "cloud_devops", "security"];
const tooltip = { background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" };

export function ProgressPage() {
  const q = useQuery({ queryKey: qk.timeline, queryFn: () => api<Timeline>("/progress/timeline") });
  const [metric, setMetric] = useState<"categories" | "evidence">("categories");
  const series = useMemo(() => (q.data?.snapshots ?? []).map((s) => ({
    v: `v${s.version}`, date: dateOnly(s.created_at),
    ...Object.fromEntries(CATS.map((c) => [c, s.features[`lvl_${c}`] ?? null])),
    evidence: s.features.evidence_strength !== null && s.features.evidence_strength !== undefined ? Number(s.features.evidence_strength) * 100 : null,
    projects: s.features.projects ?? 0,
  })), [q.data]);
  const activeCats = CATS.filter((c) => series.some((s) => (s as Record<string, unknown>)[c] !== null));
  if (q.isLoading) return <LoadingBlock rows={4} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const t = q.data!;
  return (
    <div>
      <PageHeader icon={ChartSpline} eyebrow="Longitudinal progress" title="How your twin has evolved"
        description="Measured history only — recorded profile versions, readiness estimates and roadmap activity. Simulations are never mixed in." />
      <Notice tone="info" className="mb-5">{t.note}</Notice>
      {t.snapshots.length < 2 ? (
        <EmptyState icon={<ChartSpline className="size-5" />} title="Not enough history yet">Each change to your twin creates a version. Come back after a few updates.</EmptyState>
      ) : (
        <div className="space-y-5">
          <Card>
            <CardHeader title="Skill trajectory by version" description="Evidence-weighted category levels as recorded in each twin version."
              actions={<Select aria-label="Metric" className="h-9 w-48 text-xs" value={metric} onChange={(e) => setMetric(e.target.value as typeof metric)}>
                <option value="categories">Category levels</option><option value="evidence">Evidence strength & projects</option></Select>} />
            <CardBody>
              <div className="h-80">
                <ResponsiveContainer>
                  <LineChart data={series} margin={{ left: -12, right: 12 }}>
                    <CartesianGrid stroke="#1a2338" />
                    <XAxis dataKey="v" tick={{ fill: "#6f7d96", fontSize: 11 }} />
                    <YAxis tick={{ fill: "#6f7d96", fontSize: 11 }} domain={metric === "categories" ? [0, 4] : [0, "auto"]} />
                    <Tooltip contentStyle={tooltip} />
                    <Legend wrapperStyle={{ fontSize: 12 }} />
                    {metric === "categories"
                      ? activeCats.map((c) => <Line key={c} type="monotone" dataKey={c} name={CATEGORY_LABEL[c]} stroke={CATEGORY_COLOR[c]} strokeWidth={2} connectNulls dot={false} />)
                      : <>
                        <Line type="monotone" dataKey="evidence" name="Evidence strength (%)" stroke="#5eead4" strokeWidth={2} connectNulls />
                        <Line type="monotone" dataKey="projects" name="Projects" stroke="#a78bfa" strokeWidth={2} />
                      </>}
                  </LineChart>
                </ResponsiveContainer>
              </div>
            </CardBody>
          </Card>
          <div className="grid gap-5 lg:grid-cols-2">
            <Card>
              <CardHeader title="Readiness estimates over time" description="Each is pinned to a model version; compare only within one version." />
              <CardBody>
                {t.predictions.length ? (
                  <ul className="divide-y divide-line text-sm">
                    {t.predictions.map((p, i) => (
                      <li key={i} className="flex flex-wrap items-center gap-3 py-2">
                        <span className="w-40 text-fg-muted">{dateTime(p.created_at)}</span>
                        <Badge tone={p.band === "interview_ready" ? "ok" : p.band === "developing" ? "warn" : "danger"}>{BAND_META[p.band]?.label ?? p.band}</Badge>
                        <span className="metric">{p.probability !== null ? `≈ ${pct(p.probability)}` : "band only"}</span>
                        <span className="ml-auto font-mono text-[0.65rem] text-fg-faint">{p.model_version}</span>
                      </li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-fg-muted">No estimates recorded yet.</p>}
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Roadmap activity" />
              <CardBody>
                {t.roadmap_events.length ? (
                  <ul className="max-h-80 space-y-2 overflow-y-auto text-sm">
                    {t.roadmap_events.map((e, i) => (
                      <li key={i} className="flex gap-3"><span className="w-40 shrink-0 text-fg-faint">{dateTime(e.occurred_at)}</span>
                        <span className="capitalize text-fg-muted">{e.event.replace("_", " ")}{e.to && e.event === "status_changed" ? `: ${e.from?.replace("_", " ")} → ${e.to.replace("_", " ")}` : ""}</span></li>
                    ))}
                  </ul>
                ) : <p className="text-sm text-fg-muted">No roadmap activity yet.</p>}
              </CardBody>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}
