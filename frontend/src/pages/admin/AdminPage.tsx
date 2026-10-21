import { useMutation, useQuery } from "@tanstack/react-query";
import { Activity, Database, LinkIcon, MessageSquareText, RefreshCw, ShieldCheck, Upload } from "lucide-react";
import { useRef, useState } from "react";
import { toast } from "sonner";

import { FEEDBACK_AREAS } from "@/components/FeedbackButton";
import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ConfirmButton, TabPanel, Tabs } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, Stat } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { queryClient, useRoles } from "@/lib/queries";
import type { CareerRole, Requirement } from "@/lib/types";
import { cn, dateTime, LEVEL_NAMES } from "@/lib/utils";

const err = (e: unknown) => toast.error(e instanceof ApiError ? e.message : "Request failed.");

function SystemTab() {
  const q = useQuery({ queryKey: ["admin", "system"], queryFn: () => api<{
    database: string; readiness_model: { available: boolean; version: string | null; reason_unavailable: string | null };
    ollama: { reachable: boolean; ollama_version?: string; chat_model?: string; chat_model_available?: boolean; chat_model_quantization?: string; embed_model?: string; embed_model_available?: boolean; num_ctx?: number; loaded?: { name: string; size_vram_mb: number; context_length: number }[] };
    mentor_queue: Record<string, number | null>; vector_store: Record<string, number>; counts: Record<string, number>; environment: string;
  }>("/admin/system"), refetchInterval: 20_000 });
  const retention = useMutation({ mutationFn: () => api<Record<string, number>>("/admin/retention/run", { method: "POST" }), onSuccess: (r) => toast.success(`Retention applied: ${Object.entries(r).map(([k, v]) => `${k} ${v}`).join(", ")}`), onError: err });
  const reindex = useMutation({ mutationFn: () => api<{ chunks: number }>("/admin/knowledge/reindex", { method: "POST" }), onSuccess: (r) => toast.success(`Knowledge base re-indexed (${r.chunks} chunks).`), onError: err });
  if (q.isLoading) return <LoadingBlock rows={3} />;
  if (q.error) return <ErrorState error={q.error} />;
  const s = q.data!;
  const ok = (v: boolean | undefined) => <Badge tone={v ? "ok" : "danger"}>{v ? "ok" : "unavailable"}</Badge>;
  return (
    <div className="grid gap-5 lg:grid-cols-3">
      <Card><CardHeader title="Core services" actions={<Badge tone="muted">{s.environment}</Badge>} />
        <CardBody className="space-y-2 text-sm">
          <p className="flex justify-between">Database {ok(s.database === "ok")}</p>
          <p className="flex justify-between">Readiness model {ok(s.readiness_model.available)}</p>
          <p className="font-mono text-xs text-fg-faint">{s.readiness_model.version ?? s.readiness_model.reason_unavailable}</p>
          <p className="flex justify-between">Vector store <span className="metric text-xs">{s.vector_store.global_chunks} global · {s.vector_store.private_chunks} private chunks</span></p>
        </CardBody></Card>
      <Card><CardHeader title="Local LLM (Ollama)" actions={ok(s.ollama.reachable)} />
        <CardBody className="space-y-2 text-sm">
          <p className="flex justify-between">Chat model <span>{s.ollama.chat_model} {ok(s.ollama.chat_model_available)}</span></p>
          <p className="flex justify-between">Quantization <span className="metric">{s.ollama.chat_model_quantization ?? "—"}</span></p>
          <p className="flex justify-between">Embeddings <span>{s.ollama.embed_model} {ok(s.ollama.embed_model_available)}</span></p>
          <p className="flex justify-between">Context window <span className="metric">{s.ollama.num_ctx}</span></p>
          {(s.ollama.loaded ?? []).map((m) => <p key={m.name} className="font-mono text-xs text-fg-faint">loaded: {m.name} · {m.size_vram_mb} MB VRAM · ctx {m.context_length}</p>)}
          <p className="font-mono text-xs text-fg-faint">queue: active {s.mentor_queue.active} · waiting {s.mentor_queue.waiting} · completed {s.mentor_queue.completed} · failed {s.mentor_queue.failed}</p>
        </CardBody></Card>
      <Card><CardHeader title="Data" />
        <CardBody className="grid grid-cols-2 gap-4">{Object.entries(s.counts).map(([k, v]) => <Stat key={k} label={k.replaceAll("_", " ")} value={v} />)}</CardBody></Card>
      <Card className="lg:col-span-3"><CardHeader title="Maintenance" />
        <CardBody className="flex flex-wrap gap-3">
          <ConfirmButton destructive trigger={<Button variant="secondary"><Database className="size-4" /> Apply retention policy</Button>} title="Apply data retention now?"
            description="Expired documents, old Personalized Mentor conversations, sessions and tokens are permanently deleted." confirmLabel="Apply" onConfirm={() => retention.mutateAsync()} />
          <Button variant="secondary" onClick={() => reindex.mutate()} loading={reindex.isPending}><RefreshCw className="size-4" /> Re-index knowledge base</Button>
        </CardBody></Card>
    </div>
  );
}

function UsersTab() {
  const [search, setSearch] = useState("");
  const [offset, setOffset] = useState(0);
  const users = useQuery({ queryKey: ["admin", "users", search, offset], queryFn: () => api<{ items: { id: string; email: string; display_name: string; role: string; is_active: boolean; mfa_enabled: boolean; last_login_at: string | null }[]; total: number }>("/admin/users", { query: { search, offset, limit: 25 } }) });
  async function patch(id: string, body: Record<string, unknown>) {
    try { await api(`/admin/users/${id}`, { method: "PATCH", body }); toast.success("User updated; their sessions were revoked."); void users.refetch(); } catch (e) { err(e); }
  }
  return (
    <Card>
      <CardHeader title="Users" description="Role or status changes revoke the user's sessions immediately." actions={<Input aria-label="Search users" className="w-56" placeholder="Search email or name" value={search} onChange={(e) => { setSearch(e.target.value); setOffset(0); }} />} />
      <CardBody>
        {users.isLoading ? <LoadingBlock rows={3} /> : users.error ? <ErrorState error={users.error} /> : (
          <>
            <div className="overflow-x-auto">
              <table className="w-full min-w-[720px] text-sm">
                <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">User</th><th className="pb-2">Role</th><th className="pb-2">MFA</th><th className="pb-2">Last login</th><th className="pb-2">Active</th></tr></thead>
                <tbody className="divide-y divide-line">
                  {users.data!.items.map((u) => (
                    <tr key={u.id}>
                      <td className="py-2"><span className="block">{u.display_name}</span><span className="text-xs text-fg-faint">{u.email}</span></td>
                      <td><Select aria-label={`Role for ${u.email}`} className="h-8 w-32 text-xs" value={u.role} onChange={(e) => patch(u.id, { role: e.target.value })}><option value="student">student</option><option value="mentor">mentor</option><option value="admin">admin</option></Select></td>
                      <td>{u.mfa_enabled ? <Badge tone="ok">on</Badge> : <Badge>off</Badge>}</td>
                      <td className="text-fg-muted">{u.last_login_at ? dateTime(u.last_login_at) : "—"}</td>
                      <td><ConfirmButton destructive={u.is_active} trigger={<Button size="sm" variant={u.is_active ? "ghost" : "subtle"}>{u.is_active ? "Deactivate" : "Reactivate"}</Button>}
                        title={u.is_active ? "Deactivate this account?" : "Reactivate this account?"} description="Sessions are revoked; the user's data is kept." confirmLabel="Confirm" onConfirm={() => patch(u.id, { is_active: !u.is_active })} /></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <div className="mt-3 flex items-center justify-between text-sm text-fg-muted">
              <span>{users.data!.total} users</span>
              <div className="flex gap-2"><Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 25))}>Previous</Button><Button size="sm" variant="secondary" disabled={offset + 25 >= users.data!.total} onClick={() => setOffset(offset + 25)}>Next</Button></div>
            </div>
          </>
        )}
      </CardBody>
    </Card>
  );
}

function LinksTab() {
  const links = useQuery({ queryKey: ["admin", "links"], queryFn: () => api<{ items: { mentor_id: string; mentor: string; student_id: string; student: string | null; created_at: string }[] }>("/admin/mentor-links") });
  const mentors = useQuery({ queryKey: ["admin", "users", "mentors"], queryFn: () => api<{ items: { id: string; email: string; display_name: string }[] }>("/admin/users", { query: { role: "mentor", limit: 200 } }) });
  const students = useQuery({ queryKey: ["admin", "users", "students"], queryFn: () => api<{ items: { id: string; email: string; display_name: string }[] }>("/admin/users", { query: { role: "student", limit: 200 } }) });
  const [m, setM] = useState("");
  const [s, setS] = useState("");
  return (
    <Card>
      <CardHeader title="Mentor assignments" description="A mentor gains access only while the student also grants mentor sharing." />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Mentor" className="w-64">{({ id }) => <Select id={id} value={m} onChange={(e) => setM(e.target.value)}><option value="">Choose…</option>{mentors.data?.items.map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}</Select>}</Field>
          <Field label="Student" className="w-64">{({ id }) => <Select id={id} value={s} onChange={(e) => setS(e.target.value)}><option value="">Choose…</option>{students.data?.items.map((u) => <option key={u.id} value={u.id}>{u.display_name} ({u.email})</option>)}</Select>}</Field>
          <Button disabled={!m || !s} onClick={async () => { try { await api("/admin/mentor-links", { method: "POST", body: { mentor_id: m, student_id: s } }); toast.success("Assigned."); void links.refetch(); } catch (e) { err(e); } }}>Assign</Button>
        </div>
        <ul className="divide-y divide-line text-sm">
          {links.data?.items.map((l) => (
            <li key={l.mentor_id + l.student_id} className="flex items-center gap-3 py-2"><span className="flex-1">{l.mentor} → {l.student}</span><span className="text-xs text-fg-faint">{dateTime(l.created_at)}</span>
              <Button size="sm" variant="ghost" onClick={async () => { await api(`/admin/mentor-links/${l.mentor_id}/${l.student_id}`, { method: "DELETE" }); void links.refetch(); }}>Remove</Button></li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

function RoleEditor({ role }: { role: CareerRole }) {
  const [reqs, setReqs] = useState<Requirement[]>(role.requirements);
  const [note, setNote] = useState(role.source_note);
  const save = useMutation({
    mutationFn: () => api<{ version: number }>(`/admin/roles/${role.id}`, { method: "PUT", body: { slug: role.slug, name: role.name, summary: role.summary, description: role.description, source_note: note,
      requirements: reqs.map((q) => ({ skill_id: q.skill_id, required_level: q.required_level, importance: q.importance, is_core: q.is_core, evidence_expected: q.evidence_expected, alt_group: q.alt_group, rationale: q.rationale })) } }),
    onSuccess: (r) => { toast.success(`Saved as version ${r.version}. Students' roadmaps will show as stale.`); void queryClient.invalidateQueries({ queryKey: ["roles"] }); },
    onError: err,
  });
  const set = (i: number, patch: Partial<Requirement>) => setReqs((r) => r.map((q, j) => (j === i ? { ...q, ...patch } : q)));
  return (
    <div className="space-y-4">
      <Notice tone="info">Every save creates a new immutable version (currently v{role.version}). Document the reason for changes in the provenance note.</Notice>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[820px] text-sm">
          <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Skill</th><th className="pb-2">Level</th><th className="pb-2">Importance</th><th className="pb-2">Core</th><th className="pb-2">Evidence</th><th className="pb-2">Rationale</th><th /></tr></thead>
          <tbody className="divide-y divide-line">
            {reqs.map((q, i) => (
              <tr key={q.skill_id}>
                <td className="py-1.5">{q.skill_name}</td>
                <td><Select aria-label="Level" className="h-8 w-28 text-xs" value={q.required_level} onChange={(e) => set(i, { required_level: Number(e.target.value) })}>{[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} {LEVEL_NAMES[n]}</option>)}</Select></td>
                <td><Input aria-label="Importance" className="h-8 w-20 text-xs" type="number" min={0.05} max={1} step={0.05} value={q.importance} onChange={(e) => set(i, { importance: Number(e.target.value) })} /></td>
                <td><input type="checkbox" aria-label="Core requirement" className="size-4 accent-[#5eead4]" checked={q.is_core} onChange={(e) => set(i, { is_core: e.target.checked })} /></td>
                <td><Select aria-label="Evidence expected" className="h-8 w-28 text-xs" value={q.evidence_expected} onChange={(e) => set(i, { evidence_expected: e.target.value })}><option value="any">any</option><option value="project">project</option><option value="assessment">assessment</option></Select></td>
                <td><Input aria-label="Rationale" className="h-8 text-xs" value={q.rationale} onChange={(e) => set(i, { rationale: e.target.value })} /></td>
                <td><Button variant="ghost" size="sm" onClick={() => setReqs((r) => r.filter((_, j) => j !== i))}>Remove</Button></td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <Field label="Provenance / source note">{({ id }) => <Textarea id={id} value={note} onChange={(e) => setNote(e.target.value)} />}</Field>
      <div className="flex justify-end"><Button onClick={() => save.mutate()} loading={save.isPending}>Save new version</Button></div>
    </div>
  );
}

function RolesTab() {
  const roles = useRoles();
  const [id, setId] = useState<number | null>(null);
  const role = roles.data?.roles.find((r) => r.id === id) ?? roles.data?.roles[0];
  return (
    <Card>
      <CardHeader title="Role catalogue" actions={<Select aria-label="Role" className="w-56" value={role?.id ?? ""} onChange={(e) => setId(Number(e.target.value))}>{roles.data?.roles.map((r) => <option key={r.id} value={r.id}>{r.name} (v{r.version})</option>)}</Select>} />
      <CardBody>{role ? <RoleEditor key={`${role.id}-${role.version}`} role={role} /> : <LoadingBlock rows={3} />}</CardBody>
    </Card>
  );
}

function ResourcesTab() {
  const res = useQuery({ queryKey: ["admin", "resources"], queryFn: () => api<{ items: { id: number; title: string; provider: string; url: string; type: string; verification_status: string; last_checked_at: string | null; last_http_status: number | null; is_active: boolean }[] }>("/admin/resources") });
  const validate = useMutation({ mutationFn: () => api<{ items: { status: string }[] }>("/admin/resources/validate", { method: "POST", body: {} }),
    onSuccess: (r) => { const c: Record<string, number> = {}; r.items.forEach((i) => (c[i.status] = (c[i.status] ?? 0) + 1)); toast.success(`Checked: ${Object.entries(c).map(([k, v]) => `${v} ${k}`).join(", ")}`); void res.refetch(); }, onError: err });
  return (
    <Card>
      <CardHeader title="Learning resources" description="Links are only labelled verified after an automated check succeeds; bot-blocked sites stay unverified."
        actions={<Button variant="secondary" onClick={() => validate.mutate()} loading={validate.isPending}><LinkIcon className="size-4" /> Validate all links</Button>} />
      <CardBody>
        {res.isLoading ? <LoadingBlock rows={3} /> : (
          <div className="overflow-x-auto">
            <table className="w-full min-w-[760px] text-sm">
              <thead className="text-left text-xs text-fg-faint"><tr><th className="pb-2">Resource</th><th className="pb-2">Type</th><th className="pb-2">Status</th><th className="pb-2">Checked</th><th /></tr></thead>
              <tbody className="divide-y divide-line">
                {res.data?.items.map((r) => (
                  <tr key={r.id} className={r.is_active ? "" : "opacity-50"}>
                    <td className="py-2"><a href={r.url} target="_blank" rel="noopener noreferrer nofollow" className="hover:text-aurora">{r.title}</a><span className="block text-xs text-fg-faint">{r.provider}</span></td>
                    <td className="text-fg-muted">{r.type}</td>
                    <td><Badge tone={r.verification_status === "verified" ? "ok" : r.verification_status === "broken" ? "danger" : "warn"}>{r.verification_status}{r.last_http_status ? ` ${r.last_http_status}` : ""}</Badge></td>
                    <td className="text-xs text-fg-faint">{r.last_checked_at ? dateTime(r.last_checked_at) : "never"}</td>
                    <td>{r.is_active && <Button size="sm" variant="ghost" onClick={async () => { await api(`/admin/resources/${r.id}`, { method: "DELETE" }); void res.refetch(); }}>Deactivate</Button>}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </CardBody>
    </Card>
  );
}

function ModelsTab() {
  const models = useQuery({ queryKey: ["admin", "models"], queryFn: () => api<{ active: { version: string | null }; items: { id: number; version: string; algorithm: string; status: string; is_synthetic: boolean; metrics: { test?: Record<string, number> }; trained_at: string }[] }>("/admin/models") });
  async function act(id: number, action: "activate" | "retire") {
    try { await api(`/admin/models/${id}/${action}`, { method: "POST" }); toast.success(`Model ${action}d.`); void models.refetch(); void queryClient.invalidateQueries({ queryKey: ["readiness"] }); } catch (e) { err(e); }
  }
  return (
    <Card>
      <CardHeader title="Model versions" description="Activation re-verifies the artifact checksum, feature schema and library versions before switching." />
      <CardBody>
        {models.isLoading ? <LoadingBlock rows={2} /> : (
          <ul className="divide-y divide-line">
            {models.data?.items.map((m) => (
              <li key={m.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                <Badge tone={m.status === "active" ? "ok" : m.status === "candidate" ? "info" : "muted"}>{m.status}</Badge>
                <span className="font-mono text-xs">{m.version}</span>
                {m.is_synthetic && <Badge tone="iris">synthetic data</Badge>}
                <span className="metric text-xs text-fg-muted">PR-AUC {m.metrics.test?.pr_auc?.toFixed(3)} · ROC-AUC {m.metrics.test?.roc_auc?.toFixed(3)} · ECE {m.metrics.test?.ece?.toFixed(3)}</span>
                <span className="ml-auto flex gap-2">
                  {m.status !== "active" && <ConfirmButton destructive={false} trigger={<Button size="sm" variant="secondary">Activate</Button>} title="Activate this model?" description="All new readiness estimates will use it; existing estimates keep their recorded version." confirmLabel="Activate" onConfirm={() => act(m.id, "activate")} />}
                  {m.status === "active" && <ConfirmButton trigger={<Button size="sm" variant="ghost">Retire</Button>} title="Retire the active model?" description="Readiness estimates become unavailable until another model is activated." confirmLabel="Retire" onConfirm={() => act(m.id, "retire")} />}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardBody>
    </Card>
  );
}

function KnowledgeTab() {
  const kb = useQuery({ queryKey: ["admin", "kb"], queryFn: () => api<{ stats: Record<string, number>; items: { id: string; title: string; source: string; status: string; chunks: number; injection_flags: number; error: string | null }[] }>("/admin/knowledge") });
  const file = useRef<HTMLInputElement>(null);
  const [title, setTitle] = useState("");
  async function upload(f: File) {
    const form = new FormData();
    form.append("file", f);
    form.append("title", title || f.name);
    try { const r = await api<{ chunks: number; injection_flags: number }>("/admin/knowledge/upload", { method: "POST", form }); toast.success(`Indexed ${r.chunks} chunks (${r.injection_flags} flagged).`); setTitle(""); void kb.refetch(); } catch (e) { err(e); }
  }
  return (
    <Card>
      <CardHeader title="Knowledge base (global)" description="Only upload documents you have permission to use. Passages that look like instructions to an AI are flagged and excluded from retrieval." />
      <CardBody className="space-y-4">
        <div className="flex flex-wrap items-end gap-3">
          <Field label="Title" className="w-72">{({ id }) => <Input id={id} value={title} onChange={(e) => setTitle(e.target.value)} />}</Field>
          <input ref={file} type="file" accept=".pdf,.docx,.txt,.md" className="sr-only" aria-label="Knowledge document" onChange={(e) => { const f = e.target.files?.[0]; if (f) void upload(f); e.target.value = ""; }} />
          <Button variant="secondary" onClick={() => file.current?.click()}><Upload className="size-4" /> Upload document</Button>
        </div>
        <ul className="divide-y divide-line text-sm">
          {kb.data?.items.map((d) => (
            <li key={d.id} className="flex flex-wrap items-center gap-3 py-2">
              <span className="flex-1">{d.title}<span className="block text-xs text-fg-faint">{d.source}</span></span>
              <Badge tone={d.status === "indexed" ? "ok" : "warn"}>{d.status}</Badge><span className="metric text-xs">{d.chunks} chunks</span>
              {d.injection_flags > 0 && <Badge tone="danger">{d.injection_flags} flagged</Badge>}
              <ConfirmButton trigger={<Button size="sm" variant="ghost">Delete</Button>} title="Remove this document?" description="Its chunks are removed from retrieval." confirmLabel="Remove"
                onConfirm={async () => { await api(`/admin/knowledge/${d.id}`, { method: "DELETE" }); void kb.refetch(); }} />
            </li>
          ))}
        </ul>
      </CardBody>
    </Card>
  );
}

type FeedbackItem = { id: string; created_at: string; target_type: string; target_id: string | null; rating: number; comment: string };

const AREA_LABELS: Record<string, string> = {
  ...Object.fromEntries(FEEDBACK_AREAS),
  roadmap_item: "Roadmap item rating",
  mentor_message: "Personalized Mentor answer rating",
};
const FEEDBACK_PAGE = 50;

function FeedbackTab() {
  const [area, setArea] = useState("");
  const [offset, setOffset] = useState(0);
  // Refreshed every 30 s so new feedback appears while the page is open.
  const list = useQuery({
    queryKey: ["admin", "feedback", "list", area, offset],
    queryFn: () => api<{ total: number; items: FeedbackItem[] }>("/admin/feedback", { query: { target_type: area, limit: FEEDBACK_PAGE, offset } }),
    refetchInterval: 30_000,
  });
  const summary = useQuery({
    queryKey: ["admin", "feedback", "summary"],
    queryFn: () => api<{ items: { target_type: string; count: number; mean_rating: number }[]; note: string }>("/admin/feedback/summary"),
    refetchInterval: 30_000,
  });
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Ratings by area" description={summary.data?.note} />
        <CardBody>
          {summary.isError ? <ErrorState error={summary.error} onRetry={() => summary.refetch()} /> : (summary.data?.items.length ?? 0) === 0 ? (
            <p className="text-sm text-fg-muted">No ratings yet.</p>
          ) : (
            <ul className="grid gap-3 sm:grid-cols-3">{summary.data?.items.map((f) => (
              <li key={f.target_type} className="rounded-lg border border-line p-3">
                <p className="text-sm">{AREA_LABELS[f.target_type] ?? f.target_type}</p>
                <p className="metric text-xl">{f.mean_rating.toFixed(2)}<span className="text-xs text-fg-faint"> / 5 · n={f.count}</span></p>
              </li>
            ))}</ul>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Recent feedback" description={`Newest first, updated every 30 seconds. Shown without names or emails. ${list.data ? `${list.data.total} in total.` : ""}`}
          actions={
            <Select aria-label="Filter feedback by area" className="w-56" value={area} onChange={(e) => { setArea(e.target.value); setOffset(0); }}>
              <option value="">All areas</option>
              {Object.entries(AREA_LABELS).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
            </Select>
          } />
        <CardBody>
          {list.isLoading ? <LoadingBlock rows={3} /> : list.isError ? <ErrorState error={list.error} onRetry={() => list.refetch()} /> : (list.data?.items.length ?? 0) === 0 ? (
            <EmptyState icon={<MessageSquareText className="size-5" aria-hidden />} title="No feedback yet">
              Signed-in users can send feedback from the "Send feedback" button in the sidebar or menu.
            </EmptyState>
          ) : (
            <ul className="divide-y divide-line">
              {list.data?.items.map((f) => (
                <li key={f.id} className="py-3">
                  <div className="flex flex-wrap items-center gap-2 text-xs text-fg-faint">
                    <Badge tone={f.rating >= 4 ? "ok" : f.rating <= 2 ? "danger" : "muted"}>{f.rating} / 5</Badge>
                    <span className="text-fg-muted">{AREA_LABELS[f.target_type] ?? f.target_type}</span>
                    {f.target_id?.startsWith("/") && <span className="font-mono">{f.target_id}</span>}
                    <span className="ml-auto">{dateTime(f.created_at)}</span>
                  </div>
                  <p className={cn("mt-1.5 whitespace-pre-wrap break-words text-sm", !f.comment && "text-fg-faint")}>{f.comment || "No comment"}</p>
                </li>
              ))}
            </ul>
          )}
          <div className="mt-3 flex justify-end gap-2">
            <Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - FEEDBACK_PAGE))}>Newer</Button>
            <Button size="sm" variant="secondary" disabled={offset + FEEDBACK_PAGE >= (list.data?.total ?? 0)} onClick={() => setOffset(offset + FEEDBACK_PAGE)}>Older</Button>
          </div>
        </CardBody>
      </Card>
    </div>
  );
}

function AuditTab() {
  const [action, setAction] = useState("");
  const [offset, setOffset] = useState(0);
  const q = useQuery({ queryKey: ["admin", "audit", action, offset], queryFn: () => api<{ items: { id: number; occurred_at: string; actor_id: string | null; action: string; outcome: string; target_type: string | null; target_id: string | null; ip_prefix: string | null; details: Record<string, unknown> | null }[] }>("/admin/audit", { query: { action, offset, limit: 50 } }) });
  return (
    <div className="space-y-5">
      <Card>
        <CardHeader title="Audit log" description="Append-only. Details are redacted; no credentials or content are recorded." actions={<Input aria-label="Filter by action prefix" className="w-56" placeholder="e.g. auth. or admin." value={action} onChange={(e) => { setAction(e.target.value); setOffset(0); }} />} />
        <CardBody>
          {q.isLoading ? <LoadingBlock rows={3} /> : (
            <div className="overflow-x-auto">
              <table className="w-full min-w-[760px] text-xs">
                <thead className="text-left text-fg-faint"><tr><th className="pb-2">Time</th><th className="pb-2">Action</th><th className="pb-2">Outcome</th><th className="pb-2">Target</th><th className="pb-2">Network</th><th className="pb-2">Details</th></tr></thead>
                <tbody className="divide-y divide-line font-mono">
                  {q.data?.items.map((e) => (
                    <tr key={e.id}><td className="py-1.5">{dateTime(e.occurred_at)}</td><td>{e.action}</td><td><Badge tone={e.outcome === "success" ? "ok" : "danger"}>{e.outcome}</Badge></td>
                      <td>{e.target_type ? `${e.target_type}:${(e.target_id ?? "").slice(0, 8)}` : "—"}</td><td>{e.ip_prefix ?? "—"}</td><td className="max-w-64 truncate">{e.details ? JSON.stringify(e.details) : ""}</td></tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
          <div className="mt-3 flex justify-end gap-2"><Button size="sm" variant="secondary" disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 50))}>Newer</Button><Button size="sm" variant="secondary" disabled={(q.data?.items.length ?? 0) < 50} onClick={() => setOffset(offset + 50)}>Older</Button></div>
        </CardBody>
      </Card>
    </div>
  );
}

export function AdminPage() {
  const [tab, setTab] = useState("system");
  return (
    <div>
      <PageHeader icon={ShieldCheck} eyebrow="Administration" title="System administration" description="All administrative actions are role-gated on the server and recorded in the audit log." />
      <Tabs value={tab} onValueChange={setTab} items={[
        { value: "system", label: <span className="flex items-center gap-1.5"><Activity className="size-3.5" />System</span> }, { value: "feedback", label: "Feedback" }, { value: "users", label: "Users" }, { value: "links", label: "Mentor links" },
        { value: "roles", label: "Roles" }, { value: "resources", label: "Resources" }, { value: "models", label: "Models" }, { value: "kb", label: "Knowledge base" }, { value: "audit", label: "Audit log" },
      ]}>
        <div className="pt-6">
          <TabPanel value="system"><SystemTab /></TabPanel>
          <TabPanel value="feedback"><FeedbackTab /></TabPanel>
          <TabPanel value="users"><UsersTab /></TabPanel>
          <TabPanel value="links"><LinksTab /></TabPanel>
          <TabPanel value="roles"><RolesTab /></TabPanel>
          <TabPanel value="resources"><ResourcesTab /></TabPanel>
          <TabPanel value="models"><ModelsTab /></TabPanel>
          <TabPanel value="kb"><KnowledgeTab /></TabPanel>
          <TabPanel value="audit"><AuditTab /></TabPanel>
        </div>
      </Tabs>
    </div>
  );
}
