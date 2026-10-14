import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { ArrowLeft, ArrowRight, Check, GraduationCap, Hourglass, Sparkles, Target } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useMemo, useState } from "react";
import { useForm } from "react-hook-form";
import { useNavigate } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { Brand } from "@/components/layout/Brand";
import { Button } from "@/components/ui/button";
import { Field, Input, Slider } from "@/components/ui/form";
import { Badge } from "@/components/ui/primitives";
import { ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, qk, useCatalogueSkills, useProfile, useRoles, useSkills } from "@/lib/queries";
import type { CareerRole, CatalogueSkill, Profile } from "@/lib/types";
import { cn, LEVEL_NAMES } from "@/lib/utils";

const STEPS = [
  { key: "academics", label: "Academics", icon: GraduationCap },
  { key: "goals", label: "Goals", icon: Target },
  { key: "skills", label: "Skills", icon: Sparkles },
  { key: "availability", label: "Availability", icon: Hourglass },
] as const;

const academicSchema = z.object({
  degree: z.string().trim().min(2, "Enter your degree (e.g. B.Tech).").max(80),
  specialization: z.string().trim().min(2, "Enter your specialization.").max(80),
  current_semester: z.coerce.number().int().min(1).max(12),
  graduation_year: z.coerce.number().int().min(2000).max(2100),
  cgpa: z.union([z.literal("").transform(() => null), z.coerce.number().min(0, "0–10").max(10, "0–10")]).nullable(),
});

function StepAcademics({ onDone }: { onDone: () => void }) {
  const profile = useProfile();
  const form = useForm<z.input<typeof academicSchema>, unknown, z.output<typeof academicSchema>>({
    resolver: zodResolver(academicSchema),
    mode: "onTouched",
  });
  useEffect(() => {
    const p = profile.data;
    if (p) form.reset({ degree: p.degree ?? "", specialization: p.specialization ?? "", current_semester: p.current_semester ?? 5,
      graduation_year: p.graduation_year ?? new Date().getFullYear() + 2, cgpa: p.cgpa ?? "" });
  }, [profile.data, form]);
  const submit = form.handleSubmit(async (v) => {
    await api("/profile", { method: "PATCH", body: v });
    await invalidateTwin();
    onDone();
  });
  if (profile.isLoading) return <LoadingBlock rows={2} />;
  const e = form.formState.errors;
  return (
    <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
      <Field label="Degree" error={e.degree?.message} required>
        {({ id, describedBy, invalid }) => <Input id={id} placeholder="B.Tech" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("degree")} />}
      </Field>
      <Field label="Specialization" error={e.specialization?.message} required>
        {({ id, describedBy, invalid }) => <Input id={id} placeholder="Computer Engineering" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("specialization")} />}
      </Field>
      <Field label="Current semester" error={e.current_semester?.message} required>
        {({ id, describedBy, invalid }) => <Input id={id} type="number" min={1} max={12} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("current_semester")} />}
      </Field>
      <Field label="Graduation year" error={e.graduation_year?.message} required>
        {({ id, describedBy, invalid }) => <Input id={id} type="number" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("graduation_year")} />}
      </Field>
      <Field label="CGPA (10-point scale)" hint="Optional. Leave blank if you prefer not to share it." error={e.cgpa?.message}>
        {({ id, describedBy, invalid }) => <Input id={id} type="number" step="0.01" min={0} max={10} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("cgpa")} />}
      </Field>
      <div className="flex items-end justify-end sm:col-span-2">
        <Button type="submit" loading={form.formState.isSubmitting}>Save and continue <ArrowRight className="size-4" /></Button>
      </div>
    </form>
  );
}

function StepGoals({ onDone }: { onDone: () => void }) {
  const roles = useRoles();
  const profile = useProfile();
  if (roles.isLoading || profile.isLoading) return <LoadingBlock rows={3} />;
  if (roles.error || profile.error) return <ErrorState error={roles.error ?? profile.error} onRetry={() => { void roles.refetch(); void profile.refetch(); }} />;
  return <GoalsForm profile={profile.data!} roles={roles.data!.roles} onDone={onDone} />;
}

function GoalsForm({ profile, roles, onDone }: { profile: Profile; roles: CareerRole[]; onDone: () => void }) {
  const [target, setTarget] = useState<number | null>(profile.target_role_id);
  const [preferred, setPreferred] = useState<number[]>(profile.preferred_role_ids.filter((r) => r !== profile.target_role_id));
  const [interests, setInterests] = useState(profile.career_interests.join(", "));
  const [busy, setBusy] = useState(false);
  async function save() {
    if (!target) return;
    setBusy(true);
    try {
      await api("/profile/roles", { method: "PUT", body: { target_role_id: target, preferred_role_ids: preferred } });
      await api("/profile", { method: "PATCH", body: {
        career_interests: interests.split(",").map((s) => s.trim()).filter(Boolean).slice(0, 10) } });
      await invalidateTwin();
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save goals.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-6">
      <div>
        <p className="mb-3 text-sm font-medium">Primary target role <span className="text-danger">*</span></p>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3" role="radiogroup" aria-label="Target role">
          {roles.map((r) => {
            const active = target === r.id;
            return (
              <button key={r.id} type="button" role="radio" aria-checked={active}
                onClick={() => { setTarget(r.id); setPreferred((p) => p.filter((x) => x !== r.id)); }}
                className={cn("card p-4 text-left transition", active ? "border-aurora/60 shadow-[var(--shadow-glow)]" : "hover:border-line-strong")}>
                <div className="flex items-center justify-between">
                  <p className="font-display font-semibold">{r.name}</p>
                  {active && <Check className="size-4 text-aurora" />}
                </div>
                <p className="mt-1 text-xs leading-relaxed text-fg-muted">{r.summary}</p>
                <p className="mt-2 font-mono text-[0.68rem] text-fg-faint">{r.requirements.length} requirements · v{r.version}</p>
              </button>
            );
          })}
        </div>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">Other roles you are considering (up to 4)</p>
        <div className="flex flex-wrap gap-2">
          {roles.filter((r) => r.id !== target).map((r) => {
            const on = preferred.includes(r.id);
            return (
              <button key={r.id} type="button" aria-pressed={on}
                onClick={() => setPreferred((p) => (on ? p.filter((x) => x !== r.id) : p.length < 4 ? [...p, r.id] : p))}
                className={cn("rounded-full border px-3 py-1.5 text-sm transition", on ? "border-iris/60 bg-iris/10 text-iris" : "border-line text-fg-muted hover:text-fg")}>
                {r.name}
              </button>
            );
          })}
        </div>
      </div>
      <Field label="Career interests" hint="Comma-separated, e.g. computer vision, fintech, open source">
        {({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} value={interests} onChange={(e) => setInterests(e.target.value)} />}
      </Field>
      <div className="flex justify-end">
        <Button onClick={save} loading={busy} disabled={!target}>Save and continue <ArrowRight className="size-4" /></Button>
      </div>
    </div>
  );
}

function StepSkills({ onDone }: { onDone: () => void }) {
  const roles = useRoles();
  const profile = useProfile();
  const skills = useSkills();
  const catalogue = useCatalogueSkills();
  const targetSkills = useMemo(() => {
    const role = roles.data?.roles.find((r) => r.id === profile.data?.target_role_id);
    return role?.requirements.map((q) => q.skill_id) ?? [];
  }, [roles.data, profile.data]);
  if (skills.isLoading || catalogue.isLoading || roles.isLoading || profile.isLoading) return <LoadingBlock rows={4} />;
  if (skills.error || catalogue.error) return <ErrorState error={skills.error ?? catalogue.error} />;
  const initial: Record<number, number | null> = {};
  for (const s of skills.data!.items) if (s.self_rating !== null) initial[s.skill_id] = s.self_rating;
  const list = (catalogue.data?.skills ?? []).filter((s) => targetSkills.includes(s.id));
  return <SkillsForm list={list} initial={initial} onDone={onDone} />;
}

function SkillsForm({ list, initial, onDone }: { list: CatalogueSkill[]; initial: Record<number, number | null>; onDone: () => void }) {
  const [ratings, setRatings] = useState<Record<number, number | null>>(initial);
  const [busy, setBusy] = useState(false);
  async function save() {
    const entries = Object.entries(ratings).filter(([, v]) => v !== null) as [string, number][];
    setBusy(true);
    try {
      if (entries.length) {
        await api("/twin/skills", { method: "PUT", body: { source: "onboarding", ratings: entries.map(([k, v]) => ({ skill_id: Number(k), self_rating: v })) } });
      }
      await invalidateTwin();
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save ratings.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-5">
      <Notice tone="info" title="Rate honestly — or skip">
        Self-ratings carry the least weight. Skills you skip stay <strong>unknown</strong>, which is shown as unmeasured rather than counted as zero.
      </Notice>
      <ul className="divide-y divide-line rounded-xl border border-line">
        {list.map((s) => {
          const v = ratings[s.id];
          return (
            <li key={s.id} className="flex flex-col gap-3 p-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">{s.name}</p>
                <p className="line-clamp-1 text-xs text-fg-faint">{s.description}</p>
              </div>
              <div className="flex shrink-0 flex-wrap items-center gap-1.5" role="radiogroup" aria-label={`${s.name} self-rating`}>
                {LEVEL_NAMES.map((name, lvl) => (
                  <button key={name} type="button" role="radio" aria-checked={v === lvl} title={name} aria-label={`${lvl} – ${name}`}
                    onClick={() => setRatings((r) => ({ ...r, [s.id]: lvl }))}
                    className={cn("h-8 min-w-8 rounded-md border px-2 font-mono text-xs transition",
                      v === lvl ? "border-aurora bg-aurora/15 text-aurora" : "border-line text-fg-muted hover:border-line-strong")}>
                    {lvl}
                  </button>
                ))}
                <button type="button" onClick={() => setRatings((r) => ({ ...r, [s.id]: null }))}
                  className={cn("h-8 rounded-md px-2 text-xs", v === null || v === undefined ? "text-fg" : "text-fg-faint hover:text-fg")}>
                  Skip
                </button>
              </div>
            </li>
          );
        })}
      </ul>
      <p className="text-xs text-fg-faint">Scale: {LEVEL_NAMES.map((n, i) => `${i} ${n}`).join(" · ")}</p>
      <div className="flex justify-end">
        <Button onClick={save} loading={busy}>Save and continue <ArrowRight className="size-4" /></Button>
      </div>
    </div>
  );
}

const PREFS = [
  ["documentation", "Documentation"], ["video", "Video"], ["interactive", "Interactive"],
  ["project_based", "Project-based"], ["books", "Books"], ["mentoring", "Mentoring"],
] as const;

function StepAvailability({ onDone }: { onDone: () => void }) {
  const profile = useProfile();
  if (profile.isLoading) return <LoadingBlock rows={2} />;
  if (profile.error) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  return <AvailabilityForm profile={profile.data!} onDone={onDone} />;
}

function AvailabilityForm({ profile, onDone }: { profile: Profile; onDone: () => void }) {
  const [hours, setHours] = useState(profile.weekly_hours);
  const [prefs, setPrefs] = useState<string[]>(profile.learning_preferences);
  const [busy, setBusy] = useState(false);
  async function finish() {
    setBusy(true);
    try {
      await api("/profile", { method: "PATCH", body: { learning_preferences: prefs, weekly_hours: hours } });
      await api("/profile/onboarding/complete", { method: "POST" });
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not finish onboarding.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="space-y-6">
      <div>
        <div className="mb-3 flex items-baseline justify-between">
          <p className="text-sm font-medium">Weekly study time</p>
          <p className="metric text-2xl font-semibold text-aurora">{hours} h</p>
        </div>
        <Slider value={hours} onChange={setHours} min={1} max={40} label="Weekly study hours" marks={[1, 10, 20, 30, 40]} />
        <p className="mt-2 text-xs text-fg-faint">Your roadmap is scheduled against this. A realistic number beats an ambitious one.</p>
      </div>
      <div>
        <p className="mb-2 text-sm font-medium">How do you like to learn?</p>
        <div className="flex flex-wrap gap-2">
          {PREFS.map(([key, label]) => {
            const on = prefs.includes(key);
            return (
              <button key={key} type="button" aria-pressed={on} onClick={() => setPrefs((p) => (on ? p.filter((x) => x !== key) : [...p, key]))}
                className={cn("rounded-full border px-3 py-1.5 text-sm transition", on ? "border-aurora/60 bg-aurora/10 text-aurora" : "border-line text-fg-muted hover:text-fg")}>
                {label}
              </button>
            );
          })}
        </div>
      </div>
      <div className="flex justify-end">
        <Button onClick={finish} loading={busy}>Finish setup <Check className="size-4" /></Button>
      </div>
    </div>
  );
}

export function OnboardingPage() {
  const [step, setStep] = useState(0);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const Current = [StepAcademics, StepGoals, StepSkills, StepAvailability][step]!;
  function goTo(n: number) {
    setStep(n);
    window.scrollTo({ top: 0, behavior: "smooth" });
  }
  async function next() {
    if (step < STEPS.length - 1) goTo(step + 1);
    else {
      await qc.invalidateQueries({ queryKey: qk.me });
      await invalidateTwin();
      toast.success("Your digital twin is ready.");
      navigate("/app", { replace: true });
    }
  }
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-8 flex items-center justify-between">
        <Brand to="/app/onboarding" />
        <Badge tone="aurora">Setup · step {step + 1} of {STEPS.length}</Badge>
      </div>
      <ol className="mb-8 grid grid-cols-4 gap-2" aria-label="Onboarding progress">
        {STEPS.map((s, i) => (
          <li key={s.key} className="space-y-2">
            <div className={cn("h-1 rounded-full transition-colors", i <= step ? "bg-gradient-to-r from-aurora to-iris" : "bg-white/[0.07]")} />
            <p className={cn("flex items-center gap-1.5 text-xs", i === step ? "text-fg" : "text-fg-faint")} aria-current={i === step ? "step" : undefined}>
              <s.icon className="size-3.5" /> <span className="hidden sm:inline">{s.label}</span>
            </p>
          </li>
        ))}
      </ol>
      <div className="card p-5 sm:p-8">
        <h1 className="mb-6 text-2xl font-semibold">{["Tell us about your studies", "Where are you heading?", "Quick skill self-assessment", "Plan around your time"][step]}</h1>
        {/* Enter-only animation: the next step mounts immediately even if animation frames are throttled. */}
        <motion.div key={step} initial={{ opacity: 0, x: 16 }} animate={{ opacity: 1, x: 0 }} transition={{ duration: 0.25 }}>
          <Current onDone={next} />
        </motion.div>
      </div>
      {step > 0 && (
        <Button variant="ghost" className="mt-4" onClick={() => goTo(step - 1)}>
          <ArrowLeft className="size-4" /> Back
        </Button>
      )}
    </div>
  );
}
