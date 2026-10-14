import { useMutation, useQuery } from "@tanstack/react-query";
import { Check, ClipboardCheck, Search, X } from "lucide-react";
import { useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { TabPanel, Tabs } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, LevelMeter, Meter, StatusBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { BAND_META, pct } from "@/lib/utils";

interface Student { id: string; display_name: string; email: string }
interface Overview {
  student: { id: string; display_name: string };
  profile: Record<string, unknown>;
  completeness: { overall: number };
  skills: { skill: string; level: number | null; status: string }[];
  gaps: { role: string; match: number; match_upper: number; top: { skill: string; action: string; required: number; estimate: number | null; status: string }[] } | null;
  latest_readiness: { band: string; probability: number | null; created_at: string } | null;
  pending_verifications: { item_type: string; item_id: string; title: string }[];
  projects: { id: string; title: string; repo_url: string | null; verification_status: string }[];
}

const RUBRIC = ["technical_depth", "problem_solving", "communication", "evidence_quality"] as const;

function StudentPanel({ id }: { id: string }) {
  const ov = useQuery({ queryKey: ["staff", "overview", id], queryFn: () => api<Overview>(`/staff/students/${id}/overview`) });
  const assessments = useQuery({ queryKey: ["staff", "assessments"], queryFn: () => api<{ items: { id: number; name: string; max_score: number }[] }>("/staff/assessments") });
  const [a, setA] = useState({ assessment_id: "", score: "", taken_on: "", notes: "" });
  const [label, setLabel] = useState<"ready" | "not_ready">("not_ready");
  const [rubric, setRubric] = useState<Record<string, number>>({});
  const [notes, setNotes] = useState("");
  const record = useMutation({
    mutationFn: () => api(`/staff/students/${id}/assessments`, { method: "POST", body: { assessment_id: Number(a.assessment_id), score: Number(a.score), taken_on: a.taken_on, notes: a.notes } }),
    onSuccess: () => { toast.success("Verified assessment recorded."); setA({ assessment_id: "", score: "", taken_on: "", notes: "" }); void ov.refetch(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed."),
  });
  const saveLabel = useMutation({
    mutationFn: () => api(`/staff/students/${id}/readiness-labels`, { method: "POST", body: { label, rubric, notes } }),
    onSuccess: () => { toast.success("Readiness label recorded against the current twin snapshot."); setRubric({}); setNotes(""); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Failed."),
  });
  async function decide(item_type: string, item_id: string, decision: "verified" | "rejected") {
    try {
      await api(`/staff/students/${id}/verify`, { method: "POST", body: { item_type, item_id, decision } });
      toast.success(`Marked ${decision}.`);
      void ov.refetch();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Failed.");
    }
  }
  if (ov.isLoading) return <LoadingBlock rows={4} />;
  if (ov.error) return <ErrorState error={ov.error} />;
  const d = ov.data!;
  const max = assessments.data?.items.find((x) => String(x.id) === a.assessment_id)?.max_score;
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title={d.student.display_name} description={`${String(d.profile.degree ?? "")} ${String(d.profile.specialization ?? "")} · semester ${String(d.profile.current_semester ?? "—")}`} />
        <CardBody className="grid gap-5 md:grid-cols-3">
          <div><p className="eyebrow mb-1">Completeness</p><Meter value={d.completeness.overall} label="Completeness" /><p className="metric mt-1 text-sm">{pct(d.completeness.overall)}</p></div>
          <div><p className="eyebrow mb-1">Target role match</p><p className="text-sm">{d.gaps ? `${d.gaps.role}: ${pct(d.gaps.match)} (≤${pct(d.gaps.match_upper)})` : "No target role"}</p></div>
          <div><p className="eyebrow mb-1">Latest readiness</p><p className="text-sm">{d.latest_readiness ? `${BAND_META[d.latest_readiness.band]?.label} ${d.latest_readiness.probability !== null ? `≈ ${pct(d.latest_readiness.probability)}` : ""}` : "None"}</p></div>
        </CardBody>
      </Card>
      <div className="grid gap-5 lg:grid-cols-2">
        <Card>
          <CardHeader title="Pending verification" description="Check the evidence (repository, certificate) before deciding." />
          <CardBody>
            {d.pending_verifications.length ? (
              <ul className="divide-y divide-line">
                {d.pending_verifications.map((p) => {
                  const proj = d.projects.find((x) => x.id === p.item_id);
                  return (
                    <li key={p.item_id} className="flex flex-wrap items-center gap-2 py-2 text-sm">
                      <Badge tone="info">{p.item_type}</Badge><span className="flex-1">{p.title}</span>
                      {proj?.repo_url && <a className="text-xs text-aurora hover:underline" href={proj.repo_url} target="_blank" rel="noopener noreferrer nofollow">repo</a>}
                      <Button size="sm" variant="subtle" onClick={() => decide(p.item_type, p.item_id, "verified")}><Check className="size-3.5" /> Verify</Button>
                      <Button size="sm" variant="ghost" onClick={() => decide(p.item_type, p.item_id, "rejected")}><X className="size-3.5" /> Reject</Button>
                    </li>
                  );
                })}
              </ul>
            ) : <p className="text-sm text-fg-muted">Nothing pending.</p>}
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Top gaps" />
          <CardBody>
            <ul className="space-y-2 text-sm">
              {d.gaps?.top.map((g) => <li key={g.skill} className="flex items-center gap-3"><span className="flex-1">{g.skill}</span><LevelMeter value={g.estimate} required={g.required} status={g.status} /><Badge>{g.action}</Badge></li>)}
            </ul>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Record a verified assessment" description="Recorded results become the student's highest-trust evidence." />
          <CardBody className="space-y-3">
            <Field label="Assessment">{({ id: fid }) => <Select id={fid} value={a.assessment_id} onChange={(e) => setA({ ...a, assessment_id: e.target.value })}><option value="">Choose…</option>{assessments.data?.items.map((x) => <option key={x.id} value={x.id}>{x.name}</option>)}</Select>}</Field>
            <div className="grid grid-cols-2 gap-3">
              <Field label={`Score${max ? ` / ${max}` : ""}`}>{({ id: fid }) => <Input id={fid} type="number" min={0} max={max} value={a.score} onChange={(e) => setA({ ...a, score: e.target.value })} />}</Field>
              <Field label="Taken on">{({ id: fid }) => <Input id={fid} type="date" max={new Date().toISOString().slice(0, 10)} value={a.taken_on} onChange={(e) => setA({ ...a, taken_on: e.target.value })} />}</Field>
            </div>
            <Field label="Notes">{({ id: fid }) => <Textarea id={fid} className="min-h-16" value={a.notes} onChange={(e) => setA({ ...a, notes: e.target.value })} />}</Field>
            <div className="flex justify-end"><Button onClick={() => record.mutate()} loading={record.isPending} disabled={!a.assessment_id || a.score === "" || !a.taken_on}>Record</Button></div>
          </CardBody>
        </Card>
        <Card>
          <CardHeader title="Assessor readiness label" description="Your structured judgement, frozen against the current twin snapshot. Used for future model training only if the student grants research use." />
          <CardBody className="space-y-3">
            <div className="flex gap-2" role="radiogroup" aria-label="Readiness label">
              {(["not_ready", "ready"] as const).map((v) => <Button key={v} variant={label === v ? "subtle" : "secondary"} role="radio" aria-checked={label === v} onClick={() => setLabel(v)}>{v === "ready" ? "Interview-ready" : "Not yet ready"}</Button>)}
            </div>
            <div className="grid grid-cols-2 gap-3">
              {RUBRIC.map((r) => (
                <Field key={r} label={r.replace("_", " ")}>{({ id: fid }) => (
                  <Select id={fid} value={rubric[r] ?? ""} onChange={(e) => setRubric((x) => ({ ...x, [r]: Number(e.target.value) }))}>
                    <option value="">—</option>{[1, 2, 3, 4, 5].map((n) => <option key={n} value={n}>{n}</option>)}
                  </Select>)}
                </Field>
              ))}
            </div>
            <Field label="Notes">{({ id: fid }) => <Textarea id={fid} className="min-h-16" value={notes} onChange={(e) => setNotes(e.target.value)} />}</Field>
            <div className="flex justify-end"><Button onClick={() => saveLabel.mutate()} loading={saveLabel.isPending}>Record label</Button></div>
          </CardBody>
        </Card>
      </div>
      <Card>
        <CardHeader title="Known skills" />
        <CardBody>
          <ul className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {d.skills.map((s) => <li key={s.skill} className="flex items-center justify-between gap-2 rounded-lg border border-line px-3 py-2 text-sm"><span>{s.skill}</span><StatusBadge status={s.status} /></li>)}
          </ul>
        </CardBody>
      </Card>
    </div>
  );
}

export function StaffPage() {
  const [search, setSearch] = useState("");
  const [selected, setSelected] = useState<string | null>(null);
  const [tab, setTab] = useState("students");
  const students = useQuery({ queryKey: ["staff", "students", search], queryFn: () => api<{ items: Student[] }>("/staff/students", { query: { search } }) });
  const queue = useQuery({ queryKey: ["staff", "queue"], queryFn: () => api<{ items: { student_id: string; student: string; item_type: string; item_id: string; title: string }[] }>("/staff/verification-queue"), enabled: tab === "queue" });
  return (
    <div>
      <PageHeader icon={ClipboardCheck} eyebrow="Mentor tools" title="Assess and verify"
        description="You can see a student only while you are assigned to them and they grant mentor sharing. Every view and action is audited." />
      <Tabs value={tab} onValueChange={setTab} items={[{ value: "students", label: "Students" }, { value: "queue", label: "Verification queue", count: queue.data?.items.length }]}>
        <div className="pt-6">
          <TabPanel value="students">
            <div className="grid gap-5 lg:grid-cols-[280px_1fr]">
              <Card className="h-fit p-3">
                <div className="relative mb-3"><Search className="pointer-events-none absolute left-2.5 top-1/2 size-4 -translate-y-1/2 text-fg-faint" /><Input aria-label="Search students" className="pl-8" placeholder="Search" value={search} onChange={(e) => setSearch(e.target.value)} /></div>
                {students.isLoading ? <LoadingBlock rows={2} /> : students.data?.items.length ? (
                  <ul className="space-y-1">{students.data.items.map((s) => (
                    <li key={s.id}><button type="button" onClick={() => setSelected(s.id)} className={`w-full rounded-lg px-3 py-2 text-left text-sm ${selected === s.id ? "bg-white/[0.06]" : "hover:bg-white/[0.03]"}`}>
                      <span className="block">{s.display_name}</span><span className="block truncate text-xs text-fg-faint">{s.email}</span></button></li>
                  ))}</ul>
                ) : <p className="p-2 text-sm text-fg-muted">No accessible students. Students appear when an administrator assigns them and they grant mentor sharing.</p>}
              </Card>
              {selected ? <StudentPanel key={selected} id={selected} /> : <EmptyState icon={<ClipboardCheck className="size-5" />} title="Select a student" />}
            </div>
          </TabPanel>
          <TabPanel value="queue">
            <Card>
              <CardHeader title="Pending verification across your students" />
              <CardBody>
                {queue.isLoading ? <LoadingBlock rows={2} /> : queue.data?.items.length ? (
                  <ul className="divide-y divide-line">{queue.data.items.map((q) => (
                    <li key={q.item_id} className="flex flex-wrap items-center gap-3 py-2 text-sm"><Badge tone="info">{q.item_type}</Badge><span className="flex-1">{q.title}</span><span className="text-fg-muted">{q.student}</span>
                      <Button size="sm" variant="secondary" onClick={() => { setSelected(q.student_id); setTab("students"); }}>Review</Button></li>
                  ))}</ul>
                ) : <Notice tone="ok">Nothing waiting for verification.</Notice>}
              </CardBody>
            </Card>
          </TabPanel>
        </div>
      </Tabs>
    </div>
  );
}
