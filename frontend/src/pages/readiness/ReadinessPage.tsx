import { useMutation, useQuery } from "@tanstack/react-query";
import { BookOpenCheck, Gauge, Info, RefreshCw, Scale } from "lucide-react";
import { motion } from "motion/react";
import { useState } from "react";
import { Link } from "react-router";
import { toast } from "sonner";

import { ShapChart } from "@/components/charts/ShapChart";
import { PageHeader } from "@/components/layout/AppShell";
import { Reveal } from "@/components/motion";
import { Button } from "@/components/ui/button";
import { Badge, Card, CardBody, CardHeader, InfoHint, Stat } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice, SyntheticModelNotice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, qk, queryClient, useLatestReadiness, useProfile, useRoleGaps } from "@/lib/queries";
import type { Contribution, ReadinessResult } from "@/lib/types";
import { BAND_META, dateTime, pct } from "@/lib/utils";

const BANDS = [
  { key: "not_yet_ready", from: 0, to: 0.35 },
  { key: "developing", from: 0.35, to: 0.65 },
  { key: "interview_ready", from: 0.65, to: 1 },
];

function BandGauge({ band, probability }: { band: string; probability: number | null }) {
  return (
    <div>
      <div className="relative flex h-3 overflow-hidden rounded-full" aria-hidden>
        {BANDS.map((b) => (
          <div key={b.key} style={{ width: `${(b.to - b.from) * 100}%`, background: BAND_META[b.key]!.color, opacity: b.key === band ? 0.95 : 0.18 }} />
        ))}
        {probability !== null && (
          <motion.div className="absolute -top-1 h-5 w-1 rounded-full bg-fg shadow" initial={{ left: "0%" }} animate={{ left: `calc(${probability * 100}% - 2px)` }}
            transition={{ duration: 1, ease: [0.22, 1, 0.36, 1] }} />
        )}
      </div>
      <div className="mt-2 flex justify-between font-mono text-[0.65rem] text-fg-faint">
        <span>0</span><span>0.35</span><span>0.65</span><span>1</span>
      </div>
    </div>
  );
}

function GapStatement({ roleId }: { roleId: number | null | undefined }) {
  const gaps = useRoleGaps(roleId);
  if (!gaps.data) return null;
  const met = gaps.data.gaps.filter((g) => g.action === "maintain" || g.action === "verify").length;
  const top = gaps.data.gaps.filter((g) => ["learn", "prerequisite", "assess"].includes(g.action)).slice(0, 2);
  return (
    <p className="text-sm leading-relaxed text-fg-muted">
      For <span className="text-fg">{gaps.data.role_name}</span>, your recorded profile meets {met} of {gaps.data.gaps.length} requirements in the
      role-skill framework (v{gaps.data.role_version}).{" "}
      {top.length > 0 && (
        <>The highest-priority gaps identified by the framework are{" "}
          {top.map((g, i) => (
            <span key={g.skill_id}>
              <span className="text-fg">{g.skill_name}</span> ({g.estimated_level === null ? "not yet measured" : `level ${g.estimated_level} of required ${g.required_level}`}){i < top.length - 1 ? " and " : "."}
            </span>
          ))}</>
      )}
    </p>
  );
}

function ContributionTable({ rows }: { rows: Contribution[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <caption className="sr-only">All feature contributions</caption>
        <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2 font-medium">Input</th><th className="pb-2 font-medium">Your value</th><th className="pb-2 text-right font-medium">Contribution</th></tr></thead>
        <tbody className="divide-y divide-line">
          {rows.map((c) => (
            <tr key={c.feature}>
              <td className="py-2">{c.label}</td>
              <td className="py-2">{c.is_missing ? <Badge tone="muted">unknown</Badge> : <span className="metric">{c.display_value}</span>}</td>
              <td className={`metric py-2 text-right ${c.contribution > 0 ? "text-ok" : c.contribution < 0 ? "text-danger" : "text-fg-faint"}`}>
                {c.contribution > 0 ? "+" : ""}{c.contribution.toFixed(3)}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReadinessPage() {
  const profile = useProfile();
  const latest = useLatestReadiness();
  const [result, setResult] = useState<ReadinessResult | null>(null);
  const history = useQuery({ queryKey: qk.readinessHistory, queryFn: () => api<{ items: { id: string; created_at: string; band: string; probability: number | null; model_version: string }[] }>("/readiness/history") });
  const run = useMutation({
    mutationFn: () => api<ReadinessResult>("/readiness/analyse", { method: "POST" }),
    onSuccess: (r) => {
      setResult(r);
      if (!r.available) toast.warning(r.message ?? "Model unavailable.");
      void queryClient.invalidateQueries({ queryKey: ["readiness"] });
      void invalidateTwin();
    },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Analysis failed."),
  });

  const contributions: Contribution[] | undefined = result?.explanation?.contributions ?? latest.data?.explanation?.contributions;
  const band = result?.band ?? latest.data?.band;
  const prob = result ? (result.probability?.value ?? null) : (latest.data?.probability ?? null);
  const outputSpace = result?.explanation?.output_space ?? latest.data?.explanation?.output_space ?? "log_odds";
  const summary = result?.summary ?? latest.data?.explanation?.summary;
  const warnings = result?.warnings ?? latest.data?.warnings ?? [];
  const synthetic = result?.is_synthetic_model ?? latest.data?.is_synthetic_model;
  const modelAvailable = latest.data?.model.available;

  return (
    <div>
      <PageHeader icon={Gauge} eyebrow="Career readiness" title="Readiness analysis & explanation"
        description="An estimate of whether an assessor would judge you interview-ready for an entry-level technical role, with an explanation of how the model used each input. It is not a placement or hiring prediction."
        actions={<>
          <Button asChild variant="secondary"><Link to="/app/readiness/model"><BookOpenCheck className="size-4" /> Model card</Link></Button>
          <Button onClick={() => run.mutate()} loading={run.isPending} disabled={!modelAvailable}><RefreshCw className="size-4" /> Run analysis</Button>
        </>} />

      {latest.isLoading ? <LoadingBlock rows={4} /> : latest.error ? <ErrorState error={latest.error} onRetry={() => latest.refetch()} /> : (
        <div className="space-y-5">
          {!modelAvailable && (
            <Notice tone="warn" title="The readiness model is unavailable">
              {latest.data?.model.reason_unavailable ?? "No active model is registered."} No estimate is produced rather than a guessed one.
            </Notice>
          )}
          {synthetic && <SyntheticModelNotice />}
          {band ? (
            <div className="grid gap-5 lg:grid-cols-[1fr_1.5fr]">
              <Reveal>
                <Card className="h-full">
                  <CardHeader eyebrow="Estimate" title={BAND_META[band]?.label ?? band}
                    description={prob !== null ? "Calibrated probability, rounded to the nearest 5%." : "Calibration is not validated, so only the band is shown."} />
                  <CardBody className="space-y-5">
                    <div className="flex items-end gap-6">
                      <Stat label="Probability" value={prob !== null ? `≈ ${pct(prob)}` : "—"} hint="Validated calibration: among held-out records given ≈X%, about X% were labelled ready by assessors. Applies only to the training population." />
                      {result?.known_input_share !== undefined && <Stat label="Inputs known" value={pct(result.known_input_share)} hint="Share of the model's inputs recorded for you. Unknown inputs are handled explicitly, not treated as zero." />}
                    </div>
                    <BandGauge band={band} probability={prob} />
                    {warnings.length > 0 && (
                      <ul className="space-y-2">
                        {warnings.filter((w) => w.code !== "synthetic_model").map((w, i) => <li key={i}><Notice tone="warn">{w.message}</Notice></li>)}
                      </ul>
                    )}
                    <GapStatement roleId={profile.data?.target_role_id} />
                  </CardBody>
                </Card>
              </Reveal>
              <Reveal delay={0.05}>
                <Card className="h-full">
                  <CardHeader eyebrow="Explainability (SHAP)" title="What moved the estimate"
                    description={<>Green raised and red lowered the model's output ({outputSpace.replace("_", "-")} units) relative to the training baseline.</>}
                    actions={<InfoHint content="SHAP values split the model's output into additive per-input contributions. They describe the model's behaviour, not real-world cause and effect." />} />
                  <CardBody>
                    {contributions ? <ShapChart contributions={contributions} outputSpace={outputSpace} /> : <LoadingBlock rows={2} />}
                    {summary && <p className="mt-4 rounded-lg bg-ink-800/60 p-3 text-sm text-fg-muted">{summary}</p>}
                  </CardBody>
                </Card>
              </Reveal>
            </div>
          ) : modelAvailable ? (
            <EmptyState icon={<Gauge className="size-5" />} title="No estimate yet" action={<Button onClick={() => run.mutate()} loading={run.isPending}>Run analysis</Button>}>
              Running the analysis records a snapshot of your twin and the model version used.
            </EmptyState>
          ) : null}

          {contributions && (
            <div className="grid gap-5 lg:grid-cols-[1.5fr_1fr]">
              <Card>
                <CardHeader title="All inputs and contributions" description="Every input the model saw, including those recorded as unknown." />
                <CardBody><ContributionTable rows={contributions} /></CardBody>
              </Card>
              <Card>
                <CardHeader title="How to read this" />
                <CardBody className="space-y-4 text-sm text-fg-muted">
                  <p className="flex gap-2"><Scale className="mt-0.5 size-4 shrink-0 text-aurora" /><span><strong className="text-fg">Correlation</strong>: inputs that tended to go with "ready" labels in the training data.</span></p>
                  <p className="flex gap-2"><Info className="mt-0.5 size-4 shrink-0 text-aurora" /><span><strong className="text-fg">Model attribution</strong>: how this particular model combined your inputs. It can change between model versions.</span></p>
                  <p className="flex gap-2"><Info className="mt-0.5 size-4 shrink-0 text-warn" /><span><strong className="text-fg">Not causation</strong>: changing an input will not necessarily change an assessor's judgement or your employability by the same amount.</span></p>
                  <Button asChild variant="subtle" size="sm"><Link to="/app/simulator">Explore hypotheticals in the simulator</Link></Button>
                </CardBody>
              </Card>
            </div>
          )}

          {history.data && history.data.items.length > 0 && (
            <Card>
              <CardHeader title="Estimate history" description="Each estimate is pinned to a twin snapshot and model version." />
              <CardBody>
                <ul className="divide-y divide-line text-sm">
                  {history.data.items.map((h) => (
                    <li key={h.id} className="flex flex-wrap items-center gap-3 py-2">
                      <span className="w-44 text-fg-muted">{dateTime(h.created_at)}</span>
                      <Badge tone={h.band === "interview_ready" ? "ok" : h.band === "developing" ? "warn" : "danger"}>{BAND_META[h.band]?.label ?? h.band}</Badge>
                      <span className="metric">{h.probability !== null ? `≈ ${pct(h.probability)}` : "band only"}</span>
                      <span className="ml-auto font-mono text-[0.68rem] text-fg-faint">{h.model_version}</span>
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
