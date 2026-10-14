import { useQuery } from "@tanstack/react-query";
import {
  ArrowRight,
  Bot,
  ClipboardCheck,
  Cpu,
  FlaskConical,
  Gauge,
  HelpCircle,
  LockKeyhole,
  Network,
  Route,
  ShieldCheck,
  Target,
  UserRoundPen,
} from "lucide-react";
import { motion, useReducedMotion, useScroll, useTransform } from "motion/react";
import { lazy, Suspense, useRef } from "react";
import { Link } from "react-router";

import { Brand } from "@/components/layout/Brand";
import { Reveal, Stagger, StaggerItem } from "@/components/motion";
import { ConstellationFallback } from "@/components/three/ConstellationFallback";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/states";
import { api } from "@/lib/api";
import { useCatalogueSkills, useMe, useRoles } from "@/lib/queries";
import { useCan3D } from "@/lib/visuals";

const SkillConstellation = lazy(() => import("@/components/three/SkillConstellation"));

const TRUST = [
  { key: "Assessed", desc: "Verified assessment recorded by a mentor", w: 100, color: "bg-ok" },
  { key: "Verified evidence", desc: "Project or internship a mentor verified", w: 85, color: "bg-info" },
  { key: "Unverified evidence", desc: "Linked project, not yet verified", w: 60, color: "bg-iris" },
  { key: "Self-reported", desc: "Your own rating", w: 40, color: "bg-warn" },
  { key: "Unknown", desc: "Not measured yet — never treated as zero", w: 0, color: "bg-fg-faint" },
];

const CAPABILITIES = [
  { icon: UserRoundPen, title: "Adaptive digital twin", body: "A versioned record of your academics, skills, projects and assessments. Every change is snapshotted, so you can see exactly how your profile evolved." },
  { icon: Gauge, title: "Explainable readiness model", body: "A versioned classifier with held-out evaluation, calibration checks and per-feature SHAP attributions. Its limitations are shown next to every estimate." },
  { icon: Target, title: "Role-specific skill gaps", body: "A documented, configurable formula compares your evidence with each role's requirements, separating unknown, self-reported and assessed skills." },
  { icon: FlaskConical, title: "What-if simulator", body: "Change hypothetical inputs on an isolated copy of your twin and see how the same model and framework respond. Your real profile is never touched." },
  { icon: Network, title: "Knowledge graph", body: "Skills, prerequisites, roles, resources and your evidence in one graph, with recorded facts visually distinct from inferences." },
  { icon: Route, title: "Adaptive roadmap", body: "Prerequisite-ordered plans built from your real gaps, scheduled around your weekly hours, using a catalogue of link-checked resources." },
  { icon: Bot, title: "Private local AI mentor", body: "A retrieval-augmented mentor that runs on a local model through Ollama. Your data and documents are never sent to an external AI service." },
  { icon: ClipboardCheck, title: "Mentor verification", body: "Assigned mentors can record assessments and verify evidence, but only while you grant mentor sharing." },
];

const HONEST = [
  "No hiring or placement guarantees. Match scores compare you with a framework; they are not hiring probabilities.",
  "The demonstration model is labelled as trained on synthetic data until real, consented assessor labels exist.",
  "Simulated changes are model outputs, not proof of cause and effect.",
  "No invented job openings, testimonials or success statistics.",
];

function HeroVisual() {
  const roles = useRoles();
  const skills = useCatalogueSkills();
  const { enabled } = useCan3D();
  const reduce = useReducedMotion();
  if (roles.isLoading || skills.isLoading) return <Skeleton className="h-full w-full rounded-2xl" />;
  if (!roles.data || !skills.data) {
    return <div className="grid h-full place-items-center text-sm text-fg-muted">The live framework map is unavailable right now.</div>;
  }
  const reqCount = roles.data.roles.reduce((n, r) => n + r.requirements.length, 0);
  return (
    <div className="relative h-full w-full">
      {enabled ? (
        <Suspense fallback={<ConstellationFallback roles={roles.data.roles} skills={skills.data.skills} />}>
          <SkillConstellation roles={roles.data.roles} skills={skills.data.skills} animate={!reduce} />
        </Suspense>
      ) : (
        <ConstellationFallback roles={roles.data.roles} skills={skills.data.skills} />
      )}
      <p className="pointer-events-none absolute bottom-3 left-4 right-4 font-mono text-[0.68rem] text-fg-faint">
        Live from the catalogue · {roles.data.roles.length} roles · {skills.data.skills.length} skills · {reqCount} weighted requirements
      </p>
    </div>
  );
}

function ModelStatusStrip() {
  const { data } = useQuery({
    queryKey: ["readiness", "model", "public"],
    queryFn: () => api<{ available: boolean; version?: string; is_synthetic?: boolean; algorithm?: string }>("/readiness/model"),
  });
  if (!data) return null;
  return (
    <p className="font-mono text-[0.7rem] text-fg-faint">
      Readiness model:{" "}
      {data.available ? (
        <>
          {data.algorithm?.replace("_", " ")} · {data.version}
          {data.is_synthetic && <span className="ml-2 rounded bg-iris/15 px-1.5 py-0.5 text-iris">synthetic-data demo</span>}
        </>
      ) : (
        "not yet available"
      )}
    </p>
  );
}

export function LandingPage() {
  const { data: me } = useMe();
  const heroRef = useRef<HTMLDivElement>(null);
  const reduce = useReducedMotion();
  const { scrollYProgress } = useScroll({ target: heroRef, offset: ["start start", "end start"] });
  const visualY = useTransform(scrollYProgress, [0, 1], [0, reduce ? 0 : 80]);
  const fade = useTransform(scrollYProgress, [0, 0.8], [1, reduce ? 1 : 0.2]);

  return (
    <div className="relative overflow-x-clip">
      <header className="sticky top-0 z-30 border-b border-white/[0.04] bg-ink-900/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center justify-between px-4 py-3 sm:px-6">
          <Brand />
          <nav className="flex items-center gap-2" aria-label="Account">
            {me ? (
              <Button asChild size="sm">
                <Link to="/app">Open dashboard</Link>
              </Button>
            ) : (
              <>
                <Button asChild variant="ghost" size="sm">
                  <Link to="/login">Sign in</Link>
                </Button>
                <Button asChild size="sm">
                  <Link to="/register">Create account</Link>
                </Button>
              </>
            )}
          </nav>
        </div>
      </header>

      <section ref={heroRef} className="grid-bg relative">
        <div className="mx-auto grid max-w-7xl items-center gap-10 px-4 pb-16 pt-14 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pb-24 lg:pt-20">
          <motion.div initial={{ opacity: 0, y: reduce ? 0 : 20 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.7, ease: [0.22, 1, 0.36, 1] }}>
            <p className="eyebrow mb-4 flex items-center gap-2">
              <Cpu className="size-3.5 text-aurora" /> Career digital twin for engineering students
            </p>
            <h1 className="text-4xl font-semibold leading-[1.05] sm:text-5xl lg:text-6xl">
              Your skills. Your future.
              <br />
              <span className="text-gradient">Simulated intelligently.</span>
            </h1>
            <p className="mt-6 max-w-xl text-base leading-relaxed text-fg-muted sm:text-lg">
              TwinPath builds an evidence-aware model of your profile, shows which role requirements you meet and which you don't, explains
              every estimate, and lets you test what-if changes before you commit months of effort.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-3">
              <Button asChild size="lg">
                <Link to={me ? "/app" : "/register"}>
                  {me ? "Go to your twin" : "Build your twin"} <ArrowRight className="size-4" />
                </Link>
              </Button>
              <Button asChild size="lg" variant="outline">
                <a href="#how">How it works</a>
              </Button>
            </div>
            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2 text-sm text-fg-muted">
              <span className="inline-flex items-center gap-2"><LockKeyhole className="size-4 text-aurora" /> Local AI, no external LLM APIs</span>
              <span className="inline-flex items-center gap-2"><ShieldCheck className="size-4 text-aurora" /> Explainable, versioned models</span>
            </div>
            <div className="mt-6"><ModelStatusStrip /></div>
          </motion.div>

          <motion.div style={{ y: visualY, opacity: fade }} className="relative h-[360px] overflow-hidden rounded-2xl border border-line bg-ink-900 sm:h-[460px]">
            <HeroVisual />
          </motion.div>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <Reveal className="grid gap-10 lg:grid-cols-[0.9fr_1.1fr] lg:items-center">
          <div>
            <p className="eyebrow mb-3">Evidence, not just claims</p>
            <h2 className="text-3xl font-semibold sm:text-4xl">Every skill estimate says where it came from.</h2>
            <p className="mt-4 text-fg-muted">
              A GitHub link or a confident self-rating isn't proof of competence. TwinPath ranks each signal by how trustworthy it is, and
              uses the most trustworthy one available. When nothing has been measured, the skill is shown as <em>unknown</em> rather than
              silently counted as zero.
            </p>
          </div>
          <Stagger className="space-y-2.5">
            {TRUST.map((t) => (
              <StaggerItem key={t.key} className="card flex items-center gap-4 px-4 py-3">
                <div className="w-40 shrink-0">
                  <p className="text-sm font-medium">{t.key}</p>
                  <p className="text-xs text-fg-faint">{t.desc}</p>
                </div>
                <div className="h-2 flex-1 overflow-hidden rounded-full bg-white/[0.05]">
                  <motion.div className={`h-full rounded-full ${t.color}`} initial={{ width: 0 }} whileInView={{ width: `${t.w}%` }}
                    viewport={{ once: true }} transition={{ duration: 0.9, ease: [0.22, 1, 0.36, 1] }} />
                </div>
                <span className="metric w-10 text-right text-xs text-fg-muted">{t.w ? (t.w / 100).toFixed(2) : "—"}</span>
              </StaggerItem>
            ))}
          </Stagger>
        </Reveal>
      </section>

      <section id="how" className="border-y border-line bg-ink-850/40">
        <div className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
          <Reveal>
            <p className="eyebrow mb-3">Capabilities</p>
            <h2 className="max-w-2xl text-3xl font-semibold sm:text-4xl">One twin, several honest lenses.</h2>
          </Reveal>
          <Stagger className="mt-10 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {CAPABILITIES.map((c) => (
              <StaggerItem key={c.title} className="card group p-5 transition hover:border-aurora/30">
                <div className="mb-4 grid size-10 place-items-center rounded-lg bg-gradient-to-br from-aurora/15 to-iris/15 text-aurora transition group-hover:scale-105">
                  <c.icon className="size-5" />
                </div>
                <h3 className="text-base font-semibold">{c.title}</h3>
                <p className="mt-2 text-sm leading-relaxed text-fg-muted">{c.body}</p>
              </StaggerItem>
            ))}
          </Stagger>
        </div>
      </section>

      <section className="mx-auto max-w-7xl px-4 py-20 sm:px-6">
        <div className="grid gap-12 lg:grid-cols-2">
          <Reveal>
            <p className="eyebrow mb-3">How it works</p>
            <h2 className="text-3xl font-semibold sm:text-4xl">From profile to plan in four steps.</h2>
            <ol className="mt-8 space-y-6">
              {[
                ["Build the twin", "Add your academics, rate your skills, and link projects as evidence. Upload a resume to pre-fill suggestions you confirm yourself."],
                ["See the gaps", "Compare your evidence with any role's versioned requirements. Unknown skills are flagged for a baseline, not penalised in secret."],
                ["Simulate", "Ask what changes if you reach SQL level 3 or complete a deployed project, using the same model, on a copy of your twin."],
                ["Follow and verify", "Work through a prerequisite-ordered roadmap, record evidence, and ask a mentor to verify it as you progress."],
              ].map(([title, body], i) => (
                <li key={title} className="flex gap-4">
                  <span className="metric grid size-8 shrink-0 place-items-center rounded-full border border-aurora/40 text-sm text-aurora">{i + 1}</span>
                  <div>
                    <p className="font-medium">{title}</p>
                    <p className="mt-1 text-sm text-fg-muted">{body}</p>
                  </div>
                </li>
              ))}
            </ol>
          </Reveal>
          <Reveal delay={0.1} className="card p-6 sm:p-8">
            <div className="mb-4 flex items-center gap-2 text-iris">
              <HelpCircle className="size-5" />
              <p className="eyebrow !text-iris">Honest by design</p>
            </div>
            <h3 className="text-2xl font-semibold">What TwinPath will never claim</h3>
            <ul className="mt-6 space-y-4">
              {HONEST.map((h) => (
                <li key={h} className="flex gap-3 text-sm text-fg-muted">
                  <ShieldCheck className="mt-0.5 size-4 shrink-0 text-aurora" /> {h}
                </li>
              ))}
            </ul>
            <Button asChild className="mt-8">
              <Link to={me ? "/app" : "/register"}>
                Start with your profile <ArrowRight className="size-4" />
              </Link>
            </Button>
          </Reveal>
        </div>
      </section>

      <footer className="border-t border-line">
        <div className="mx-auto flex max-w-7xl flex-wrap items-center justify-between gap-4 px-4 py-8 text-sm text-fg-faint sm:px-6">
          <Brand />
          <p>Final-year engineering project · runs on your institution's infrastructure · AI inference stays local.</p>
        </div>
      </footer>
    </div>
  );
}
