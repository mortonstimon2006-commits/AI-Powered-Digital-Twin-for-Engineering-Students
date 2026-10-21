import { useMutation, useQuery } from "@tanstack/react-query";
import { CheckCheck, Download, FileSearch, FileText, GitCompareArrows, Lightbulb, ShieldAlert, Trash2, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ConfirmButton } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, StatusBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError, download } from "@/lib/api";
import { invalidateTwin, qk, queryClient } from "@/lib/queries";
import type { DocumentItem } from "@/lib/types";
import { cn, dateOnly, LEVEL_NAMES, pct } from "@/lib/utils";

const MAX = 5 * 1024 * 1024;
const ACCEPT = ".pdf,.docx,.txt,application/pdf,application/vnd.openxmlformats-officedocument.wordprocessingml.document,text/plain";

interface CompareResult {
  skills: { skill_id: number; skill: string; jd_weight: number; twin_level: number | null; twin_status: string; in_resume: boolean | null; status: "missing" | "claimed" | "demonstrated" }[];
  summary: { total: number; missing: number; claimed_only: number; demonstrated: number };
  closest_roles: { role_id: number; role_name: string; jd_overlap: number }[];
  note: string;
}

function UploadZone({ onUploaded }: { onUploaded: (d: DocumentItem) => void }) {
  const input = useRef<HTMLInputElement>(null);
  const [drag, setDrag] = useState(false);
  const [busy, setBusy] = useState(false);
  async function upload(file: File) {
    if (file.size > MAX) return toast.error("Files are limited to 5 MB.");
    if (!/\.(pdf|docx|txt)$/i.test(file.name)) return toast.error("Upload a PDF, DOCX or plain-text file.");
    const form = new FormData();
    form.append("file", file);
    form.append("kind", "resume");
    setBusy(true);
    try {
      const d = await api<DocumentItem>("/documents", { method: "POST", form });
      onUploaded(d);
      toast.success("Resume analysed. Review the suggestions below.");
      void queryClient.invalidateQueries({ queryKey: qk.documents });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Upload failed.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <div
      onDragOver={(e) => { e.preventDefault(); setDrag(true); }} onDragLeave={() => setDrag(false)}
      onDrop={(e) => { e.preventDefault(); setDrag(false); const f = e.dataTransfer.files[0]; if (f) void upload(f); }}
      className={cn("flex flex-col items-center rounded-xl border-2 border-dashed px-6 py-8 text-center transition", drag ? "border-aurora bg-aurora/5" : "border-line")}
    >
      <Upload className="size-6 text-aurora" />
      <p className="mt-2 font-medium">Drop your resume here</p>
      <p className="mt-1 text-xs text-fg-faint">PDF, DOCX or TXT · up to 5 MB · stored privately, auto-deleted after the retention period</p>
      <input ref={input} type="file" accept={ACCEPT} className="sr-only" aria-label="Choose resume file" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
      <Button className="mt-4" variant="secondary" loading={busy} onClick={() => input.current?.click()}>Choose file</Button>
    </div>
  );
}

function ResumeAnalysis({ doc }: { doc: DocumentItem }) {
  const skills = doc.extracted.skills ?? [];
  const [chosen, setChosen] = useState<Record<number, number | null>>({});
  const confirm = useMutation({
    mutationFn: () => api(`/documents/${doc.id}/confirm-skills`, { method: "POST", body: { skills: Object.entries(chosen).filter(([, v]) => v !== null).map(([k, v]) => ({ skill_id: Number(k), self_rating: v })) } }),
    onSuccess: async () => { toast.success("Confirmed skills added as self-reported ratings."); setChosen({}); await invalidateTwin(); void queryClient.invalidateQueries({ queryKey: qk.documents }); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not confirm."),
  });
  const count = Object.values(chosen).filter((v) => v !== null).length;
  return (
    <div className="grid gap-5 lg:grid-cols-[1.3fr_1fr]">
      <Card>
        <CardHeader title="Skills found in your resume" description="Unverified suggestions. Confirm only what is accurate; confirmed skills count as self-reported." />
        <CardBody>
          {doc.extracted.warnings?.map((w) => <Notice key={w} tone="warn" className="mb-3">{w}</Notice>)}
          {skills.length ? (
            <ul className="divide-y divide-line">
              {skills.map((s) => (
                <li key={s.skill_id} className="flex flex-wrap items-center gap-3 py-2.5 text-sm">
                  <div className="min-w-40 flex-1">
                    <p className="font-medium">{s.name}</p>
                    <p className="text-xs text-fg-faint">matched “{s.matched.join("”, “")}” · {s.count}× · {s.sections.join(", ") || "unsectioned"}</p>
                  </div>
                  <Select aria-label={`Confirm ${s.name} with a self-rating`} className="h-8 w-44 text-xs" value={chosen[s.skill_id] ?? ""}
                    onChange={(e) => setChosen((c) => ({ ...c, [s.skill_id]: e.target.value === "" ? null : Number(e.target.value) }))}>
                    <option value="">Don't add</option>
                    {LEVEL_NAMES.map((n, i) => <option key={n} value={i}>Add as {i} · {n}</option>)}
                  </Select>
                </li>
              ))}
            </ul>
          ) : <EmptyState title="No catalogue skills recognised" />}
          <div className="mt-4 flex items-center justify-between">
            <p className="text-xs text-fg-faint">{doc.confirmed_at ? `Last confirmed ${dateOnly(doc.confirmed_at)}` : "Not confirmed yet"}</p>
            <Button onClick={() => confirm.mutate()} disabled={!count} loading={confirm.isPending}><CheckCheck className="size-4" /> Add {count || ""} to my twin</Button>
          </div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Suggestions" description="Deterministic checks — never invented achievements." actions={<Lightbulb className="size-4 text-warn" />} />
        <CardBody className="space-y-2">
          {(doc.extracted.suggestions ?? []).length ? doc.extracted.suggestions!.map((s) => <Notice key={s.code} tone="info">{s.message}</Notice>) : <p className="text-sm text-fg-muted">No issues found by the automated checks.</p>}
          {doc.injection_flags > 0 && <Notice tone="warn" icon={<ShieldAlert className="size-4" />}>{doc.injection_flags} passage(s) looked like instructions to an AI and are withheld from the Personalized Mentor.</Notice>}
          <p className="pt-2 text-xs text-fg-faint">{doc.extracted.word_count} words · {Object.entries(doc.extracted.sections ?? {}).map(([k, v]) => `${k} (${v})`).join(", ")}</p>
        </CardBody>
      </Card>
    </div>
  );
}

export function DocumentsPage() {
  const docs = useQuery({ queryKey: qk.documents, queryFn: () => api<{ items: DocumentItem[] }>("/documents") });
  const [selected, setSelected] = useState<string | null>(null);
  const [jdTitle, setJdTitle] = useState("");
  const [jdText, setJdText] = useState("");
  const [cmpJd, setCmpJd] = useState("");
  const [cmpResume, setCmpResume] = useState("");
  const addJd = useMutation({
    mutationFn: () => api<DocumentItem>("/documents/job-description", { method: "POST", body: { title: jdTitle || "Job description", text: jdText } }),
    onSuccess: (d) => { toast.success("Job description analysed."); setJdText(""); setJdTitle(""); setCmpJd(d.id); void docs.refetch(); },
    onError: (e) => toast.error(e instanceof ApiError ? e.message : "Could not analyse."),
  });
  const compare = useMutation({ mutationFn: () => api<CompareResult>("/documents/compare", { method: "POST", body: { job_description_id: cmpJd, resume_id: cmpResume || null } }) });

  const items = docs.data?.items ?? [];
  const resumes = items.filter((d) => d.kind === "resume");
  const jds = items.filter((d) => d.kind === "job_description");
  const current = items.find((d) => d.id === selected) ?? resumes[0];

  return (
    <div>
      <PageHeader icon={FileText} eyebrow="Documents" title="Resume & job-description analyser"
        description="Extract skills from your resume, get honest writing suggestions, and compare against a job description. Files are private and served only to you." />
      {docs.isLoading ? <LoadingBlock rows={3} /> : docs.error ? <ErrorState error={docs.error} onRetry={() => docs.refetch()} /> : (
        <div className="space-y-5">
          <div className="grid gap-5 lg:grid-cols-2">
            <Card><CardHeader title="Upload a resume" /><CardBody><UploadZone onUploaded={(d) => setSelected(d.id)} /></CardBody></Card>
            <Card>
              <CardHeader title="Add a job description" description="Paste the text of a posting you're interested in." />
              <CardBody className="space-y-3">
                <Field label="Title">{({ id }) => <Input id={id} value={jdTitle} maxLength={160} onChange={(e) => setJdTitle(e.target.value)} placeholder="Junior Data Analyst — Example Co." />}</Field>
                <Field label="Description" hint={`${jdText.length}/20000`}>{({ id, describedBy }) => <Textarea id={id} aria-describedby={describedBy} className="min-h-32" value={jdText} maxLength={20000} onChange={(e) => setJdText(e.target.value)} />}</Field>
                <div className="flex justify-end"><Button onClick={() => addJd.mutate()} loading={addJd.isPending} disabled={jdText.trim().length < 30}><FileSearch className="size-4" /> Analyse</Button></div>
              </CardBody>
            </Card>
          </div>

          <Card>
            <CardHeader title="Your documents" description="Deleting a document removes the file, its analysis and its Personalized Mentor index." />
            <CardBody>
              {items.length ? (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[680px] text-sm">
                    <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Title</th><th className="pb-2">Type</th><th className="pb-2">Status</th><th className="pb-2">Uploaded</th><th className="pb-2">Deleted after</th><th /></tr></thead>
                    <tbody className="divide-y divide-line">
                      {items.map((d) => (
                        <tr key={d.id} className={cn(current?.id === d.id && d.kind === "resume" && "bg-white/[0.02]")}>
                          <td className="py-2"><button type="button" className="text-left hover:text-aurora" onClick={() => d.kind === "resume" && setSelected(d.id)}>{d.title}</button></td>
                          <td><Badge tone={d.kind === "resume" ? "aurora" : "iris"}>{d.kind.replace("_", " ")}</Badge></td>
                          <td><Badge tone={d.status === "indexed" ? "ok" : d.status === "failed" ? "danger" : "muted"}>{d.status}</Badge></td>
                          <td className="text-fg-muted">{dateOnly(d.created_at)}</td>
                          <td className="text-fg-muted">{dateOnly(d.retention_until)}</td>
                          <td className="text-right">
                            {d.original_filename && <Button variant="ghost" size="icon" aria-label={`Download ${d.title}`} onClick={() => download(`/documents/${d.id}/download`, d.original_filename ?? "document")}><Download className="size-4" /></Button>}
                            <ConfirmButton trigger={<Button variant="ghost" size="icon" aria-label={`Delete ${d.title}`}><Trash2 className="size-4" /></Button>}
                              title="Delete this document?" description="The file, its extracted analysis and its Personalized Mentor index are permanently removed." confirmLabel="Delete"
                              onConfirm={async () => { await api(`/documents/${d.id}`, { method: "DELETE" }); await docs.refetch(); }} />
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : <EmptyState icon={<FileText className="size-5" />} title="No documents yet">Upload a resume or paste a job description to start.</EmptyState>}
            </CardBody>
          </Card>

          {current && <ResumeAnalysis key={current.id} doc={current} />}

          {jds.length > 0 && (
            <Card>
              <CardHeader title="Compare with a job description" description="Which of the posting's recognised skills your twin and resume already show." />
              <CardBody className="space-y-4">
                <div className="flex flex-wrap items-end gap-3">
                  <Field label="Job description" className="w-64">{({ id }) => <Select id={id} value={cmpJd} onChange={(e) => setCmpJd(e.target.value)}><option value="">Choose…</option>{jds.map((j) => <option key={j.id} value={j.id}>{j.title}</option>)}</Select>}</Field>
                  <Field label="Resume (optional)" className="w-64">{({ id }) => <Select id={id} value={cmpResume} onChange={(e) => setCmpResume(e.target.value)}><option value="">None</option>{resumes.map((r) => <option key={r.id} value={r.id}>{r.title}</option>)}</Select>}</Field>
                  <Button onClick={() => compare.mutate()} disabled={!cmpJd} loading={compare.isPending}><GitCompareArrows className="size-4" /> Compare</Button>
                </div>
                {compare.error && <ErrorState error={compare.error} />}
                {compare.data && (
                  <div className="space-y-4">
                    <div className="flex flex-wrap gap-2"><Badge tone="danger">{compare.data.summary.missing} missing</Badge><Badge tone="warn">{compare.data.summary.claimed_only} claimed only</Badge><Badge tone="ok">{compare.data.summary.demonstrated} demonstrated</Badge></div>
                    <div className="overflow-x-auto">
                      <table className="w-full min-w-[560px] text-sm">
                        <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Skill</th><th className="pb-2">JD emphasis</th><th className="pb-2">Your twin</th><th className="pb-2">In resume</th><th className="pb-2">Status</th></tr></thead>
                        <tbody className="divide-y divide-line">
                          {compare.data.skills.map((s) => (
                            <tr key={s.skill_id}><td className="py-2">{s.skill}</td><td className="metric">{s.jd_weight}</td><td><StatusBadge status={s.twin_status} /></td>
                              <td>{s.in_resume === null ? "—" : s.in_resume ? "yes" : "no"}</td>
                              <td><Badge tone={s.status === "missing" ? "danger" : s.status === "claimed" ? "warn" : "ok"}>{s.status}</Badge></td></tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    <p className="text-sm text-fg-muted">Closest catalogue roles to this posting: {compare.data.closest_roles.map((r) => `${r.role_name} (${pct(r.jd_overlap)} overlap)`).join(", ")}.</p>
                    <p className="text-xs text-fg-faint">{compare.data.note}</p>
                  </div>
                )}
              </CardBody>
            </Card>
          )}
        </div>
      )}
    </div>
  );
}
