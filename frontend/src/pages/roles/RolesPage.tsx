import { useMutation } from "@tanstack/react-query";
import { BarChart3, Compass, Crosshair, Plus, Star } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Stagger, StaggerItem } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Dialog } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, InfoHint } from "@/components/ui/primitives";
import { ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, useMatches, useProfile, useRoles } from "@/lib/queries";
import type { CareerRole } from "@/lib/types";
import { CATEGORY_COLOR, cn, LEVEL_NAMES, pct } from "@/lib/utils";

interface Sensitivity {
  samples: number;
  perturbation: number;
  top_role_stability: number;
  interpretation: string;
  roles: { role_id: number; role_name: string; base_rank: number; best_rank: number; worst_rank: number; p_top1: number; p_top3: number }[];
}

function RoleDetail({ role, open, onOpenChange }: { role: CareerRole; open: boolean; onOpenChange: (o: boolean) => void }) {
  const groups = new Map<string, string[]>();
  role.requirements.forEach((q) => q.alt_group && groups.set(q.alt_group, [...(groups.get(q.alt_group) ?? []), q.skill_name]));
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title={`${role.name} · v${role.version}`} description={role.summary}>
      <div className="space-y-4">
        <p className="text-sm text-fg-muted">{role.description}</p>
        <Notice tone="info" title="Provenance">{role.source_note}</Notice>
        {groups.size > 0 && <p className="text-sm text-fg-muted">Alternatives: {[...groups.values()].map((g) => `any one of ${g.join(" / ")}`).join("; ")}.</p>}
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Skill</th><th className="pb-2">Level</th><th className="pb-2">Importance</th><th className="pb-2">Type</th><th className="pb-2">Evidence</th><th className="pb-2">Why</th></tr></thead>
            <tbody className="divide-y divide-line">
              {role.requirements.map((q) => (
                <tr key={q.skill_id} className="align-top">
                  <td className="py-2 pr-3"><span className="mr-2 inline-block size-2 rounded-full" style={{ background: CATEGORY_COLOR[q.category] }} />{q.skill_name}</td>
                  <td className="metric py-2 pr-3">{q.required_level} · {LEVEL_NAMES[q.required_level]}</td>
                  <td className="metric py-2 pr-3">{q.importance.toFixed(1)}</td>
                  <td className="py-2 pr-3"><Badge tone={q.is_core ? "aurora" : "muted"}>{q.is_core ? "core" : "optional"}</Badge></td>
                  <td className="py-2 pr-3 text-fg-muted">{q.evidence_expected}</td>
                  <td className="py-2 text-xs text-fg-muted">{q.rationale}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </Dialog>
  );
}

export function RolesPage() {
  const roles = useRoles();
  const matches = useMatches();
  const profile = useProfile();
  const [detail, setDetail] = useState<CareerRole | null>(null);
  const sens = useMutation({ mutationFn: () => api<Sensitivity>("/skill-gaps/sensitivity", { query: { samples: 200 } }) });

  async function setTarget(roleId: number, mode: "target" | "preferred") {
    const p = profile.data!;
    const target = mode === "target" ? roleId : p.target_role_id;
    const preferred = mode === "preferred" ? Array.from(new Set([...p.preferred_role_ids.filter((r) => r !== p.target_role_id), roleId])).slice(0, 4)
      : p.preferred_role_ids.filter((r) => r !== roleId && r !== p.target_role_id);
    try {
      await api("/profile/roles", { method: "PUT", body: { target_role_id: target, preferred_role_ids: preferred } });
      await invalidateTwin();
      toast.success(mode === "target" ? "Target role updated." : "Added to preferred roles.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update roles.");
    }
  }

  if (roles.isLoading || matches.isLoading) return <LoadingBlock rows={5} />;
  if (roles.error || matches.error) return <ErrorState error={roles.error ?? matches.error} onRetry={() => { void roles.refetch(); void matches.refetch(); }} />;
  const byId = new Map(roles.data!.roles.map((r) => [r.id, r]));

  return (
    <div>
      <PageHeader icon={Compass} eyebrow="Role explorer" title="Career roles ranked against your twin" description={matches.data!.disclaimer}
        actions={<Button variant="secondary" onClick={() => sens.mutate()} loading={sens.isPending}><BarChart3 className="size-4" /> Test ranking stability</Button>} />
      <Notice tone="info" className="mb-5" title="About the framework">{roles.data!.framework_note}</Notice>

      {sens.data && (
        <Card className="mb-5">
          <CardHeader title="Ranking sensitivity" description={`${sens.data.samples} random perturbations of ±${sens.data.perturbation * 100}% to every importance weight. ${sens.data.interpretation}`} />
          <CardBody>
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Role</th><th className="pb-2">Rank</th><th className="pb-2">Range</th><th className="pb-2">P(top 1)</th><th className="pb-2">P(top 3)</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {sens.data.roles.map((r) => (
                    <tr key={r.role_id}><td className="py-2">{r.role_name}</td><td className="metric">#{r.base_rank}</td><td className="metric">#{r.best_rank}–#{r.worst_rank}</td><td className="metric">{pct(r.p_top1)}</td><td className="metric">{pct(r.p_top3)}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardBody>
        </Card>
      )}

      <Stagger className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {matches.data!.matches.map((m, idx) => {
          const role = byId.get(m.role_id)!;
          const isTarget = profile.data?.target_role_id === m.role_id;
          const isPreferred = profile.data?.preferred_role_ids.includes(m.role_id);
          return (
            <StaggerItem key={m.role_id}>
              <Card className={cn("flex h-full flex-col", isTarget && "border-aurora/40")}>
                <CardHeader eyebrow={`#${idx + 1} by demonstrated match`} title={m.role_name} description={role.summary}
                  actions={isTarget ? <Badge tone="aurora"><Crosshair className="size-3" /> Target</Badge> : isPreferred ? <Badge tone="iris"><Star className="size-3" /> Preferred</Badge> : undefined} />
                <CardBody className="flex flex-1 flex-col gap-4">
                  <div>
                    <div className="mb-1.5 flex items-baseline justify-between text-sm">
                      <span className="flex items-center gap-1.5 text-fg-muted">Match <InfoHint content="Solid bar: demonstrated. Faint bar: upper bound if all unknown skills were met." /></span>
                      <span className="metric">{pct(m.match)} <span className="text-fg-faint">/ ≤{pct(m.match_upper)}</span></span>
                    </div>
                    <div className="relative h-2.5 overflow-hidden rounded-full bg-white/[0.06]">
                      <div className="absolute inset-y-0 left-0 bg-white/10" style={{ width: pct(m.match_upper) }} />
                      <div className="absolute inset-y-0 left-0 rounded-full bg-gradient-to-r from-aurora to-iris" style={{ width: pct(m.match) }} />
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-1.5 text-xs"><Badge tone="ok">{m.met_count} met</Badge><Badge tone="danger">{m.gap_count} gaps</Badge><Badge tone="muted">{m.unknown_count} unknown</Badge></div>
                  {m.top_gaps.length > 0 && (
                    <ul className="space-y-1 text-xs text-fg-muted">{m.top_gaps.map((g) => <li key={g.skill}>• {g.skill} <span className="text-fg-faint">({g.action})</span></li>)}</ul>
                  )}
                  <div className="mt-auto flex flex-wrap gap-2">
                    <Button size="sm" variant="secondary" onClick={() => setDetail(role)}>Requirements</Button>
                    {!isTarget && <Button size="sm" variant="ghost" onClick={() => setTarget(m.role_id, "target")}><Crosshair className="size-3.5" /> Make target</Button>}
                    {!isTarget && !isPreferred && <Button size="sm" variant="ghost" onClick={() => setTarget(m.role_id, "preferred")}><Plus className="size-3.5" /> Prefer</Button>}
                  </div>
                </CardBody>
              </Card>
            </StaggerItem>
          );
        })}
      </Stagger>
      {detail && <RoleDetail role={detail} open onOpenChange={(o) => !o && setDetail(null)} />}
    </div>
  );
}
