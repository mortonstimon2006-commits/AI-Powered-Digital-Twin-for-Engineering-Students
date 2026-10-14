import { ArrowDownUp, ChevronDown, ExternalLink, RotateCcw, Sigma, Target } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Select, Slider } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader, InfoHint, LevelMeter, Stat, StatusBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { useProfile, useRoleGaps, useRoles } from "@/lib/queries";
import type { Gap } from "@/lib/types";
import { ACTION_META, CATEGORY_LABEL, cn, level, pct } from "@/lib/utils";

const DEFAULTS = { optional_weight: 0.5, unlock_bonus: 0.15, blocking_bonus: 0.2, unknown_gap_assumption: 0.5 };
const ACTION_COLOR: Record<string, string> = { learn: "#fb7185", prerequisite: "#fbbf24", assess: "#7dd3fc", verify: "#a78bfa", maintain: "#34d399" };

function GapRow({ g }: { g: Gap }) {
  const [open, setOpen] = useState(false);
  return (
    <>
      <tr className="cursor-pointer align-middle hover:bg-white/[0.02]" onClick={() => setOpen((o) => !o)}>
        <td className="py-3 pl-4 pr-3">
          <button type="button" className="flex items-center gap-2 text-left" aria-expanded={open}>
            <ChevronDown className={cn("size-4 text-fg-faint transition", open && "rotate-180")} />
            <span>
              <span className="block font-medium">{g.skill_name}</span>
              <span className="block text-xs text-fg-faint">{CATEGORY_LABEL[g.category]}{!g.is_core && " · optional"}{g.alternatives.length > 0 && ` · or ${g.alternatives.join("/")}`}</span>
            </span>
          </button>
        </td>
        <td className="px-3"><LevelMeter value={g.estimated_level} required={g.required_level} status={g.status} /></td>
        <td className="metric px-3 text-sm">{level(g.estimated_level)} / {g.required_level}</td>
        <td className="metric px-3 text-sm">{g.gap === null ? "?" : g.gap.toFixed(1)}</td>
        <td className="metric px-3 text-sm">{g.importance.toFixed(1)}</td>
        <td className="px-3"><Badge tone={ACTION_META[g.action]?.tone ?? "muted"}>{ACTION_META[g.action]?.label ?? g.action}</Badge></td>
        <td className="metric px-3 pr-4 text-right text-sm">{g.priority.toFixed(3)}</td>
      </tr>
      <AnimatePresence initial={false}>
        {open && (
          <tr>
            <td colSpan={7} className="p-0">
              <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
                <div className="grid gap-5 bg-ink-800/40 px-4 py-4 text-sm md:grid-cols-3">
                  <div className="space-y-2">
                    <p className="eyebrow">Recommended next action</p>
                    <p>{g.action_text}</p>
                    <p className="text-xs text-fg-muted">Why it matters: {g.rationale}</p>
                    <div className="flex flex-wrap items-center gap-2 text-xs"><span className="text-fg-faint">Evidence:</span><StatusBadge status={g.status} />
                      <Badge tone={g.evidence_met ? "ok" : "warn"}>expects {g.evidence_expected}{g.evidence_met ? " ✓" : ""}</Badge></div>
                  </div>
                  <div className="space-y-2">
                    <p className="eyebrow">Prerequisites</p>
                    {g.prerequisites.length ? g.prerequisites.map((p) => (
                      <p key={p.skill_id} className="flex items-center gap-2"><Badge tone={p.met ? "ok" : "warn"}>{p.met ? "met" : "unmet"}</Badge>{p.skill_name} ≥ {p.min_level} <span className="text-fg-faint">(you: {level(p.estimated_level)})</span></p>
                    )) : <p className="text-fg-muted">None defined.</p>}
                    <p className="text-xs text-fg-faint">Blocks {g.blocking_count} other gap skill(s) · needed by {g.unlock_count} other preferred role(s)</p>
                  </div>
                  <div className="space-y-2">
                    <p className="eyebrow">Resources from the catalogue</p>
                    {g.resources?.length ? g.resources.map((r) => (
                      <a key={r.id} href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="flex items-start gap-2 rounded-md p-1 hover:bg-white/[0.03]" onClick={(e) => e.stopPropagation()}>
                        <ExternalLink className="mt-0.5 size-3.5 shrink-0 text-aurora" />
                        <span><span className="block">{r.title}</span><span className="text-xs text-fg-faint">{r.provider} · {r.cost} · {r.est_hours?.[0]}–{r.est_hours?.[1]} h · link {r.verification_status}</span></span>
                      </a>
                    )) : <p className="text-fg-muted">No catalogued resource for this skill yet.</p>}
                  </div>
                </div>
              </motion.div>
            </td>
          </tr>
        )}
      </AnimatePresence>
    </>
  );
}

export function SkillGapsPage() {
  const profile = useProfile();
  const roles = useRoles();
  const [roleId, setRoleId] = useState<number | null>(null);
  const [cfg, setCfg] = useState(DEFAULTS);
  const [category, setCategory] = useState("");
  const [action, setAction] = useState("");
  const [sort, setSort] = useState<"priority" | "gap" | "importance" | "name">("priority");
  const activeRole = roleId ?? profile.data?.target_role_id ?? null;
  const gaps = useRoleGaps(activeRole, cfg);
  const rows = useMemo(() => {
    let list = gaps.data?.gaps ?? [];
    if (category) list = list.filter((g) => g.category === category);
    if (action) list = list.filter((g) => g.action === action);
    const sorted = [...list];
    if (sort === "gap") sorted.sort((a, b) => (b.gap ?? 99) - (a.gap ?? 99));
    if (sort === "importance") sorted.sort((a, b) => b.importance - a.importance);
    if (sort === "name") sorted.sort((a, b) => a.skill_name.localeCompare(b.skill_name));
    return sorted;
  }, [gaps.data, category, action, sort]);
  const chart = (gaps.data?.gaps ?? []).filter((g) => g.priority > 0).slice(0, 12).map((g) => ({ name: g.skill_name, priority: Number(g.priority.toFixed(3)), action: g.action })).reverse();

  return (
    <div>
      <PageHeader icon={Target} eyebrow="Skill-gap analysis" title="Where you stand against a role"
        description="A documented comparison between your evidence-weighted skill estimates and a versioned role specification."
        actions={
          <Select aria-label="Role to analyse" className="w-56" value={activeRole ?? ""} onChange={(e) => setRoleId(Number(e.target.value))}>
            <option value="" disabled>Choose a role</option>
            {roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name}</option>)}
          </Select>
        } />
      {!activeRole ? <EmptyState icon={<Target className="size-5" />} title="Choose a role to analyse" /> : gaps.isLoading && !gaps.data ? <LoadingBlock rows={5} /> : gaps.error ? <ErrorState error={gaps.error} onRetry={() => gaps.refetch()} /> : gaps.data && (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-[1fr_1.3fr]">
            <Card>
              <CardHeader title={`${gaps.data.role_name} · v${gaps.data.role_version}`} description={gaps.data.disclaimer} />
              <CardBody className="grid grid-cols-2 gap-5">
                <Stat label="Demonstrated match" value={pct(gaps.data.match)} hint="Σ weight × coverage / Σ weight, unknown counted as not demonstrated." />
                <Stat label="Upper bound" value={pct(gaps.data.match_upper)} hint="If every unknown skill met its requirement." />
                <Stat label="Known coverage" value={pct(gaps.data.known_share)} hint="Share of requirement weight where your level is known." />
                <Stat label="Evidence strength" value={gaps.data.evidence_strength === null ? "—" : pct(gaps.data.evidence_strength)} hint="Weighted trust of the sources behind known levels (assessed = 100%, self-reported = 40%)." />
              </CardBody>
            </Card>
            <Card>
              <CardHeader title="Priority ranking" description="Top gaps by the priority formula, coloured by recommended action." />
              <CardBody>
                <div className="h-72" role="img" aria-label="Bar chart of gap priority by skill">
                  <ResponsiveContainer>
                    <BarChart data={chart} layout="vertical" margin={{ left: 4, right: 16 }}>
                      <XAxis type="number" tick={{ fill: "#6f7d96", fontSize: 11 }} stroke="#233049" />
                      <YAxis type="category" dataKey="name" width={150} tick={{ fill: "#a3b0c6", fontSize: 11 }} stroke="#233049" />
                      <Tooltip cursor={{ fill: "rgb(255 255 255 / 0.03)" }} contentStyle={{ background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" }} />
                      <Bar dataKey="priority" radius={[3, 3, 3, 3]}>{chart.map((c) => <Cell key={c.name} fill={ACTION_COLOR[c.action] ?? "#a3b0c6"} />)}</Bar>
                    </BarChart>
                  </ResponsiveContainer>
                </div>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader title="How gap scores are calculated" description="All assumptions are adjustable. Changes re-rank the table live; nothing is saved."
              actions={<Button variant="ghost" size="sm" onClick={() => setCfg(DEFAULTS)}><RotateCcw className="size-3.5" /> Reset</Button>} />
            <CardBody className="grid gap-6 lg:grid-cols-[1.1fr_1fr]">
              <div className="space-y-3 text-sm text-fg-muted">
                <p className="flex items-center gap-2 font-mono text-xs text-fg"><Sigma className="size-4 text-aurora" /> priority = W × (gap / L) × (1 + β·U) × (1 + γ·B)</p>
                <ul className="space-y-1.5 text-xs">
                  <li><b className="text-fg">W</b> importance × (1 if core, else the optional weight)</li>
                  <li><b className="text-fg">gap / L</b> levels missing relative to the required level; for unknown skills the assumed value below</li>
                  <li><b className="text-fg">U</b> other preferred roles that also need this skill (β = unlock bonus)</li>
                  <li><b className="text-fg">B</b> other gap skills that depend on this one (γ = blocking bonus)</li>
                </ul>
                <p className="text-xs">Unknown skills are never treated as zero proficiency. They get an "assess" action so a real baseline can be recorded.</p>
              </div>
              <div className="grid gap-5 sm:grid-cols-2">
                {([["optional_weight", "Optional-skill weight"], ["unlock_bonus", "Unlock bonus β"], ["blocking_bonus", "Blocking bonus γ"], ["unknown_gap_assumption", "Assumed gap if unknown"]] as const).map(([key, label]) => (
                  <div key={key}>
                    <div className="mb-2 flex justify-between text-xs"><span className="text-fg-muted">{label}</span><span className="metric text-aurora">{cfg[key].toFixed(2)}</span></div>
                    <Slider value={cfg[key]} min={0} max={1} step={0.05} label={label} onChange={(v) => setCfg((c) => ({ ...c, [key]: v }))} />
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>

          <Card>
            <CardHeader title="Skill-by-skill breakdown" description="Select a row for prerequisites, evidence and catalogue resources."
              actions={
                <div className="flex flex-wrap gap-2">
                  <Select aria-label="Filter by category" className="h-9 w-40 text-xs" value={category} onChange={(e) => setCategory(e.target.value)}>
                    <option value="">All categories</option>{Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
                  </Select>
                  <Select aria-label="Filter by action" className="h-9 w-36 text-xs" value={action} onChange={(e) => setAction(e.target.value)}>
                    <option value="">All actions</option>{Object.entries(ACTION_META).map(([k, v]) => <option key={k} value={k}>{v.label}</option>)}
                  </Select>
                  <Select aria-label="Sort by" className="h-9 w-36 text-xs" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
                    <option value="priority">Sort: priority</option><option value="gap">Sort: gap</option><option value="importance">Sort: importance</option><option value="name">Sort: name</option>
                  </Select>
                </div>
              } />
            <CardBody className="px-0 sm:px-0">
              {rows.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[760px] text-sm">
                    <thead className="border-b border-line text-left text-xs text-fg-faint">
                      <tr>
                        <th className="pb-2 pl-4 font-medium">Skill</th><th className="px-3 pb-2 font-medium">Level vs required</th><th className="px-3 pb-2 font-medium">Est / Req</th>
                        <th className="px-3 pb-2 font-medium">Gap <InfoHint content="Levels below the requirement; ? = unknown" /></th><th className="px-3 pb-2 font-medium">Importance</th>
                        <th className="px-3 pb-2 font-medium">Action</th><th className="px-3 pb-2 pr-4 text-right font-medium"><ArrowDownUp className="inline size-3" /> Priority</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-line">{rows.map((g) => <GapRow key={g.skill_id} g={g} />)}</tbody>
                  </table>
                </div>
              ) : <div className="px-6"><EmptyState title="No skills match the filters" /></div>}
            </CardBody>
          </Card>
          {gaps.isFetching && <Notice tone="info">Recomputing with the new assumptions…</Notice>}
        </div>
      )}
    </div>
  );
}
