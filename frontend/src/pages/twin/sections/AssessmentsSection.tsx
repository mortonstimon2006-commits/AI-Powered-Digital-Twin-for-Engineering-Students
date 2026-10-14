import { ClipboardList, Plus, Trash2 } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ConfirmButton, Dialog } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, VerificationBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, useAssessments } from "@/lib/queries";
import { dateOnly } from "@/lib/utils";

export function AssessmentsSection() {
  const data = useAssessments();
  const [open, setOpen] = useState(false);
  const [assessmentId, setAssessmentId] = useState("");
  const [score, setScore] = useState("");
  const [takenOn, setTakenOn] = useState("");
  const [notes, setNotes] = useState("");
  const [busy, setBusy] = useState(false);
  if (data.isLoading) return <LoadingBlock rows={3} />;
  if (data.error) return <ErrorState error={data.error} onRetry={() => data.refetch()} />;
  const selected = data.data!.catalogue.find((a) => String(a.id) === assessmentId);
  async function save() {
    setBusy(true);
    try {
      await api("/twin/assessments", { method: "POST", body: { assessment_id: Number(assessmentId), score: Number(score), taken_on: takenOn, notes } });
      await invalidateTwin();
      toast.success("Result recorded as self-reported (unverified).");
      setOpen(false);
      setScore("");
      setNotes("");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not save.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="grid gap-5 lg:grid-cols-[1.4fr_1fr]">
      <Card>
        <CardHeader title="Assessment results" description="Mentor-recorded results are verified and carry the highest trust."
          actions={<Button variant="secondary" onClick={() => setOpen(true)}><Plus className="size-4" /> Self-report a result</Button>} />
        <CardBody>
          {data.data!.results.length ? (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2 font-medium">Assessment</th><th className="pb-2 font-medium">Score</th><th className="pb-2 font-medium">Date</th><th className="pb-2 font-medium">Source</th><th className="pb-2 font-medium">Status</th><th /></tr></thead>
                <tbody className="divide-y divide-line">
                  {data.data!.results.map((r) => (
                    <tr key={r.id}>
                      <td className="py-2.5">{r.assessment_name}</td>
                      <td className="metric py-2.5">{r.score}/{r.max_score} <span className="text-fg-faint">({r.pct}%)</span></td>
                      <td className="py-2.5 text-fg-muted">{dateOnly(r.taken_on)}</td>
                      <td className="py-2.5"><Badge tone={r.source === "mentor_recorded" ? "ok" : "muted"}>{r.source.replace("_", " ")}</Badge></td>
                      <td className="py-2.5"><VerificationBadge status={r.verification_status} /></td>
                      <td className="py-2.5 text-right">
                        {r.source === "self_reported" && (
                          <ConfirmButton trigger={<Button variant="ghost" size="icon" aria-label="Delete result"><Trash2 className="size-4" /></Button>}
                            title="Delete this result?" description="Only self-reported results can be removed by you." confirmLabel="Delete"
                            onConfirm={async () => { await api(`/twin/assessments/${r.id}`, { method: "DELETE" }); await invalidateTwin(); }} />
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <EmptyState icon={<ClipboardList className="size-5" />} title="No assessment results">
              Ask your mentor to run an assessment. Verified results move a skill from "self-reported" to "assessed".
            </EmptyState>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Available assessments" description="Definitions maintained by administrators." />
        <CardBody>
          <ul className="space-y-3">
            {data.data!.catalogue.map((a) => (
              <li key={a.id} className="rounded-lg border border-line p-3">
                <p className="text-sm font-medium">{a.name}</p>
                <p className="mt-0.5 text-xs text-fg-muted">{a.description}</p>
                <p className="mt-1.5 text-xs text-fg-faint">Measures: {a.skills.join(", ")}</p>
              </li>
            ))}
          </ul>
        </CardBody>
      </Card>
      <Dialog open={open} onOpenChange={setOpen} title="Self-report an assessment result">
        <div className="space-y-4">
          <Notice tone="warn">Self-reported results are stored as <strong>unverified</strong> and do not count as "assessed" until a mentor verifies them.</Notice>
          <Field label="Assessment">{({ id }) => (
            <Select id={id} value={assessmentId} onChange={(e) => setAssessmentId(e.target.value)}>
              <option value="">Choose…</option>
              {data.data!.catalogue.map((a) => <option key={a.id} value={a.id}>{a.name}</option>)}
            </Select>)}
          </Field>
          <div className="grid grid-cols-2 gap-3">
            <Field label={`Score${selected ? ` (max ${selected.max_score})` : ""}`}>{({ id }) => <Input id={id} type="number" min={0} max={selected?.max_score} value={score} onChange={(e) => setScore(e.target.value)} />}</Field>
            <Field label="Taken on">{({ id }) => <Input id={id} type="date" value={takenOn} onChange={(e) => setTakenOn(e.target.value)} max={new Date().toISOString().slice(0, 10)} />}</Field>
          </div>
          <Field label="Notes">{({ id }) => <Textarea id={id} value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
          <div className="flex justify-end gap-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button onClick={save} loading={busy} disabled={!assessmentId || score === "" || !takenOn}>Save</Button>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
