import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, Bot, ChartSpline, Gauge, LayoutDashboard, RefreshCw, Route, Target } from "lucide-react";
import { Link } from "react-router";
import { toast } from "sonner";

import { Ring } from "@/components/charts/Ring";
import { PageHeader } from "@/components/layout/AppShell";
import { Stagger, StaggerItem } from "@/components/motion";
import { TwinVisual, useTwinAxes } from "@/components/twin/TwinVisual";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardBody, CardHeader, InfoHint, Meter, Stat } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice, Skeleton, SyntheticModelNotice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, qk, queryClient, useCompleteness, useFeatures, useLatestReadiness, useMe, useMentorStatus, useProfile, useRoadmap, useRoleGaps } from "@/lib/queries";
import type { Roadmap } from "@/lib/types";
import { ACTION_META, BAND_META, pct, relative } from "@/lib/utils";

function ReadinessCard() {
  const latest = useLatestReadiness();
  const run = useMutation({
    mutationFn: () => api<{ available: boolean; message?: string }>("/readiness/analyse", { method: "POST" }),
    onSuccess: (r) => {
      if (!r.available) toast.warning(r.message ?? "The readiness model is unavailable.");
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      void invalidateTwin();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Analysis failed."),
  });
  if (latest.isLoading) return <Skeleton className="h-64" />;
  if (latest.error) return <ErrorState error={latest.error} onRetry={() => latest.refetch()} />;
  const d = latest.data!;
  const band = d.band ? BAND_META[d.band] : null;
  return (
    <Card className="flex h-full flex-col">
      <CardHeader eyebrow="Readiness estimate" title="Interview readiness" description="Assessor-judgement model — not a hiring prediction."
        actions={<Button size="sm" variant="secondary" onClick={() => run.mutate()} loading={run.isPending}><RefreshCw className="size-3.5" />{d.exists ? "Re-run" : "Run"}</Button>} />
      <CardBody className="flex flex-1 flex-col gap-4">
        {!d.model.available && !d.exists && (
          <Notice tone="warn" title="Model unavailable">No readiness model is active, so no estimate is shown. Other features work normally.</Notice>
        )}
        {d.exists ? (
          <>
            <div className="flex items-end gap-4">
              <div>
                <p className="text-xl font-semibold" style={{ color: band?.color }}>{band?.label ?? d.band}</p>
                <p className="metric mt-1 text-sm text-fg-muted">
                  {d.probability !== null && d.probability !== undefined ? `≈ ${pct(d.probability)} (calibrated, rounded to 5%)` : "Band only — calibration not validated"}
                </p>
              </div>
            </div>
            {d.stale && <Notice tone="info">Your profile or the model changed since this estimate. Re-run to update it.</Notice>}
            {d.is_synthetic_model && <SyntheticModelNotice compact />}
            <p className="mt-auto font-mono text-[0.68rem] text-fg-faint">model {d.model_version} · twin v{d.snapshot_version} · {d.created_at && relative(d.created_at)}</p>
            <Button asChild variant="ghost" size="sm" className="self-start"><Link to="/app/readiness">Explanation <ArrowRight className="size-3.5" /></Link></Button>
          </>
        ) : (
          d.model.available && <EmptyState icon={<Gauge className="size-5" />} title="No estimate yet">Run the analysis to see an explained estimate.</EmptyState>
        )}
      </CardBody>
    </Card>
  );
}

function RecentChanges() {
  const snaps = useQuery({
    queryKey: qk.snapshots,
    queryFn: () => api<{ items: { version: number; reason: string; created_at: string }[] }>("/twin/snapshots", { query: { limit: 6 } }),
  });
  if (snaps.isLoading) return <LoadingBlock rows={2} />;
  const items = snaps.data?.items ?? [];
  if (!items.length) return <p className="text-sm text-fg-muted">No changes recorded yet.</p>;
  return (
    <ol className="space-y-3">
      {items.map((s) => (
        <li key={s.version} className="flex items-center gap-3 text-sm">
          <span className="metric grid size-7 shrink-0 place-items-center rounded-full border border-line text-[0.7rem] text-fg-muted">v{s.version}</span>
          <span className="flex-1 truncate capitalize text-fg-muted">{s.reason.replaceAll("_", " ")}</span>
          <span className="text-xs text-fg-faint">{relative(s.created_at)}</span>
        </li>
      ))}
    </ol>
  );
}

export function DashboardPage() {
  const me = useMe();
  const profile = useProfile();
  const completeness = useCompleteness();
  const features = useFeatures();
  const gaps = useRoleGaps(profile.data?.target_role_id);
  const roadmap = useRoadmap();
  const mentor = useMentorStatus();
  const axes = useTwinAxes(features.data?.features, gaps.data?.gaps);
  const rm = roadmap.data && "id" in roadmap.data ? (roadmap.data as Roadmap) : null;
  const nextActions = (gaps.data?.gaps ?? []).filter((g) => g.action !== "maintain").slice(0, 5);
  const firstName = me.data?.user.display_name.split(" ")[0];

  return (
    <div>
      <PageHeader icon={LayoutDashboard} eyebrow="Dashboard" title={`Welcome back${firstName ? `, ${firstName}` : ""}`}
        description="A live summary of your digital twin. Everything here is computed from your recorded profile."
        actions={<><Button asChild variant="secondary"><Link to="/app/simulator">Try a what-if</Link></Button><Button asChild><Link to="/app/mentor"><Bot className="size-4" /> Ask your Personalized Mentor</Link></Button></>} />

      <Stagger className="grid gap-5 lg:grid-cols-12">
        <StaggerItem className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader eyebrow="Your twin" title="Skill profile by category"
              description={gaps.data ? `Compared with ${gaps.data.role_name} (framework v${gaps.data.role_version}).` : "Choose a target role to compare against."}
              actions={<Button asChild size="sm" variant="ghost"><Link to="/app/profile">Edit twin</Link></Button>} />
            <CardBody>{features.isLoading ? <Skeleton className="h-80" /> : <TwinVisual axes={axes} />}</CardBody>
          </Card>
        </StaggerItem>

        <StaggerItem className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader eyebrow="Profile completeness" title="How complete is your twin?" description="More evidence means more trustworthy analysis." />
            <CardBody>
              {completeness.isLoading ? <LoadingBlock rows={3} /> : completeness.error ? <ErrorState error={completeness.error} /> : (
                <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
                  <Ring value={completeness.data!.overall} label="Profile completeness">
                    <div><p className="metric text-2xl font-semibold">{pct(completeness.data!.overall)}</p><p className="text-[0.65rem] text-fg-faint">complete</p></div>
                  </Ring>
                  <ul className="flex-1 space-y-2.5">
                    {completeness.data!.sections.map((s) => (
                      <li key={s.key}>
                        <div className="mb-1 flex items-center justify-between text-xs">
                          <span className="flex items-center gap-1.5 text-fg-muted">{s.label}{s.hint && <InfoHint content={s.hint} />}</span>
                          <span className="metric text-fg-faint">{pct(s.score)}</span>
                        </div>
                        <Meter value={s.score} tone={s.complete ? "ok" : "aurora"} label={`${s.label} completeness`} />
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </CardBody>
          </Card>
        </StaggerItem>

        <StaggerItem className="lg:col-span-4"><ReadinessCard /></StaggerItem>

        <StaggerItem className="lg:col-span-4">
          <Card className="h-full">
            <CardHeader eyebrow="Target role" title={gaps.data?.role_name ?? "No target role"} description="Profile-to-framework match, not a hiring probability."
              actions={<Button asChild size="sm" variant="ghost"><Link to="/app/gaps"><Target className="size-3.5" /> Gaps</Link></Button>} />
            <CardBody>
              {gaps.isLoading ? <LoadingBlock rows={2} /> : gaps.data ? (
                <div className="space-y-4">
                  <div className="grid grid-cols-2 gap-4">
                    <Stat label="Demonstrated" value={pct(gaps.data.match)} hint="Importance-weighted share of requirements you currently meet. Unknown skills count as not demonstrated." />
                    <Stat label="Upper bound" value={pct(gaps.data.match_upper)} hint="The match if every unknown skill turned out to meet its requirement. The gap between the two numbers is what you haven't measured yet." />
                  </div>
                  <div className="relative h-3 overflow-hidden rounded-full bg-white/[0.06]" aria-hidden>
                    <div className="absolute inset-y-0 left-0 rounded-full bg-white/10" style={{ width: pct(gaps.data.match_upper) }} />
                    <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-aurora to-iris" style={{ width: pct(gaps.data.match) }} />
                  </div>
                  <div className="flex flex-wrap gap-2 text-xs">
                    <Badge tone="ok">{gaps.data.met_count} met</Badge><Badge tone="danger">{gaps.data.gap_count} gaps</Badge><Badge tone="muted">{gaps.data.unknown_count} unknown</Badge>
                  </div>
                </div>
              ) : <EmptyState title="Pick a target role" action={<Button asChild size="sm"><Link to="/app/roles">Explore roles</Link></Button>} />}
            </CardBody>
          </Card>
        </StaggerItem>

        <StaggerItem className="lg:col-span-4">
          <Card className="h-full">
            <CardHeader eyebrow="Roadmap" title="Learning plan" actions={<Button asChild size="sm" variant="ghost"><Link to="/app/roadmap"><Route className="size-3.5" /> Open</Link></Button>} />
            <CardBody>
              {roadmap.isLoading ? <LoadingBlock rows={2} /> : rm ? (
                <div className="space-y-4">
                  <Stat label="Progress" value={`${rm.progress.completed}/${rm.progress.total}`} sub={`${rm.params.weeks as number} weeks at ${rm.hours_per_week} h/week`} />
                  <Meter value={rm.progress.share} label="Roadmap completion" />
                  {rm.stale && <Notice tone="info">Your profile changed — regenerate the roadmap to adapt it.</Notice>}
                  <p className="text-sm text-fg-muted">Next: <span className="text-fg">{rm.items.find((i) => i.status !== "completed" && i.status !== "skipped")?.skill_name ?? "all done"}</span></p>
                </div>
              ) : <EmptyState icon={<Route className="size-5" />} title="No roadmap yet" action={<Button asChild size="sm"><Link to="/app/roadmap">Generate a roadmap</Link></Button>} />}
            </CardBody>
          </Card>
        </StaggerItem>

        <StaggerItem className="lg:col-span-7">
          <Card className="h-full">
            <CardHeader eyebrow="Next actions" title="Highest-priority gaps" description="Ranked by the documented gap formula for your target role." />
            <CardBody>
              {gaps.isLoading ? <LoadingBlock rows={3} /> : nextActions.length ? (
                <ul className="divide-y divide-line">
                  {nextActions.map((g) => (
                    <li key={g.skill_id} className="flex items-start gap-3 py-3 first:pt-0 last:pb-0">
                      <Badge tone={ACTION_META[g.action]?.tone ?? "muted"}>{ACTION_META[g.action]?.label ?? g.action}</Badge>
                      <div className="min-w-0 flex-1">
                        <p className="text-sm font-medium">{g.skill_name}</p>
                        <p className="text-xs text-fg-muted">{g.action_text}</p>
                      </div>
                      <span className="metric text-xs text-fg-faint">{g.priority.toFixed(2)}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-fg-muted">No open gaps for the selected role.</p>}
            </CardBody>
          </Card>
        </StaggerItem>

        <StaggerItem className="lg:col-span-5">
          <Card className="h-full">
            <CardHeader eyebrow="History" title="Recent twin changes" actions={<Button asChild size="sm" variant="ghost"><Link to="/app/progress"><ChartSpline className="size-3.5" /> Progress</Link></Button>} />
            <CardBody>
              <RecentChanges />
              <div className="mt-5 flex items-center justify-between rounded-lg border border-line bg-ink-800/50 p-3">
                <div className="flex items-center gap-2 text-sm">
                  <Bot className="size-4 text-aurora" />
                  <span>{mentor.data?.available ? "Personalized Mentor is online" : "Personalized Mentor is offline"}</span>
                </div>
                <Button asChild size="sm" variant={mentor.data?.available ? "subtle" : "secondary"}><Link to="/app/mentor">Open</Link></Button>
              </div>
            </CardBody>
          </Card>
        </StaggerItem>
      </Stagger>
    </div>
  );
}
