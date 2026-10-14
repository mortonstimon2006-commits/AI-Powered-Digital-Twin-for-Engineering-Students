import { Info } from "lucide-react";
import { Tooltip as RT } from "radix-ui";
import type { HTMLAttributes, ReactNode } from "react";

import { cn, LEVEL_NAMES, STATUS_META } from "@/lib/utils";

export function Card({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("card", className)} {...props} />;
}

export function CardHeader({
  title,
  description,
  eyebrow,
  actions,
  className,
}: {
  title: ReactNode;
  description?: ReactNode;
  eyebrow?: ReactNode;
  actions?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-wrap items-start justify-between gap-3 px-5 pt-5 sm:px-6 sm:pt-6", className)}>
      <div className="min-w-0">
        {eyebrow && <p className="eyebrow mb-1.5">{eyebrow}</p>}
        <h2 className="text-lg font-semibold leading-tight">{title}</h2>
        {description && <p className="mt-1 max-w-prose text-sm text-fg-muted">{description}</p>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
    </div>
  );
}

export function CardBody({ className, ...props }: HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("px-5 pb-5 pt-4 sm:px-6 sm:pb-6", className)} {...props} />;
}

const TONES = {
  ok: "bg-ok/10 text-ok border-ok/25",
  info: "bg-info/10 text-info border-info/25",
  warn: "bg-warn/10 text-warn border-warn/25",
  danger: "bg-danger/10 text-danger border-danger/25",
  iris: "bg-iris/10 text-iris border-iris/25",
  aurora: "bg-aurora/10 text-aurora border-aurora/25",
  muted: "bg-white/[0.04] text-fg-muted border-line",
} as const;
export type Tone = keyof typeof TONES;

export function Badge({ tone = "muted", className, children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-1 whitespace-nowrap rounded-full border px-2 py-0.5 text-[0.72rem] font-medium leading-5",
        TONES[tone],
        className,
      )}
    >
      {children}
    </span>
  );
}

export function StatusBadge({ status }: { status: string }) {
  const meta = STATUS_META[status] ?? { label: status, tone: "muted" as const, hint: "" };
  return (
    <Hint content={meta.hint}>
      <span tabIndex={0} className="inline-flex rounded-full">
        <Badge tone={meta.tone}>{meta.label}</Badge>
      </span>
    </Hint>
  );
}

export function VerificationBadge({ status }: { status: string }) {
  const tone: Tone = status === "verified" ? "ok" : status === "pending" ? "info" : status === "rejected" ? "danger" : "muted";
  return <Badge tone={tone}>{status.charAt(0).toUpperCase() + status.slice(1)}</Badge>;
}

export function Hint({ content, children, side = "top" }: { content: ReactNode; children: ReactNode; side?: "top" | "bottom" | "left" | "right" }) {
  if (!content) return <>{children}</>;
  return (
    <RT.Root delayDuration={150}>
      <RT.Trigger asChild>{children}</RT.Trigger>
      <RT.Portal>
        <RT.Content
          side={side}
          sideOffset={6}
          className="z-50 max-w-xs rounded-lg border border-line-strong bg-ink-750 px-3 py-2 text-xs leading-relaxed text-fg shadow-xl"
        >
          {content}
          <RT.Arrow className="fill-ink-750" />
        </RT.Content>
      </RT.Portal>
    </RT.Root>
  );
}

export function InfoHint({ content, label = "More information" }: { content: ReactNode; label?: string }) {
  return (
    <Hint content={content}>
      <button type="button" aria-label={label} className="inline-flex text-fg-faint transition hover:text-fg">
        <Info className="size-3.5" />
      </button>
    </Hint>
  );
}

/** 0–4 proficiency indicator. Unknown is visibly different from zero. */
export function LevelMeter({
  value,
  required,
  status,
  className,
}: {
  value: number | null;
  required?: number;
  status?: string;
  className?: string;
}) {
  const known = value !== null && value !== undefined;
  const color =
    status === "assessed" ? "bg-ok" : status === "verified_evidence" ? "bg-info" : status === "unverified_evidence" ? "bg-iris" : "bg-warn";
  return (
    <div
      className={cn("flex items-center gap-1", className)}
      role="img"
      aria-label={
        known
          ? `Level ${value} of 4 (${LEVEL_NAMES[Math.min(4, Math.floor(value ?? 0))]})${required ? `, required ${required}` : ""}`
          : `Unknown level${required ? `, required ${required}` : ""}`
      }
    >
      {[1, 2, 3, 4].map((i) => {
        const fill = known ? Math.max(0, Math.min(1, (value ?? 0) - (i - 1))) : 0;
        return (
          <span
            key={i}
            className={cn(
              "relative h-2 w-6 overflow-hidden rounded-full",
              known ? "bg-white/[0.07]" : "border border-dashed border-fg-faint/50 bg-transparent",
              required !== undefined && i <= required && "ring-1 ring-fg-faint/40",
            )}
          >
            {known && <span className={cn("absolute inset-y-0 left-0 rounded-full", color)} style={{ width: `${fill * 100}%` }} />}
          </span>
        );
      })}
    </div>
  );
}

export function Meter({ value, max = 1, tone = "aurora", label, className }: { value: number; max?: number; tone?: "aurora" | "iris" | "warn" | "ok"; label?: string; className?: string }) {
  const pct = Math.max(0, Math.min(1, value / max)) * 100;
  const color = { aurora: "from-aurora to-[#7ee8fa]", iris: "from-iris to-[#c4b5fd]", warn: "from-warn to-[#fde68a]", ok: "from-ok to-[#6ee7b7]" }[tone];
  return (
    <div
      className={cn("h-2 w-full overflow-hidden rounded-full bg-white/[0.06]", className)}
      role="progressbar"
      aria-valuemin={0}
      aria-valuemax={100}
      aria-valuenow={Math.round(pct)}
      aria-label={label}
    >
      <div className={cn("h-full rounded-full bg-gradient-to-r transition-[width] duration-700 ease-out", color)} style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Stat({ label, value, sub, hint }: { label: string; value: ReactNode; sub?: ReactNode; hint?: ReactNode }) {
  return (
    <div className="min-w-0">
      <div className="flex items-center gap-1.5">
        <p className="eyebrow">{label}</p>
        {hint && <InfoHint content={hint} />}
      </div>
      <p className="metric mt-1 text-2xl font-semibold text-fg">{value}</p>
      {sub && <p className="mt-0.5 text-xs text-fg-muted">{sub}</p>}
    </div>
  );
}

export function Kbd({ children }: { children: ReactNode }) {
  return <kbd className="rounded border border-line-strong bg-ink-750 px-1.5 py-0.5 font-mono text-[0.7rem] text-fg-muted">{children}</kbd>;
}
