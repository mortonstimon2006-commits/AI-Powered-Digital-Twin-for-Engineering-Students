import { ChevronDown, Search, X } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useMemo, useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Input, Select } from "@/components/ui/form";
import { Badge, Card, CardBody, CardHeader, LevelMeter, StatusBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, useSkills } from "@/lib/queries";
import type { SkillItem } from "@/lib/types";
import { CATEGORY_COLOR, CATEGORY_LABEL, cn, LEVEL_NAMES, level } from "@/lib/utils";

function SkillRow({ s }: { s: SkillItem }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  async function rate(v: number | null) {
    setBusy(true);
    try {
      if (v === null) await api(`/twin/skills/${s.skill_id}`, { method: "DELETE" });
      else await api(`/twin/skills/${s.skill_id}`, { method: "PUT", body: { self_rating: v } });
      await invalidateTwin();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save rating.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <li className="border-b border-line last:border-0">
      <div className="flex flex-col gap-3 px-4 py-3 md:flex-row md:items-center">
        <button type="button" className="flex min-w-0 flex-1 items-center gap-3 text-left" onClick={() => setOpen((o) => !o)} aria-expanded={open}>
          <span className="size-2 shrink-0 rounded-full" style={{ background: CATEGORY_COLOR[s.category] }} aria-hidden />
          <span className="min-w-0">
            <span className="block truncate text-sm font-medium">{s.name}</span>
            <span className="block text-xs text-fg-faint">{CATEGORY_LABEL[s.category]} · {s.kind}</span>
          </span>
          <ChevronDown className={cn("ml-auto size-4 shrink-0 text-fg-faint transition md:ml-2", open && "rotate-180")} aria-hidden />
        </button>
        <div className="flex flex-wrap items-center gap-3 md:justify-end">
          <LevelMeter value={s.estimated_level} status={s.status} />
          <span className="metric w-10 text-sm">{level(s.estimated_level)}</span>
          <StatusBadge status={s.status} />
          <Select aria-label={`Self-rating for ${s.name}`} className="h-8 w-36 text-xs" disabled={busy}
            value={s.self_rating ?? ""} onChange={(e) => rate(e.target.value === "" ? null : Number(e.target.value))}>
            <option value="">Self-rating: none</option>
            {LEVEL_NAMES.map((n, i) => <option key={n} value={i}>{i} · {n}</option>)}
          </Select>
        </div>
      </div>
      <AnimatePresence initial={false}>
        {open && (
          <motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: "auto", opacity: 1 }} exit={{ height: 0, opacity: 0 }} className="overflow-hidden">
            <div className="space-y-3 bg-ink-800/40 px-4 py-4 text-sm">
              <p className="text-fg-muted">{s.description}</p>
              <p className="eyebrow">Evidence behind this estimate (highest-trust source wins)</p>
              {s.signals.length ? (
                <ul className="space-y-1.5">
                  {s.signals.map((sig, i) => (
                    <li key={i} className={cn("flex flex-wrap items-center gap-2", i > 0 && "opacity-70")}>
                      <StatusBadge status={sig.status} />
                      <span className="metric">level {level(sig.level)}</span>
                      <span className="text-fg-muted">
                        {sig.source === "assessment" ? `${sig.assessment} — ${sig.pct}%` : sig.source === "self_rating" ? "Your self-rating" : `${sig.source}: ${sig.title ?? ""}`}
                      </span>
                      {i === 0 && <Badge tone="aurora">used</Badge>}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-fg-faint">Nothing recorded. This skill is <strong>unknown</strong> (not zero). Rate it, link a project, or ask a mentor for an assessment.</p>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </li>
  );
}

export function SkillsSection() {
  const skills = useSkills();
  const [q, setQ] = useState("");
  const [cat, setCat] = useState("");
  const [status, setStatus] = useState("");
  const [sort, setSort] = useState<"category" | "level" | "name">("category");
  const items = useMemo(() => {
    let list = skills.data?.items ?? [];
    if (q) list = list.filter((s) => s.name.toLowerCase().includes(q.toLowerCase()));
    if (cat) list = list.filter((s) => s.category === cat);
    if (status) list = list.filter((s) => s.status === status);
    const sorted = [...list];
    if (sort === "level") sorted.sort((a, b) => (b.estimated_level ?? -1) - (a.estimated_level ?? -1));
    if (sort === "name") sorted.sort((a, b) => a.name.localeCompare(b.name));
    return sorted;
  }, [skills.data, q, cat, status, sort]);
  if (skills.isLoading) return <LoadingBlock rows={5} />;
  if (skills.error) return <ErrorState error={skills.error} onRetry={() => skills.refetch()} />;
  const scale = skills.data!.proficiency_scale;
  return (
    <Card>
      <CardHeader title="Skills" description="Self-ratings are the lowest-trust signal; evidence and verified assessments override them." />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap gap-2">
          <div className="relative min-w-48 flex-1">
            <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-fg-faint" aria-hidden />
            <Input aria-label="Search skills" placeholder="Search skills" className="pl-9" value={q} onChange={(e) => setQ(e.target.value)} />
          </div>
          <Select aria-label="Filter by category" className="w-44" value={cat} onChange={(e) => setCat(e.target.value)}>
            <option value="">All categories</option>
            {Object.entries(CATEGORY_LABEL).map(([k, v]) => <option key={k} value={k}>{v}</option>)}
          </Select>
          <Select aria-label="Filter by evidence status" className="w-44" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">All statuses</option>
            <option value="assessed">Assessed</option>
            <option value="verified_evidence">Verified evidence</option>
            <option value="unverified_evidence">Unverified evidence</option>
            <option value="self_reported">Self-reported</option>
            <option value="unknown">Unknown</option>
          </Select>
          <Select aria-label="Sort" className="w-36" value={sort} onChange={(e) => setSort(e.target.value as typeof sort)}>
            <option value="category">By category</option>
            <option value="level">By level</option>
            <option value="name">By name</option>
          </Select>
          {(q || cat || status) && <Button variant="ghost" onClick={() => { setQ(""); setCat(""); setStatus(""); }}><X className="size-4" /> Clear</Button>}
        </div>
        <details className="rounded-lg border border-line bg-ink-800/40 px-4 py-3 text-sm">
          <summary className="cursor-pointer text-fg-muted">Proficiency scale definitions</summary>
          <dl className="mt-3 grid gap-2 sm:grid-cols-2">
            {scale.map((l) => (<div key={l.level}><dt className="font-medium">{l.level} · {l.name}</dt><dd className="text-fg-muted">{l.description}</dd></div>))}
          </dl>
        </details>
        {items.length ? <ul className="overflow-hidden rounded-xl border border-line">{items.map((s) => <SkillRow key={s.skill_id} s={s} />)}</ul>
          : <EmptyState title="No skills match these filters" />}
      </CardBody>
    </Card>
  );
}
