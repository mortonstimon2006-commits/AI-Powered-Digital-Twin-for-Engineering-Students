import { useMutation, useQuery } from "@tanstack/react-query";
import { ArrowRight, FlaskConical, GitCompareArrows, RotateCcw, Save, Trash2 } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Slider, Switch } from "@/components/ui/form";
import { ConfirmButton, Dialog } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice, SyntheticModelNotice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { useProfile, useRoles, useSkills } from "@/lib/queries";
import { BAND_META, cn, dateTime, level, pct } from "@/lib/utils";

interface ReadinessSide { available: boolean; band?: string; band_label?: string; probability?: { value: number } | null; reason?: string; model_version?: string; is_synthetic_model?: boolean }
interface SimRole {
  role_id: number; role_name: string; role_version: number;
  baseline: { match: number; match_upper: number; gap_count: number; unknown_count: number };
  hypothetical: { match: number; match_upper: number; gap_count: number; unknown_count: number };
  delta_match: number;
  changed_skills: { skill: string; before_level: number | null; after_level: number | null; before_action: string; after_action: string; required_level: number }[];
  top_remaining_gaps: { skill: string; action: string; gap: number | null }[];
}
interface SimResult {
  hypothetical: true;
  changes_applied: Record<string, unknown>[];
  plausibility_notes: string[];
  feature_changes: { feature: string; label: string; before: number | null; after: number | null }[];
  readiness: { baseline: ReadinessSide; hypothetical: ReadinessSide };
  roles: SimRole[];
  limitations: string[];
}
interface Scenario { id: string; name: string; created_at: string; changes: { changes: Changes; role_ids: number[] }; result: SimResult }
interface Changes {
  skill_levels: { skill_id: number; level: number; basis: "assessed" | "project_evidence" }[];
  add_projects: number; add_deployed_projects: number; add_internship_months: number;
  add_verified_certifications: number; add_hackathons: number;
  assessments: { kind: "coding" | "communication" | "mock_interview"; pct: number }[];
  cgpa: number | null; semester: number | null;
}

const EMPTY: Changes = { skill_levels: [], add_projects: 0, add_deployed_projects: 0, add_internship_months: 0, add_verified_certifications: 0,
  add_hackathons: 0, assessments: [], cgpa: null, semester: null };

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => {
    const t = setTimeout(() => setV(value), ms);
    return () => clearTimeout(t);
  }, [value, ms]);
  return v;
}

function isEmpty(c: Changes): boolean {
  return JSON.stringify(c) === JSON.stringify(EMPTY);
}

function ReadinessCompare({ r }: { r: SimResult["readiness"] }) {
  const side = (s: ReadinessSide, label: string) => (
    <div className="flex-1 rounded-xl border border-line bg-ink-800/50 p-4">
      <p className="eyebrow">{label}</p>
      {s.available ? (
        <>
          <p className="mt-1 font-semibold" style={{ color: BAND_META[s.band ?? ""]?.color }}>{s.band_label}</p>
          <p className="metric text-sm text-fg-muted">{s.probability ? `≈ ${pct(s.probability.value)}` : "band only"}</p>
        </>
      ) : <p className="mt-1 text-sm text-fg-muted">Model unavailable</p>}
    </div>
  );
  return (
    <div className="flex items-stretch gap-3">
      {side(r.baseline, "Your twin today")}
      <div className="grid place-items-center"><ArrowRight className="size-5 text-aurora" /></div>
      {side(r.hypothetical, "Hypothetical")}
    </div>
  );
}

function Stepper({ label, value, onChange, max }: { label: string; value: number; onChange: (v: number) => void; max: number }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <span className="text-sm text-fg-muted">{label}</span>
      <div className="flex items-center gap-1">
        <Button variant="secondary" size="icon" aria-label={`Decrease ${label}`} disabled={value <= 0} onClick={() => onChange(value - 1)}>−</Button>
        <span className="metric w-8 text-center" aria-live="polite">{value}</span>
        <Button variant="secondary" size="icon" aria-label={`Increase ${label}`} disabled={value >= max} onClick={() => onChange(value + 1)}>+</Button>
      </div>
    </div>
  );
}

export function SimulatorPage() {
  const profile = useProfile();
  const roles = useRoles();
  const skills = useSkills();
  const [changes, setChanges] = useState<Changes>(EMPTY);
  const [pickedRoleIds, setRoleIds] = useState<number[] | null>(null);
  const [saveOpen, setSaveOpen] = useState(false);
  const [name, setName] = useState("");
  const [compare, setCompare] = useState<string[]>([]);
  const scenarios = useQuery({ queryKey: ["scenarios"], queryFn: () => api<{ items: Scenario[] }>("/simulations/scenarios") });
  const defaultRoleIds = useMemo(() => {
    const p = profile.data;
    if (!p) return [];
    return Array.from(new Set([p.target_role_id, ...p.preferred_role_ids].filter((x): x is number => Boolean(x)))).slice(0, 3);
  }, [profile.data]);
  const roleIds = pickedRoleIds ?? defaultRoleIds;
  const request = useMemo(() => ({ changes, role_ids: roleIds }), [changes, roleIds]);
  const debounced = useDebounced(request, 600);
  const sim = useQuery({
    queryKey: ["simulation", debounced],
    queryFn: () => api<SimResult>("/simulations/run", { method: "POST", body: debounced }),
    enabled: !isEmpty(debounced.changes),
    placeholderData: (prev) => prev,
    retry: false,
  });
  const save = useMutation({
    mutationFn: () => api("/simulations/scenarios", { method: "POST", body: { name, request } }),
    onSuccess: () => { toast.success("Scenario saved."); setSaveOpen(false); setName(""); void scenarios.refetch(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not save."),
  });

  const targetRole = roles.data?.roles.find((r) => r.id === profile.data?.target_role_id);
  const skillMap = new Map((skills.data?.items ?? []).map((s) => [s.skill_id, s]));
  const relevantSkills = (targetRole?.requirements ?? []).map((q) => skillMap.get(q.skill_id)).filter(Boolean) as NonNullable<ReturnType<typeof skillMap.get>>[];
  const setSkill = (id: number, lvl: number | null, basis: "assessed" | "project_evidence" = "assessed") =>
    setChanges((c) => ({ ...c, skill_levels: lvl === null ? c.skill_levels.filter((s) => s.skill_id !== id)
      : [...c.skill_levels.filter((s) => s.skill_id !== id), { skill_id: id, level: lvl, basis }] }));
  const setAssessment = (kind: Changes["assessments"][number]["kind"], v: number | null) =>
    setChanges((c) => ({ ...c, assessments: v === null ? c.assessments.filter((a) => a.kind !== kind) : [...c.assessments.filter((a) => a.kind !== kind), { kind, pct: v }] }));

  if (profile.isLoading || roles.isLoading || skills.isLoading) return <LoadingBlock rows={5} />;
  const result = sim.data;
  const compared = (scenarios.data?.items ?? []).filter((s) => compare.includes(s.id));

  return (
    <div>
      <PageHeader icon={FlaskConical} eyebrow="What-if simulator" title="Explore hypothetical changes safely"
        description="Changes apply to an isolated copy of your twin. The same model and framework are re-run; nothing is saved to your profile."
        actions={<>
          <Button variant="ghost" onClick={() => setChanges(EMPTY)} disabled={isEmpty(changes)}><RotateCcw className="size-4" /> Reset</Button>
          <Button variant="secondary" onClick={() => setSaveOpen(true)} disabled={isEmpty(changes)}><Save className="size-4" /> Save scenario</Button>
        </>} />

      <div className="grid gap-5 xl:grid-cols-[minmax(340px,0.9fr)_1.3fr]">
        <Card className="h-fit xl:sticky xl:top-6">
          <CardHeader title="Hypothetical inputs" description={targetRole ? `Skill controls show ${targetRole.name} requirements.` : "Choose a target role to see role skills."} />
          <CardBody className="space-y-6">
            <section aria-labelledby="sim-skills" className="space-y-3">
              <p id="sim-skills" className="eyebrow">Skill levels (as if verified)</p>
              {relevantSkills.slice(0, 12).map((s) => {
                const ch = changes.skill_levels.find((x) => x.skill_id === s.skill_id);
                const val = ch?.level ?? s.estimated_level ?? 0;
                return (
                  <div key={s.skill_id}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className={cn(ch ? "text-fg" : "text-fg-muted")}>{s.name}</span>
                      <span className="metric text-xs">{level(s.estimated_level)} {ch && <><ArrowRight className="inline size-3" /> <span className="text-aurora">{ch.level}</span></>}</span>
                    </div>
                    <div className="flex items-center gap-2">
                      <Slider value={val} min={0} max={4} step={0.5} label={`${s.name} hypothetical level`} onChange={(v) => setSkill(s.skill_id, v, ch?.basis)} />
                      {ch && <Button variant="ghost" size="icon" aria-label={`Undo ${s.name}`} onClick={() => setSkill(s.skill_id, null)}><RotateCcw className="size-3.5" /></Button>}
                    </div>
                  </div>
                );
              })}
            </section>
            <section className="space-y-3" aria-label="Practical evidence">
              <p className="eyebrow">Practical evidence</p>
              <Stepper label="New projects" value={changes.add_projects} max={10} onChange={(v) => setChanges((c) => ({ ...c, add_projects: v, add_deployed_projects: Math.min(c.add_deployed_projects, v) }))} />
              <Stepper label="…of which deployed" value={changes.add_deployed_projects} max={changes.add_projects} onChange={(v) => setChanges((c) => ({ ...c, add_deployed_projects: v }))} />
              <Stepper label="Verified certifications" value={changes.add_verified_certifications} max={10} onChange={(v) => setChanges((c) => ({ ...c, add_verified_certifications: v }))} />
              <Stepper label="Hackathons" value={changes.add_hackathons} max={10} onChange={(v) => setChanges((c) => ({ ...c, add_hackathons: v }))} />
              <div>
                <div className="mb-1 flex justify-between text-sm"><span className="text-fg-muted">Internship months</span><span className="metric text-aurora">+{changes.add_internship_months}</span></div>
                <Slider value={changes.add_internship_months} min={0} max={24} label="Additional internship months" onChange={(v) => setChanges((c) => ({ ...c, add_internship_months: v }))} />
              </div>
            </section>
            <section className="space-y-3" aria-label="Assessments">
              <p className="eyebrow">Verified assessment scores</p>
              {(["coding", "communication", "mock_interview"] as const).map((k) => {
                const a = changes.assessments.find((x) => x.kind === k);
                return (
                  <div key={k}>
                    <div className="mb-1 flex items-center justify-between text-sm">
                      <span className="capitalize text-fg-muted">{k.replace("_", " ")}</span>
                      <div className="flex items-center gap-2">{a && <span className="metric text-aurora">{a.pct}%</span>}<Switch label={`Simulate ${k} assessment`} checked={Boolean(a)} onCheckedChange={(on) => setAssessment(k, on ? 70 : null)} /></div>
                    </div>
                    {a && <Slider value={a.pct} min={0} max={100} step={5} label={`${k} score`} onChange={(v) => setAssessment(k, v)} />}
                  </div>
                );
              })}
            </section>
            <section className="space-y-3" aria-label="Roles to compare">
              <p className="eyebrow">Compare roles (up to 4)</p>
              <div className="flex flex-wrap gap-2">
                {roles.data?.roles.map((r) => {
                  const on = roleIds.includes(r.id);
                  return (
                    <button key={r.id} type="button" aria-pressed={on} onClick={() => setRoleIds(on ? roleIds.filter((x) => x !== r.id) : roleIds.length < 4 ? [...roleIds, r.id] : roleIds)}
                      className={cn("rounded-full border px-2.5 py-1 text-xs transition", on ? "border-aurora/60 bg-aurora/10 text-aurora" : "border-line text-fg-muted hover:text-fg")}>{r.name}</button>
                  );
                })}
              </div>
            </section>
          </CardBody>
        </Card>

        <div className="space-y-5">
          <div className="relative overflow-hidden rounded-xl border border-iris/30 bg-iris/[0.06] px-4 py-2 text-sm text-iris">
            <span className="font-semibold">HYPOTHETICAL</span> — results describe what the current model and framework compute for these inputs, not guaranteed outcomes.
          </div>
          {isEmpty(changes) ? (
            <EmptyState icon={<FlaskConical className="size-5" />} title="Adjust an input to start">Move a slider or add projects on the left. Results update as you change inputs.</EmptyState>
          ) : sim.error ? <ErrorState error={sim.error} onRetry={() => sim.refetch()} /> : !result ? <LoadingBlock rows={3} /> : (
            <AnimatePresence mode="popLayout">
              <motion.div key="res" initial={{ opacity: 0 }} animate={{ opacity: sim.isFetching ? 0.6 : 1 }} className="space-y-5">
                {result.readiness.hypothetical.is_synthetic_model && <SyntheticModelNotice compact />}
                <Card>
                  <CardHeader title="Readiness estimate" description={`Model ${result.readiness.baseline.model_version ?? "unavailable"} on both sides.`} />
                  <CardBody><ReadinessCompare r={result.readiness} /></CardBody>
                </Card>
                <Card>
                  <CardHeader title="Role match: today vs hypothetical" />
                  <CardBody>
                    <div className="h-64">
                      <ResponsiveContainer>
                        <BarChart data={result.roles.map((r) => ({ name: r.role_name, today: Math.round(r.baseline.match * 100), hypothetical: Math.round(r.hypothetical.match * 100) }))}>
                          <CartesianGrid stroke="#1a2338" vertical={false} />
                          <XAxis dataKey="name" tick={{ fill: "#a3b0c6", fontSize: 11 }} />
                          <YAxis unit="%" domain={[0, 100]} tick={{ fill: "#6f7d96", fontSize: 11 }} />
                          <Tooltip contentStyle={{ background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" }} />
                          <Legend wrapperStyle={{ fontSize: 12, color: "#a3b0c6" }} />
                          <Bar dataKey="today" name="Today" fill="#4b5d80" radius={[4, 4, 0, 0]} />
                          <Bar dataKey="hypothetical" name="Hypothetical" fill="#5eead4" radius={[4, 4, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                    <div className="mt-4 grid gap-4 md:grid-cols-2">
                      {result.roles.map((r) => (
                        <div key={r.role_id} className="rounded-lg border border-line p-3 text-sm">
                          <p className="font-medium">{r.role_name} <Badge tone={r.delta_match > 0 ? "ok" : "muted"}>{r.delta_match >= 0 ? "+" : ""}{(r.delta_match * 100).toFixed(1)} pts</Badge></p>
                          {r.changed_skills.length > 0 && <ul className="mt-2 space-y-1 text-xs text-fg-muted">{r.changed_skills.map((c) => <li key={c.skill}>{c.skill}: {level(c.before_level)} → <span className="text-aurora">{level(c.after_level)}</span> (req {c.required_level}) · {c.before_action} → {c.after_action}</li>)}</ul>}
                          {r.top_remaining_gaps.length > 0 && <p className="mt-2 text-xs text-fg-faint">Still open: {r.top_remaining_gaps.map((g) => g.skill).join(", ")}</p>}
                        </div>
                      ))}
                    </div>
                  </CardBody>
                </Card>
                <div className="grid gap-5 lg:grid-cols-2">
                  <Card>
                    <CardHeader title="Model inputs that changed" />
                    <CardBody>
                      <ul className="space-y-1.5 text-sm">
                        {result.feature_changes.map((f) => <li key={f.feature} className="flex justify-between"><span className="text-fg-muted">{f.label}</span><span className="metric">{f.before ?? "unknown"} → <span className="text-aurora">{f.after ?? "unknown"}</span></span></li>)}
                      </ul>
                    </CardBody>
                  </Card>
                  <Card>
                    <CardHeader title="Plausibility and limitations" />
                    <CardBody className="space-y-2">
                      {result.plausibility_notes.map((n) => <Notice key={n} tone="warn">{n}</Notice>)}
                      {result.limitations.map((n) => <p key={n} className="text-xs text-fg-muted">• {n}</p>)}
                    </CardBody>
                  </Card>
                </div>
              </motion.div>
            </AnimatePresence>
          )}

          <Card>
            <CardHeader title="Saved scenarios" description="Select two to compare them side by side."
              actions={compare.length === 2 ? <Badge tone="aurora"><GitCompareArrows className="size-3" /> comparing 2</Badge> : undefined} />
            <CardBody>
              {scenarios.data?.items.length ? (
                <ul className="divide-y divide-line">
                  {scenarios.data.items.map((s) => (
                    <li key={s.id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                      <input type="checkbox" className="size-4 accent-[#5eead4]" aria-label={`Compare ${s.name}`} checked={compare.includes(s.id)}
                        onChange={(e) => setCompare((c) => (e.target.checked ? [...c, s.id].slice(-2) : c.filter((x) => x !== s.id)))} />
                      <span className="flex-1 font-medium">{s.name}</span>
                      <span className="text-xs text-fg-faint">{dateTime(s.created_at)}</span>
                      <Button size="sm" variant="ghost" onClick={() => { setChanges({ ...EMPTY, ...s.changes.changes }); setRoleIds(s.changes.role_ids); toast.message(`Loaded "${s.name}".`); }}>Load</Button>
                      <ConfirmButton trigger={<Button size="icon" variant="ghost" aria-label={`Delete ${s.name}`}><Trash2 className="size-4" /></Button>} title="Delete scenario?" description="This removes the saved scenario only." confirmLabel="Delete"
                        onConfirm={async () => { await api(`/simulations/scenarios/${s.id}`, { method: "DELETE" }); await scenarios.refetch(); }} />
                    </li>
                  ))}
                </ul>
              ) : <p className="text-sm text-fg-muted">No saved scenarios yet.</p>}
              {compared.length === 2 && (
                <div className="mt-4 overflow-x-auto">
                  <table className="w-full text-sm">
                    <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Outcome</th>{compared.map((s) => <th key={s.id} className="pb-2">{s.name}</th>)}</tr></thead>
                    <tbody className="divide-y divide-line">
                      <tr><td className="py-2 text-fg-muted">Readiness (hypothetical)</td>{compared.map((s) => <td key={s.id}>{s.result.readiness.hypothetical.band_label ?? "—"} {s.result.readiness.hypothetical.probability ? `≈ ${pct(s.result.readiness.hypothetical.probability.value)}` : ""}</td>)}</tr>
                      {compared[0]!.result.roles.map((r) => (
                        <tr key={r.role_id}><td className="py-2 text-fg-muted">{r.role_name} match</td>{compared.map((s) => { const x = s.result.roles.find((y) => y.role_id === r.role_id); return <td key={s.id} className="metric">{x ? pct(x.hypothetical.match) : "—"}</td>; })}</tr>
                      ))}
                    </tbody>
                  </table>
                  <p className="mt-2 text-xs text-fg-faint">Saved results reflect the model and framework versions at save time.</p>
                </div>
              )}
            </CardBody>
          </Card>
        </div>
      </div>

      <Dialog open={saveOpen} onOpenChange={setSaveOpen} title="Save scenario" description="Saves the inputs and computed result. Your real profile is not changed.">
        <div className="space-y-4">
          <Field label="Scenario name">{({ id }) => <Input id={id} value={name} maxLength={80} onChange={(e) => setName(e.target.value)} placeholder="e.g. SQL to level 3 + one deployed project" />}</Field>
          <div className="flex justify-end gap-2"><Button variant="secondary" onClick={() => setSaveOpen(false)}>Cancel</Button><Button onClick={() => save.mutate()} loading={save.isPending} disabled={!name.trim()}>Save</Button></div>
        </div>
      </Dialog>
    </div>
  );
}
