import { useQuery } from "@tanstack/react-query";
import { BookOpenCheck } from "lucide-react";
import { Bar, BarChart, CartesianGrid, Line, LineChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";

import { PageHeader } from "@/components/layout/AppShell";
import { Badge, Card, CardBody, CardHeader, Stat } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice, SyntheticModelNotice } from "@/components/ui/states";
import { api } from "@/lib/api";
import { dateTime } from "@/lib/utils";

interface ModelInfo {
  available: boolean;
  version: string;
  algorithm: string;
  is_synthetic: boolean;
  target_definition: string;
  dataset: { source: string; origin: string; splits: Record<string, { rows: number; students: number; positive_rate: number }> };
  test_metrics: Record<string, number>;
  test_ci95: Record<string, { low: number; high: number }>;
  confusion_matrix: { tn: number; fp: number; fn: number; tp: number };
  calibration: { method: string; validated: boolean; test_ece_calibrated: number; test_ece_uncalibrated: number; criterion: string;
    reliability_test: { bin_low: number; bin_high: number; n: number; mean_predicted: number; observed_rate: number }[] };
  band_observed_rates: { band: string; share: number; observed_ready_rate: number | null }[];
  model_selection: { rule: string; baseline: { name: string; cv_pr_auc_mean: number }; candidates: Record<string, { pr_auc_mean: number; pr_auc_std: number; roc_auc_mean: number }> };
  global_importance: { feature: string; label: string; mean_abs_shap: number }[];
  fairness: { group_column: string; groups: { group: string; n: number; base_rate: number; tpr?: number; fpr?: number; roc_auc?: number; ece?: number; sufficient_n: boolean }[]; max_gaps: Record<string, number> } | null;
  fairness_note: string;
  leakage_checks: Record<string, unknown>;
  limitations: string[];
  trained_at: string;
}

const tooltipStyle = { background: "#131b2e", border: "1px solid #31405e", borderRadius: 10, color: "#e8edf6" };

export function ModelCardPage() {
  const q = useQuery({ queryKey: ["readiness", "model"], queryFn: () => api<ModelInfo>("/readiness/model") });
  if (q.isLoading) return <LoadingBlock rows={5} />;
  if (q.error) return <ErrorState error={q.error} onRetry={() => q.refetch()} />;
  const m = q.data!;
  if (!m.available) return <EmptyState title="No active model" icon={<BookOpenCheck className="size-5" />}>No readiness model is registered, so there is no model card to show.</EmptyState>;
  const t = m.test_metrics;
  const ci = m.test_ci95;
  const rel = m.calibration.reliability_test.map((r) => ({ x: Number(((r.bin_low + r.bin_high) / 2).toFixed(2)), predicted: r.mean_predicted, observed: r.observed_rate, n: r.n }));
  const candidates = Object.entries(m.model_selection.candidates).map(([k, v]) => ({ name: k.replace("_", " "), pr_auc: Number(v.pr_auc_mean.toFixed(3)) }));
  return (
    <div>
      <PageHeader icon={BookOpenCheck} eyebrow="Model card" title={m.version}
        description={`${m.algorithm.replace("_", " ")} · trained ${dateTime(m.trained_at)}. Every number on this page comes from the executed evaluation recorded with the model artifact.`} />
      <div className="space-y-5">
        {m.is_synthetic && <SyntheticModelNotice />}
        <Card>
          <CardHeader title="Prediction target" />
          <CardBody><p className="text-sm text-fg-muted">{m.target_definition}</p></CardBody>
        </Card>
        <div className="grid gap-5 lg:grid-cols-3">
          <Card className="lg:col-span-2">
            <CardHeader title="Held-out test performance" description={`n = ${m.dataset.splits.test?.rows} records from ${m.dataset.splits.test?.students} students never seen in training. 95% CIs from a student-clustered bootstrap.`} />
            <CardBody className="grid grid-cols-2 gap-5 sm:grid-cols-4">
              {(["roc_auc", "pr_auc", "f1", "brier"] as const).map((k) => (
                <Stat key={k} label={k.replace("_", "-").toUpperCase()} value={t[k]!.toFixed(3)} sub={ci[k] ? `CI ${ci[k]!.low.toFixed(3)}–${ci[k]!.high.toFixed(3)}` : undefined} />
              ))}
              {(["precision", "recall", "accuracy", "ece"] as const).map((k) => <Stat key={k} label={k.toUpperCase()} value={t[k]!.toFixed(3)} />)}
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Confusion matrix" description="At the decision threshold chosen on the validation split." />
            <CardBody>
              <div className="grid grid-cols-2 gap-2 text-center text-sm" role="table" aria-label="Confusion matrix">
                {[["True negative", m.confusion_matrix.tn, "ok"], ["False positive", m.confusion_matrix.fp, "danger"], ["False negative", m.confusion_matrix.fn, "danger"], ["True positive", m.confusion_matrix.tp, "ok"]].map(([l, v, tone]) => (
                  <div key={String(l)} role="cell" className={`rounded-lg border p-3 ${tone === "ok" ? "border-ok/25 bg-ok/5" : "border-danger/25 bg-danger/5"}`}>
                    <p className="metric text-xl font-semibold">{String(v)}</p><p className="text-xs text-fg-muted">{String(l)}</p>
                  </div>
                ))}
              </div>
            </CardBody>
          </Card>
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title="Calibration (reliability)" description={`${m.calibration.method}. Test ECE ${m.calibration.test_ece_uncalibrated} → ${m.calibration.test_ece_calibrated}.`}
              actions={<Badge tone={m.calibration.validated ? "ok" : "warn"}>{m.calibration.validated ? "validated" : "not validated"}</Badge>} />
            <CardBody>
              <div className="h-64">
                <ResponsiveContainer>
                  <LineChart data={rel} margin={{ left: -10, right: 10 }}>
                    <CartesianGrid stroke="#1a2338" />
                    <XAxis dataKey="x" type="number" domain={[0, 1]} tick={{ fill: "#6f7d96", fontSize: 11 }} />
                    <YAxis domain={[0, 1]} tick={{ fill: "#6f7d96", fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Line dataKey="x" name="Perfect calibration" stroke="#6f7d96" strokeDasharray="4 4" dot={false} />
                    <Line dataKey="observed" name="Observed ready rate" stroke="#5eead4" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
              <p className="mt-2 text-xs text-fg-faint">Criterion: {m.calibration.criterion}</p>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Model selection" description={m.model_selection.rule} />
            <CardBody>
              <div className="h-56">
                <ResponsiveContainer>
                  <BarChart data={candidates}>
                    <CartesianGrid stroke="#1a2338" vertical={false} />
                    <XAxis dataKey="name" tick={{ fill: "#a3b0c6", fontSize: 11 }} />
                    <YAxis domain={[0, 1]} tick={{ fill: "#6f7d96", fontSize: 11 }} />
                    <Tooltip contentStyle={tooltipStyle} />
                    <Bar dataKey="pr_auc" name="CV PR-AUC" fill="#a78bfa" radius={[4, 4, 0, 0]} />
                  </BarChart>
                </ResponsiveContainer>
              </div>
              <p className="text-xs text-fg-faint">Baseline ({m.model_selection.baseline.name}): CV PR-AUC {m.model_selection.baseline.cv_pr_auc_mean.toFixed(3)}</p>
            </CardBody>
          </Card>
        </div>
        <div className="grid gap-5 lg:grid-cols-2">
          <Card>
            <CardHeader title="Global feature attribution" description="Mean |SHAP| on the test split." />
            <CardBody>
              <ul className="space-y-2">
                {m.global_importance.slice(0, 10).map((g) => {
                  const max = m.global_importance[0]!.mean_abs_shap;
                  return (
                    <li key={g.feature} className="text-sm">
                      <div className="mb-1 flex justify-between"><span className="text-fg-muted">{g.label}</span><span className="metric text-xs text-fg-faint">{g.mean_abs_shap.toFixed(3)}</span></div>
                      <div className="h-1.5 rounded-full bg-white/[0.05]"><div className="h-full rounded-full bg-iris" style={{ width: `${(g.mean_abs_shap / max) * 100}%` }} /></div>
                    </li>
                  );
                })}
              </ul>
            </CardBody>
          </Card>
          <Card>
            <CardHeader title="Subgroup performance" description={m.fairness_note} />
            <CardBody>
              {m.fairness ? (
                <>
                  <div className="overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">{m.fairness.group_column}</th><th className="pb-2">n</th><th className="pb-2">TPR</th><th className="pb-2">FPR</th><th className="pb-2">ROC-AUC</th><th className="pb-2">ECE</th></tr></thead>
                      <tbody className="divide-y divide-line">
                        {m.fairness.groups.map((g) => (
                          <tr key={g.group}><td className="py-1.5">{g.group}</td><td className="metric">{g.n}</td><td className="metric">{g.tpr?.toFixed(2) ?? "—"}</td><td className="metric">{g.fpr?.toFixed(2) ?? "—"}</td><td className="metric">{g.roc_auc?.toFixed(2) ?? "—"}</td><td className="metric">{g.ece?.toFixed(2) ?? "—"}</td></tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                  <p className="mt-3 text-xs text-fg-faint">Largest gaps: {Object.entries(m.fairness.max_gaps).map(([k, v]) => `${k} ${v.toFixed(2)}`).join(" · ")}. Small groups make these estimates noisy; no claim of being unbiased is made.</p>
                </>
              ) : <p className="text-sm text-fg-muted">No subgroup report for this model.</p>}
            </CardBody>
          </Card>
        </div>
        <Card>
          <CardHeader title="Data, leakage checks and limitations" />
          <CardBody className="grid gap-5 lg:grid-cols-2">
            <div className="space-y-2 text-sm text-fg-muted">
              <p><span className="text-fg">Source:</span> {m.dataset.origin}</p>
              {Object.entries(m.dataset.splits).map(([k, s]) => <p key={k} className="metric text-xs">{k}: {s.rows} rows · {s.students} students · positive rate {s.positive_rate.toFixed(3)}</p>)}
              <p className="pt-2"><span className="text-fg">Leakage checks:</span> students shared between splits {String(m.leakage_checks.students_shared_between_splits)}; shuffled-label CV ROC-AUC {String(m.leakage_checks.shuffled_label_cv_roc_auc)}.</p>
            </div>
            <ul className="space-y-2">{m.limitations.map((l) => <li key={l}><Notice tone="warn">{l}</Notice></li>)}</ul>
          </CardBody>
        </Card>
      </div>
    </div>
  );
}
