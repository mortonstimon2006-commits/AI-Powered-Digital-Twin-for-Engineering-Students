import { useQuery } from "@tanstack/react-query";
import { ArrowRight, GitCompareArrows } from "lucide-react";
import { useState } from "react";

import { Select } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api } from "@/lib/api";
import { qk } from "@/lib/queries";
import { dateTime } from "@/lib/utils";

interface Snapshot { id: string; version: number; reason: string; created_at: string }
interface Diff {
  from: { version: number; created_at: string };
  to: { version: number; created_at: string };
  changes: Record<string, unknown>[];
  feature_changes: { feature: string; before: number | null; after: number | null }[];
}

function describe(c: Record<string, unknown>): string {
  const k = String(c.kind);
  const v = (x: unknown) => (x === null || x === undefined || x === "" ? "—" : Array.isArray(x) ? x.join(", ") || "—" : String(x));
  if (k === "profile") return `${String(c.field).replaceAll("_", " ")}: ${v(c.before)} → ${v(c.after)}`;
  if (k === "self_rating") return `${c.skill} self-rating: ${v(c.before)} → ${v(c.after)}`;
  if (k.endsWith("_added")) return `${k.replace("_added", "").replace("_", " ")} added: ${c.title ?? c.skill ?? c.assessment}${c.source ? ` (${c.source})` : ""}${c.pct !== undefined ? ` — ${c.pct}%` : ""}`;
  if (k.endsWith("_removed")) return `${k.replace("_removed", "").replace("_", " ")} removed: ${c.title ?? c.skill}`;
  if (k.endsWith("_verification")) return `${c.title}: ${v(c.before)} → ${v(c.after)}`;
  return k;
}

export function HistorySection() {
  const snaps = useQuery({ queryKey: [...qk.snapshots, "all"], queryFn: () => api<{ items: Snapshot[] }>("/twin/snapshots", { query: { limit: 200 } }) });
  const [pickedFrom, setFrom] = useState<number | null>(null);
  const [pickedTo, setTo] = useState<number | null>(null);
  const list = snaps.data?.items ?? [];
  const to = pickedTo ?? list[0]?.version ?? null;
  const from = pickedFrom ?? (list.length >= 2 ? list[1]!.version : null);
  const diff = useQuery({
    queryKey: ["twin", "diff", from, to],
    queryFn: () => api<Diff>("/twin/diff", { query: { from_version: from, to_version: to } }),
    enabled: from !== null && to !== null,
  });
  if (snaps.isLoading) return <LoadingBlock rows={3} />;
  if (snaps.error) return <ErrorState error={snaps.error} />;
  const items = snaps.data!.items;
  if (items.length < 2) return <EmptyState icon={<GitCompareArrows className="size-5" />} title="Not enough history yet">Each saved change creates a twin version you can compare here.</EmptyState>;
  return (
    <div className="grid gap-5 lg:grid-cols-[1fr_1.4fr]">
      <Card>
        <CardHeader title="Versions" description={`${items.length} snapshots, newest first.`} />
        <CardBody>
          <ol className="max-h-[480px] space-y-2 overflow-y-auto pr-1">
            {items.map((s) => (
              <li key={s.id} className="flex items-center gap-3 rounded-lg px-2 py-1.5 text-sm hover:bg-white/[0.03]">
                <span className="metric w-10 text-fg-faint">v{s.version}</span>
                <span className="flex-1 capitalize text-fg-muted">{s.reason.replaceAll("_", " ")}</span>
                <span className="text-xs text-fg-faint">{dateTime(s.created_at)}</span>
              </li>
            ))}
          </ol>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Compare versions" description="Previous vs current: recorded changes and their effect on model inputs." />
        <CardBody className="space-y-4">
          <div className="flex flex-wrap items-center gap-2">
            <Select aria-label="From version" className="w-32" value={from ?? ""} onChange={(e) => setFrom(Number(e.target.value))}>
              {items.map((s) => <option key={s.version} value={s.version}>v{s.version}</option>)}
            </Select>
            <ArrowRight className="size-4 text-fg-faint" aria-hidden />
            <Select aria-label="To version" className="w-32" value={to ?? ""} onChange={(e) => setTo(Number(e.target.value))}>
              {items.map((s) => <option key={s.version} value={s.version}>v{s.version}</option>)}
            </Select>
          </div>
          {diff.isLoading ? <LoadingBlock rows={2} /> : diff.data ? (
            <>
              {diff.data.changes.length ? (
                <ul className="space-y-1.5 text-sm">{diff.data.changes.map((c, i) => <li key={i} className="flex gap-2"><Badge tone="iris">{String(c.kind).split("_")[0]}</Badge><span className="text-fg-muted">{describe(c)}</span></li>)}</ul>
              ) : <p className="text-sm text-fg-muted">No recorded differences.</p>}
              {diff.data.feature_changes.length > 0 && (
                <div>
                  <p className="eyebrow mb-2">Model input changes</p>
                  <ul className="grid gap-1.5 text-sm sm:grid-cols-2">
                    {diff.data.feature_changes.map((f) => (
                      <li key={f.feature} className="metric flex justify-between rounded-md bg-ink-800/60 px-2.5 py-1.5 text-xs">
                        <span className="text-fg-muted">{f.feature}</span>
                        <span>{f.before ?? "∅"} → <span className="text-aurora">{f.after ?? "∅"}</span></span>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </>
          ) : null}
        </CardBody>
      </Card>
    </div>
  );
}
