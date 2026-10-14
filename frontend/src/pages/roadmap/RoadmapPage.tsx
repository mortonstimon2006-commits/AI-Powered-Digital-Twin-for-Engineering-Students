import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowDown, ArrowUp, CalendarRange, ExternalLink, ListOrdered, RefreshCw, Route, ThumbsDown, ThumbsUp } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader, Meter, Stat } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { qk, queryClient, useProfile, useRoadmap, useRoles } from "@/lib/queries";
import type { Roadmap, RoadmapComparison, RoadmapItem } from "@/lib/types";
import { ACTION_META, CATEGORY_COLOR, cn, dateTime, level } from "@/lib/utils";

const STATUS = [["not_started", "Not started"], ["in_progress", "In progress"], ["completed", "Completed"], ["skipped", "Skipped"]] as const;

function ItemCard({ item, index, total, onMove, editable }: { item: RoadmapItem; index: number; total: number; onMove: (dir: -1 | 1) => void; editable: boolean }) {
  const [open, setOpen] = useState(false);
  const [note, setNote] = useState(item.note);
  const update = useMutation({
    mutationFn: (body: { status?: string; note?: string }) => api<{ evidence_hint: string | null }>(`/roadmaps/items/${item.id}`, { method: "PATCH", body }),
    onSuccess: (r) => { if (r.evidence_hint) toast.info(r.evidence_hint); void queryClient.invalidateQueries({ queryKey: qk.roadmap }); void queryClient.invalidateQueries({ queryKey: qk.timeline }); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Update failed."),
  });
  async function feedback(rating: number) {
    try {
      await api("/feedback", { method: "POST", body: { target_type: "roadmap_item", target_id: item.id, rating } });
      toast.success("Thanks — feedback recorded.");
    } catch {
      toast.error("Could not send feedback.");
    }
  }
  const done = item.status === "completed";
  return (
    <motion.li layout className={cn("card overflow-hidden", done && "opacity-70")}>
      <div className="flex gap-4 p-4">
        <div className="flex flex-col items-center gap-1">
          <span className="metric grid size-8 place-items-center rounded-full border border-line text-xs" style={{ borderColor: CATEGORY_COLOR[item.category ?? ""] }}>{item.position}</span>
          {editable && (
            <>
              <Button variant="ghost" size="icon" className="size-7" aria-label={`Move ${item.skill_name} up`} disabled={index === 0} onClick={() => onMove(-1)}><ArrowUp className="size-3.5" /></Button>
              <Button variant="ghost" size="icon" className="size-7" aria-label={`Move ${item.skill_name} down`} disabled={index === total - 1} onClick={() => onMove(1)}><ArrowDown className="size-3.5" /></Button>
            </>
          )}
        </div>
        <div className="min-w-0 flex-1 space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <p className={cn("font-medium", done && "line-through")}>{item.skill_name}</p>
            <Badge tone={ACTION_META[item.action]?.tone ?? "muted"}>{ACTION_META[item.action]?.label ?? item.action}</Badge>
            <span className="metric text-xs text-fg-muted">{level(item.current_level)} → {item.target_level}</span>
            <span className="text-xs text-fg-faint">weeks {item.week_start}–{item.week_end} · {item.effort_hours[0]}–{item.effort_hours[1]} h est.</span>
            {item.user_edited && <Badge tone="iris">edited</Badge>}
          </div>
          <p className="text-sm text-fg-muted">{item.reason}</p>
          {item.prerequisites.length > 0 && <p className="text-xs text-fg-faint">After: {item.prerequisites.join(", ")}</p>}
          <div className="flex flex-wrap items-center gap-2">
            <Select aria-label={`Status of ${item.skill_name}`} className="h-8 w-40 text-xs" value={item.status} disabled={!editable || update.isPending}
              onChange={(e) => update.mutate({ status: e.target.value })}>
              {STATUS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </Select>
            <Button variant="ghost" size="sm" onClick={() => setOpen((o) => !o)} aria-expanded={open}>{open ? "Hide details" : "Details"}</Button>
            {item.resource && (
              <a href={item.resource.url} target="_blank" rel="noopener noreferrer nofollow" className="inline-flex items-center gap-1.5 text-sm text-aurora hover:underline">
                <ExternalLink className="size-3.5" />{item.resource.title}
              </a>
            )}
            {item.resource && item.resource.verification_status !== "verified" && <Badge tone="warn">link unverified</Badge>}
          </div>
          {open && (
            <div className="grid gap-4 rounded-lg bg-ink-800/50 p-3 text-sm md:grid-cols-2">
              <div><p className="eyebrow mb-1">Practical exercise</p><p className="text-fg-muted">{item.exercise || "—"}</p></div>
              <div><p className="eyebrow mb-1">Completion criteria</p><p className="text-fg-muted">{item.completion_criteria}</p></div>
              {item.resource && <p className="text-xs text-fg-faint md:col-span-2">Resource: {item.resource.provider} · {item.resource.cost} · {item.resource.est_hours[0]}–{item.resource.est_hours[1]} h (provider-independent estimate)</p>}
              {editable && (
                <div className="space-y-2 md:col-span-2">
                  <Field label="Your notes">{({ id }) => <Textarea id={id} className="min-h-16" value={note} maxLength={1000} onChange={(e) => setNote(e.target.value)} />}</Field>
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <div className="flex items-center gap-1 text-xs text-fg-faint">Was this recommendation useful?
                      <Button variant="ghost" size="icon" aria-label="Useful" onClick={() => feedback(5)}><ThumbsUp className="size-3.5" /></Button>
                      <Button variant="ghost" size="icon" aria-label="Not useful" onClick={() => feedback(1)}><ThumbsDown className="size-3.5" /></Button>
                    </div>
                    <Button size="sm" variant="secondary" disabled={note === item.note} loading={update.isPending} onClick={() => update.mutate({ note })}>Save note</Button>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </motion.li>
  );
}

function Comparison({ c }: { c: RoadmapComparison }) {
  return (
    <Card>
      <CardHeader title="What changed from your previous plan" />
      <CardBody className="grid gap-4 text-sm sm:grid-cols-4">
        <div><p className="eyebrow mb-1">Added</p>{c.added.length ? c.added.map((x) => <p key={x.skill + x.action}>{x.skill}</p>) : <p className="text-fg-faint">—</p>}</div>
        <div><p className="eyebrow mb-1">Removed</p>{c.removed.length ? c.removed.map((x) => <p key={x.skill + x.action}>{x.skill}</p>) : <p className="text-fg-faint">—</p>}</div>
        <div><p className="eyebrow mb-1">Reordered</p>{c.moved.length ? c.moved.map((x) => <p key={x.skill}>{x.skill} #{x.from}→#{x.to}</p>) : <p className="text-fg-faint">—</p>}</div>
        <div><p className="eyebrow mb-1">Progress kept</p>{c.carried_progress.length ? c.carried_progress.map((x) => <p key={x.skill}>{x.skill} ({x.status.replace("_", " ")})</p>) : <p className="text-fg-faint">—</p>}</div>
      </CardBody>
    </Card>
  );
}

export function RoadmapPage() {
  const roadmap = useRoadmap();
  const profile = useProfile();
  const roles = useRoles();
  const [view, setView] = useState<"list" | "weeks" | "months">("list");
  const [hours, setHours] = useState<string>("");
  const [roleId, setRoleId] = useState<string>("");
  const [comparison, setComparison] = useState<RoadmapComparison | null>(null);
  const [warnings, setWarnings] = useState<string[]>([]);
  const history = useQuery({ queryKey: qk.roadmaps, queryFn: () => api<{ items: { id: string; status: string; created_at: string; weeks: number; match_at_generation: number }[] }>("/roadmaps") });
  const generate = useMutation({
    mutationFn: () => api<Roadmap>("/roadmaps/generate", { method: "POST", body: { role_id: roleId ? Number(roleId) : null, hours_per_week: hours ? Number(hours) : null } }),
    onSuccess: (r) => { setComparison(r.comparison_with_previous ?? null); setWarnings([]); void queryClient.invalidateQueries({ queryKey: ["roadmap"] }); void history.refetch(); toast.success("Roadmap generated from your current gaps."); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Generation failed."),
  });
  const reorder = useMutation({
    mutationFn: ({ id, ids }: { id: string; ids: string[] }) => api<Roadmap>(`/roadmaps/${id}/order`, { method: "PUT", body: { item_ids: ids } }),
    onSuccess: (r) => { setWarnings(r.warnings ?? []); void queryClient.invalidateQueries({ queryKey: qk.roadmap }); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Reorder failed."),
  });

  if (roadmap.isLoading) return <LoadingBlock rows={4} />;
  if (roadmap.error) return <ErrorState error={roadmap.error} onRetry={() => roadmap.refetch()} />;
  const rm = roadmap.data && "id" in roadmap.data ? (roadmap.data as Roadmap) : null;
  const controls = (
    <div className="flex flex-wrap items-end gap-2">
      <Field label="Role" className="w-48">{({ id }) => (
        <Select id={id} className="h-9 text-xs" value={roleId || String(rm?.role_id ?? profile.data?.target_role_id ?? "")} onChange={(e) => setRoleId(e.target.value)}>
          {roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
        </Select>)}
      </Field>
      <Field label="Hours / week" className="w-28">{({ id }) => <Input id={id} className="h-9" type="number" min={1} max={80} placeholder={String(profile.data?.weekly_hours ?? 8)} value={hours} onChange={(e) => setHours(e.target.value)} />}</Field>
      <Button onClick={() => generate.mutate()} loading={generate.isPending}><RefreshCw className="size-4" /> {rm ? "Regenerate" : "Generate"}</Button>
    </div>
  );

  function move(index: number, dir: -1 | 1) {
    if (!rm) return;
    const ids = rm.items.map((i) => i.id);
    const j = index + dir;
    [ids[index], ids[j]] = [ids[j]!, ids[index]!];
    reorder.mutate({ id: rm.id, ids });
  }

  return (
    <div>
      <PageHeader icon={Route} eyebrow="Personalised roadmap" title={rm ? `Plan for ${rm.role_name}` : "Your learning roadmap"}
        description="Generated from your current skill gaps, ordered by prerequisites and scheduled around your weekly hours." actions={controls} />
      {!rm ? (
        <EmptyState icon={<Route className="size-5" />} title="No roadmap yet">Choose a role and weekly hours, then generate a plan. You can regenerate any time your profile changes.</EmptyState>
      ) : (
        <div className="space-y-5">
          {rm.stale && <Notice tone="info" title="This plan may be out of date">{rm.stale_reasons.join(" ")} Regenerate to adapt it; your progress on matching items is kept.</Notice>}
          {comparison && <Comparison c={comparison} />}
          {warnings.map((w) => <Notice key={w} tone="warn">{w}</Notice>)}
          <div className="grid gap-5 lg:grid-cols-4">
            <Card className="lg:col-span-3"><CardBody className="flex flex-wrap items-center gap-8 pt-5">
              <Stat label="Progress" value={`${rm.progress.completed}/${rm.progress.total}`} />
              <Stat label="Estimated span" value={`${rm.params.weeks as number} wk`} sub={`${rm.hours_per_week} h/week`} />
              <Stat label="Mid-point effort" value={`${rm.params.total_hours_mid as number} h`} hint="Sum of mid-points of each item's planning range." />
              <div className="min-w-48 flex-1"><Meter value={rm.progress.share} label="Roadmap completion" /></div>
            </CardBody></Card>
            <Card><CardBody className="flex h-full items-center justify-center gap-1 pt-5">
              {([["list", ListOrdered, "List"], ["weeks", CalendarRange, "Weeks"], ["months", CalendarRange, "Months"]] as const).map(([v, Icon, label]) => (
                <Button key={v} size="sm" variant={view === v ? "subtle" : "ghost"} onClick={() => setView(v)} aria-pressed={view === v}><Icon className="size-3.5" />{label}</Button>
              ))}
            </CardBody></Card>
          </div>
          <p className="text-xs text-fg-faint">{rm.disclaimer}</p>

          {view === "list" && (
            <ul className="space-y-3">{rm.items.map((it, i) => <ItemCard key={it.id} item={it} index={i} total={rm.items.length} onMove={(d) => move(i, d)} editable={rm.status === "active"} />)}</ul>
          )}
          {view === "weeks" && (
            <div className="space-y-2">
              {rm.weeks.map((w) => (
                <div key={w.week} className="flex gap-4">
                  <span className="metric w-16 shrink-0 pt-2 text-xs text-fg-faint">Week {w.week}</span>
                  <div className="flex flex-1 flex-wrap gap-2 border-l border-line pb-2 pl-4">
                    {w.item_ids.map((id) => { const it = rm.items.find((x) => x.id === id)!; return (
                      <span key={id} className={cn("rounded-lg border px-3 py-1.5 text-sm", it.status === "completed" ? "border-ok/30 text-ok" : "border-line")}>
                        {it.skill_name} <span className="text-xs text-fg-faint">({ACTION_META[it.action]?.label})</span>
                      </span>
                    ); })}
                  </div>
                </div>
              ))}
            </div>
          )}
          {view === "months" && (
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
              {rm.months.map((m) => {
                const ids = new Set(rm.weeks.filter((w) => m.weeks.includes(w.week)).flatMap((w) => w.item_ids));
                const items = rm.items.filter((i) => ids.has(i.id));
                return (
                  <Card key={m.month}>
                    <CardHeader title={`Month ${m.month}`} description={`Weeks ${m.weeks[0]}–${m.weeks[m.weeks.length - 1]}`} />
                    <CardBody><ul className="space-y-1.5 text-sm">{items.map((i) => <li key={i.id} className="flex items-center justify-between gap-2"><span>{i.skill_name}</span><Badge tone={i.status === "completed" ? "ok" : "muted"}>{i.status.replace("_", " ")}</Badge></li>)}</ul></CardBody>
                  </Card>
                );
              })}
            </div>
          )}
          {history.data && history.data.items.length > 1 && (
            <Card>
              <CardHeader title="Plan history" description="Archived plans are kept so you can see how your plan evolved." />
              <CardBody>
                <ul className="divide-y divide-line text-sm">
                  {history.data.items.map((h) => (
                    <li key={h.id} className="flex flex-wrap items-center gap-3 py-2">
                      <Badge tone={h.status === "active" ? "aurora" : "muted"}>{h.status}</Badge>
                      <span className="text-fg-muted">{dateTime(h.created_at)}</span>
                      <span className="metric text-xs text-fg-faint">{h.weeks} weeks · match at generation {Math.round((h.match_at_generation ?? 0) * 100)}%</span>
                      {h.status !== "active" && (
                        <Button size="sm" variant="ghost" className="ml-auto" onClick={async () => setComparison(await api<RoadmapComparison>(`/roadmaps/${rm.id}/compare/${h.id}`))}>Compare with current</Button>
                      )}
                    </li>
                  ))}
                </ul>
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
