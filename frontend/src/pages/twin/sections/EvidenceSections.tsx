import { zodResolver } from "@hookform/resolvers/zod";
import { BadgeCheck, Briefcase, ExternalLink, FolderGit2, Pencil, Plus, Send, Trash2 } from "lucide-react";
import { useState } from "react";
import { useForm } from "react-hook-form";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Field, Input, Select, Textarea } from "@/components/ui/form";
import { ConfirmButton, Dialog } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader, VerificationBadge } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingBlock } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, useCatalogueSkills, useCertifications, useExperiences, useProjects } from "@/lib/queries";
import type { Certification, EvidenceLink, Experience, Project } from "@/lib/types";
import { dateOnly, LEVEL_NAMES } from "@/lib/utils";

type Link = { skill_id: number; level: number; note: string };

export function SkillLinksEditor({ value, onChange, max = 20 }: { value: Link[]; onChange: (v: Link[]) => void; max?: number }) {
  const catalogue = useCatalogueSkills();
  const [pick, setPick] = useState("");
  const used = new Set(value.map((v) => v.skill_id));
  const names = new Map((catalogue.data?.skills ?? []).map((s) => [s.id, s.name]));
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">Skills this demonstrates</p>
      <p className="text-xs text-fg-faint">Claim honestly: the trust of this evidence depends on the item's verification status, not on the level you claim.</p>
      {value.map((l, i) => (
        <div key={l.skill_id} className="flex flex-wrap items-center gap-2 rounded-lg border border-line px-3 py-2">
          <span className="min-w-32 flex-1 text-sm">{names.get(l.skill_id) ?? l.skill_id}</span>
          <Select aria-label={`Level demonstrated for ${names.get(l.skill_id)}`} className="h-8 w-40 text-xs" value={l.level}
            onChange={(e) => onChange(value.map((x, j) => (j === i ? { ...x, level: Number(e.target.value) } : x)))}>
            {[1, 2, 3, 4].map((n) => <option key={n} value={n}>{n} · {LEVEL_NAMES[n]}</option>)}
          </Select>
          <Button variant="ghost" size="icon" aria-label={`Remove ${names.get(l.skill_id)}`} onClick={() => onChange(value.filter((_, j) => j !== i))}>
            <Trash2 className="size-4" />
          </Button>
        </div>
      ))}
      {value.length < max && (
        <div className="flex gap-2">
          <Select aria-label="Add a skill" value={pick} onChange={(e) => setPick(e.target.value)}>
            <option value="">Add a skill…</option>
            {(catalogue.data?.skills ?? []).filter((s) => !used.has(s.id)).map((s) => <option key={s.id} value={s.id}>{s.name}</option>)}
          </Select>
          <Button variant="secondary" disabled={!pick} onClick={() => { onChange([...value, { skill_id: Number(pick), level: 2, note: "" }]); setPick(""); }}>
            <Plus className="size-4" /> Add
          </Button>
        </div>
      )}
    </div>
  );
}

const toLinks = (ev: EvidenceLink[]): Link[] => ev.map((e) => ({ skill_id: e.skill_id, level: e.level_demonstrated, note: e.note }));

function useSkillNames() {
  const catalogue = useCatalogueSkills();
  return new Map((catalogue.data?.skills ?? []).map((s) => [s.id, s.name]));
}

function EvidenceChips({ links }: { links: EvidenceLink[] }) {
  const names = useSkillNames();
  if (!links.length) return <p className="text-xs text-fg-faint">No skills linked yet.</p>;
  return (
    <div className="flex flex-wrap gap-1.5">
      {links.map((l) => <Badge key={l.id} tone="aurora">{names.get(l.skill_id) ?? l.skill_id} · L{l.level_demonstrated}</Badge>)}
    </div>
  );
}

async function requestVerification(item_type: string, item_id: string) {
  try {
    await api("/twin/verification-requests", { method: "POST", body: { item_type, item_id } });
    await invalidateTwin();
    toast.success("Verification requested.");
  } catch (e) {
    toast.error(e instanceof ApiError ? e.message : "Request failed.");
  }
}

const httpsUrl = z.union([z.literal("").transform(() => null), z.null(), z.string().trim().url("Enter a full URL").startsWith("https://", "Use an https:// link")]);
const optDate = z.union([z.literal("").transform(() => null), z.null(), z.string()]);

// ----------------------------------------------------------------------------- projects

const projectSchema = z.object({
  title: z.string().trim().min(2, "Give the project a title.").max(120),
  summary: z.string().trim().max(4000),
  technologies: z.string().max(800),
  repo_url: httpsUrl,
  demo_url: httpsUrl,
  is_deployed: z.boolean(),
  started_on: optDate,
  completed_on: optDate,
});

function ProjectDialog({ open, onOpenChange, project }: { open: boolean; onOpenChange: (o: boolean) => void; project: Project | null }) {
  const [links, setLinks] = useState<Link[]>(project ? toLinks(project.skills) : []);
  const form = useForm<z.input<typeof projectSchema>, unknown, z.output<typeof projectSchema>>({
    resolver: zodResolver(projectSchema),
    defaultValues: {
      title: project?.title ?? "", summary: project?.summary ?? "", technologies: project?.technologies.join(", ") ?? "",
      repo_url: project?.repo_url ?? "", demo_url: project?.demo_url ?? "", is_deployed: project?.is_deployed ?? false,
      started_on: project?.started_on ?? "", completed_on: project?.completed_on ?? "",
    },
  });
  const submit = form.handleSubmit(async (v) => {
    const body = { ...v, technologies: v.technologies.split(",").map((t) => t.trim()).filter(Boolean), skills: links };
    try {
      if (project) await api(`/twin/projects/${project.id}`, { method: "PUT", body });
      else await api("/twin/projects", { method: "POST", body });
      await invalidateTwin();
      toast.success(project ? "Project updated." : "Project added to your twin.");
      onOpenChange(false);
    } catch (e) {
      if (e instanceof ApiError) {
        for (const [f, m] of Object.entries(e.fieldErrors)) form.setError(f as keyof z.input<typeof projectSchema>, { message: m });
        toast.error(e.message);
      }
    }
  });
  const e = form.formState.errors;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title={project ? "Edit project" : "Add project"}
      description={project?.verification_status === "verified" ? "Editing the title, summary or links resets verification." : "Projects are strong evidence once verified by a mentor."}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="Title" className="sm:col-span-2" error={e.title?.message} required>{({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("title")} />}</Field>
        <Field label="Summary" className="sm:col-span-2" hint="What problem, your contribution, the result." error={e.summary?.message}>{({ id, describedBy, invalid }) => <Textarea id={id} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("summary")} />}</Field>
        <Field label="Technologies" hint="Comma-separated" className="sm:col-span-2">{({ id, describedBy }) => <Input id={id} aria-describedby={describedBy} {...form.register("technologies")} />}</Field>
        <Field label="Repository URL" error={e.repo_url?.message}>{({ id, describedBy, invalid }) => <Input id={id} placeholder="https://github.com/…" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("repo_url")} />}</Field>
        <Field label="Demo URL" error={e.demo_url?.message}>{({ id, describedBy, invalid }) => <Input id={id} placeholder="https://…" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("demo_url")} />}</Field>
        <Field label="Started">{({ id }) => <Input id={id} type="date" {...form.register("started_on")} />}</Field>
        <Field label="Completed" error={e.completed_on?.message}>{({ id, invalid }) => <Input id={id} type="date" aria-invalid={invalid} {...form.register("completed_on")} />}</Field>
        <label className="flex items-center gap-2 text-sm sm:col-span-2"><input type="checkbox" className="size-4 accent-[#5eead4]" {...form.register("is_deployed")} /> The project is deployed and usable</label>
        <div className="sm:col-span-2"><SkillLinksEditor value={links} onChange={setLinks} /></div>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" loading={form.formState.isSubmitting}>Save project</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ProjectsSection() {
  const projects = useProjects();
  const [editing, setEditing] = useState<Project | null>(null);
  const [open, setOpen] = useState(false);
  if (projects.isLoading) return <LoadingBlock rows={3} />;
  if (projects.error) return <ErrorState error={projects.error} onRetry={() => projects.refetch()} />;
  return (
    <Card>
      <CardHeader title="Projects" description="Link the skills each project demonstrates, then request mentor verification."
        actions={<Button onClick={() => { setEditing(null); setOpen(true); }}><Plus className="size-4" /> Add project</Button>} />
      <CardBody>
        {projects.data!.length ? (
          <ul className="grid gap-4 md:grid-cols-2">
            {projects.data!.map((p) => (
              <li key={p.id} className="rounded-xl border border-line bg-ink-800/40 p-4">
                <div className="flex items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="flex items-center gap-2 font-medium"><FolderGit2 className="size-4 text-aurora" /> {p.title}</p>
                    <p className="mt-0.5 text-xs text-fg-faint">{p.completed_on ? `Completed ${dateOnly(p.completed_on)}` : "In progress"}{p.is_deployed && " · deployed"}</p>
                  </div>
                  <VerificationBadge status={p.verification_status} />
                </div>
                {p.summary && <p className="mt-2 line-clamp-3 text-sm text-fg-muted">{p.summary}</p>}
                <div className="mt-3"><EvidenceChips links={p.skills} /></div>
                <div className="mt-3 flex flex-wrap items-center gap-1">
                  {p.repo_url && <Button asChild variant="ghost" size="sm"><a href={p.repo_url} target="_blank" rel="noopener noreferrer nofollow"><ExternalLink className="size-3.5" /> Repo</a></Button>}
                  <Button variant="ghost" size="sm" onClick={() => { setEditing(p); setOpen(true); }}><Pencil className="size-3.5" /> Edit</Button>
                  {(p.verification_status === "unverified" || p.verification_status === "rejected") && (
                    <Button variant="ghost" size="sm" onClick={() => requestVerification("project", p.id)}><Send className="size-3.5" /> Request verification</Button>
                  )}
                  <ConfirmButton trigger={<Button variant="ghost" size="sm" className="ml-auto text-danger"><Trash2 className="size-3.5" /> Delete</Button>}
                    title="Delete this project?" description="Its linked skill evidence is removed too. This creates a new twin version."
                    confirmLabel="Delete project" onConfirm={async () => { await api(`/twin/projects/${p.id}`, { method: "DELETE" }); await invalidateTwin(); toast.success("Project deleted."); }} />
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState icon={<FolderGit2 className="size-5" />} title="No projects yet" action={<Button onClick={() => setOpen(true)}><Plus className="size-4" /> Add your first project</Button>}>
            Projects are the most common way to show practical skill. Add one and link the skills it uses.
          </EmptyState>
        )}
      </CardBody>
      {open && <ProjectDialog key={editing?.id ?? "new"} open={open} onOpenChange={setOpen} project={editing} />}
    </Card>
  );
}

// ----------------------------------------------------------------------------- experience

const expSchema = z.object({
  kind: z.enum(["internship", "job", "research", "hackathon", "volunteer"]),
  organization: z.string().trim().min(2, "Enter the organisation.").max(120),
  title: z.string().trim().min(2, "Enter your role or event name.").max(120),
  description: z.string().trim().max(4000),
  start_date: z.string().min(1, "Enter a start date."),
  end_date: optDate,
  outcome: z.union([z.literal("").transform(() => null), z.null(), z.string().max(60)]),
});

function ExperienceDialog({ open, onOpenChange, item }: { open: boolean; onOpenChange: (o: boolean) => void; item: Experience | null }) {
  const [links, setLinks] = useState<Link[]>(item ? toLinks(item.skills) : []);
  const form = useForm<z.input<typeof expSchema>, unknown, z.output<typeof expSchema>>({
    resolver: zodResolver(expSchema),
    defaultValues: { kind: (item?.kind as z.input<typeof expSchema>["kind"]) ?? "internship", organization: item?.organization ?? "",
      title: item?.title ?? "", description: item?.description ?? "", start_date: item?.start_date ?? "", end_date: item?.end_date ?? "",
      outcome: item?.outcome ?? "" },
  });
  const submit = form.handleSubmit(async (v) => {
    try {
      const body = { ...v, skills: links };
      if (item) await api(`/twin/experiences/${item.id}`, { method: "PUT", body });
      else await api("/twin/experiences", { method: "POST", body });
      await invalidateTwin();
      toast.success("Experience saved.");
      onOpenChange(false);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  });
  const e = form.formState.errors;
  return (
    <Dialog open={open} onOpenChange={onOpenChange} wide title={item ? "Edit experience" : "Add experience"}>
      <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
        <Field label="Type">{({ id }) => (
          <Select id={id} {...form.register("kind")}>
            <option value="internship">Internship</option><option value="job">Job</option><option value="research">Research</option>
            <option value="hackathon">Hackathon</option><option value="volunteer">Volunteer</option>
          </Select>)}
        </Field>
        <Field label="Organisation" error={e.organization?.message} required>{({ id, invalid }) => <Input id={id} aria-invalid={invalid} {...form.register("organization")} />}</Field>
        <Field label="Role / event" error={e.title?.message} required>{({ id, invalid }) => <Input id={id} aria-invalid={invalid} {...form.register("title")} />}</Field>
        <Field label="Outcome" hint="e.g. finalist, PPO, paper accepted">{({ id }) => <Input id={id} {...form.register("outcome")} />}</Field>
        <Field label="Start date" error={e.start_date?.message} required>{({ id, invalid }) => <Input id={id} type="date" aria-invalid={invalid} {...form.register("start_date")} />}</Field>
        <Field label="End date" hint="Leave empty if ongoing">{({ id }) => <Input id={id} type="date" {...form.register("end_date")} />}</Field>
        <Field label="Description" className="sm:col-span-2">{({ id }) => <Textarea id={id} {...form.register("description")} />}</Field>
        <div className="sm:col-span-2"><SkillLinksEditor value={links} onChange={setLinks} /></div>
        <div className="flex justify-end gap-2 sm:col-span-2">
          <Button variant="secondary" onClick={() => onOpenChange(false)}>Cancel</Button>
          <Button type="submit" loading={form.formState.isSubmitting}>Save</Button>
        </div>
      </form>
    </Dialog>
  );
}

export function ExperienceSection() {
  const items = useExperiences();
  const [editing, setEditing] = useState<Experience | null>(null);
  const [open, setOpen] = useState(false);
  if (items.isLoading) return <LoadingBlock rows={3} />;
  if (items.error) return <ErrorState error={items.error} onRetry={() => items.refetch()} />;
  return (
    <Card>
      <CardHeader title="Experience" description="Internships, jobs, research, hackathons and volunteering."
        actions={<Button onClick={() => { setEditing(null); setOpen(true); }}><Plus className="size-4" /> Add experience</Button>} />
      <CardBody>
        {items.data!.length ? (
          <ol className="relative space-y-4 border-l border-line pl-6">
            {items.data!.map((x) => (
              <li key={x.id} className="relative">
                <span className="absolute -left-[1.85rem] top-1.5 size-3 rounded-full border-2 border-aurora bg-ink-900" aria-hidden />
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div>
                    <p className="font-medium">{x.title} <span className="text-fg-muted">· {x.organization}</span></p>
                    <p className="text-xs text-fg-faint capitalize">{x.kind} · {dateOnly(x.start_date)} – {x.end_date ? dateOnly(x.end_date) : "present"}{x.outcome && ` · ${x.outcome}`}</p>
                  </div>
                  <VerificationBadge status={x.verification_status} />
                </div>
                {x.description && <p className="mt-1.5 text-sm text-fg-muted">{x.description}</p>}
                <div className="mt-2"><EvidenceChips links={x.skills} /></div>
                <div className="mt-2 flex flex-wrap gap-1">
                  <Button variant="ghost" size="sm" onClick={() => { setEditing(x); setOpen(true); }}><Pencil className="size-3.5" /> Edit</Button>
                  {(x.verification_status === "unverified" || x.verification_status === "rejected") && (
                    <Button variant="ghost" size="sm" onClick={() => requestVerification("experience", x.id)}><Send className="size-3.5" /> Request verification</Button>
                  )}
                  <ConfirmButton trigger={<Button variant="ghost" size="sm" className="text-danger"><Trash2 className="size-3.5" /> Delete</Button>}
                    title="Delete this experience?" description="Linked skill evidence is removed too." confirmLabel="Delete"
                    onConfirm={async () => { await api(`/twin/experiences/${x.id}`, { method: "DELETE" }); await invalidateTwin(); }} />
                </div>
              </li>
            ))}
          </ol>
        ) : (
          <EmptyState icon={<Briefcase className="size-5" />} title="No experience recorded" action={<Button onClick={() => setOpen(true)}>Add experience</Button>}>
            Internship months and hackathons are inputs to the readiness model.
          </EmptyState>
        )}
      </CardBody>
      {open && <ExperienceDialog key={editing?.id ?? "new"} open={open} onOpenChange={setOpen} item={editing} />}
    </Card>
  );
}

// ----------------------------------------------------------------------------- certifications

const certSchema = z.object({
  name: z.string().trim().min(2, "Enter the certification name.").max(160),
  issuer: z.string().trim().min(2, "Enter the issuer.").max(120),
  issued_on: optDate,
  credential_url: httpsUrl,
});

export function CertificationsSection() {
  const items = useCertifications();
  const [open, setOpen] = useState(false);
  const [links, setLinks] = useState<Link[]>([]);
  const form = useForm<z.input<typeof certSchema>, unknown, z.output<typeof certSchema>>({ resolver: zodResolver(certSchema),
    defaultValues: { name: "", issuer: "", issued_on: "", credential_url: "" } });
  const submit = form.handleSubmit(async (v) => {
    try {
      await api("/twin/certifications", { method: "POST", body: { ...v, skills: links } });
      await invalidateTwin();
      toast.success("Certification added (unverified until a mentor checks it).");
      setOpen(false);
      form.reset();
      setLinks([]);
    } catch (e) {
      if (e instanceof ApiError) toast.error(e.message);
    }
  });
  if (items.isLoading) return <LoadingBlock rows={2} />;
  if (items.error) return <ErrorState error={items.error} onRetry={() => items.refetch()} />;
  const e = form.formState.errors;
  return (
    <Card>
      <CardHeader title="Certifications" description="Only verified certifications count as a readiness-model input; an uploaded certificate is not proof by itself."
        actions={<Button onClick={() => setOpen(true)}><Plus className="size-4" /> Add certification</Button>} />
      <CardBody>
        {items.data!.length ? (
          <ul className="grid gap-3 md:grid-cols-2">
            {items.data!.map((c: Certification) => (
              <li key={c.id} className="flex items-start justify-between gap-3 rounded-xl border border-line bg-ink-800/40 p-4">
                <div className="min-w-0">
                  <p className="flex items-center gap-2 font-medium"><BadgeCheck className="size-4 text-aurora" /> {c.name}</p>
                  <p className="text-xs text-fg-faint">{c.issuer}{c.issued_on && ` · ${dateOnly(c.issued_on)}`}</p>
                  <div className="mt-2"><EvidenceChips links={c.skills} /></div>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-2">
                  <VerificationBadge status={c.verification_status} />
                  {(c.verification_status === "unverified" || c.verification_status === "rejected") && (
                    <Button variant="ghost" size="sm" onClick={() => requestVerification("certification", c.id)}><Send className="size-3.5" /> Verify</Button>
                  )}
                  <ConfirmButton trigger={<Button variant="ghost" size="sm" className="text-danger" aria-label={`Delete ${c.name}`}><Trash2 className="size-3.5" /></Button>}
                    title="Delete this certification?" description="Linked skill evidence is removed too." confirmLabel="Delete"
                    onConfirm={async () => { await api(`/twin/certifications/${c.id}`, { method: "DELETE" }); await invalidateTwin(); }} />
                </div>
              </li>
            ))}
          </ul>
        ) : <EmptyState icon={<BadgeCheck className="size-5" />} title="No certifications" />}
      </CardBody>
      <Dialog open={open} onOpenChange={setOpen} title="Add certification" wide>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
          <Field label="Name" error={e.name?.message} required>{({ id, invalid }) => <Input id={id} aria-invalid={invalid} {...form.register("name")} />}</Field>
          <Field label="Issuer" error={e.issuer?.message} required>{({ id, invalid }) => <Input id={id} aria-invalid={invalid} {...form.register("issuer")} />}</Field>
          <Field label="Issued on">{({ id }) => <Input id={id} type="date" {...form.register("issued_on")} />}</Field>
          <Field label="Credential URL" error={e.credential_url?.message}>{({ id, invalid }) => <Input id={id} placeholder="https://…" aria-invalid={invalid} {...form.register("credential_url")} />}</Field>
          <div className="sm:col-span-2"><SkillLinksEditor value={links} onChange={setLinks} max={10} /></div>
          <div className="flex justify-end gap-2 sm:col-span-2">
            <Button variant="secondary" onClick={() => setOpen(false)}>Cancel</Button>
            <Button type="submit" loading={form.formState.isSubmitting}>Add</Button>
          </div>
        </form>
      </Dialog>
    </Card>
  );
}
