import { AlertTriangle, CloudOff, FlaskConical, Inbox, RefreshCw, ShieldAlert } from "lucide-react";
import type { ReactNode } from "react";

import { ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

import { Button } from "./button";

export function Skeleton({ className }: { className?: string }) {
  return <div className={cn("skeleton rounded-lg", className)} aria-hidden />;
}

export function LoadingBlock({ rows = 3, label = "Loading" }: { rows?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-3">
      <span className="sr-only">{label}…</span>
      {Array.from({ length: rows }).map((_, i) => (
        <Skeleton key={i} className={cn("h-14", i === 0 && "h-24")} />
      ))}
    </div>
  );
}

export function EmptyState({
  icon,
  title,
  children,
  action,
  className,
}: {
  icon?: ReactNode;
  title: string;
  children?: ReactNode;
  action?: ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("flex flex-col items-center rounded-xl border border-dashed border-line px-6 py-10 text-center", className)}>
      <div className="mb-3 grid size-11 place-items-center rounded-full bg-white/[0.04] text-fg-muted">
        {icon ?? <Inbox className="size-5" aria-hidden />}
      </div>
      <h3 className="text-base font-semibold">{title}</h3>
      {children && <div className="mt-1.5 max-w-md text-sm text-fg-muted">{children}</div>}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

export function ErrorState({ error, onRetry, title }: { error: unknown; onRetry?: () => void; title?: string }) {
  const e = error instanceof ApiError ? error : null;
  const offline = e?.code === "network_error" || e?.status === 0;
  const unavailable = e && [502, 503, 504].includes(e.status);
  const Icon = offline ? CloudOff : unavailable ? ShieldAlert : AlertTriangle;
  return (
    <div role="alert" className="rounded-xl border border-danger/25 bg-danger/[0.06] px-5 py-4">
      <div className="flex items-start gap-3">
        <Icon className="mt-0.5 size-5 shrink-0 text-danger" aria-hidden />
        <div className="min-w-0 flex-1">
          <p className="font-medium text-fg">{title ?? (offline ? "You're offline" : unavailable ? "Service unavailable" : "Something went wrong")}</p>
          <p className="mt-0.5 text-sm text-fg-muted">{e?.message ?? (error instanceof Error ? error.message : "Unexpected error.")}</p>
          {e?.requestId && <p className="mt-1 font-mono text-[0.7rem] text-fg-faint">Reference: {e.requestId}</p>}
        </div>
        {onRetry && (
          <Button variant="secondary" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" aria-hidden /> Retry
          </Button>
        )}
      </div>
    </div>
  );
}

export function Notice({
  tone = "info",
  title,
  children,
  icon,
  className,
}: {
  tone?: "info" | "warn" | "danger" | "ok" | "synthetic";
  title?: ReactNode;
  children?: ReactNode;
  icon?: ReactNode;
  className?: string;
}) {
  const styles = {
    info: "border-info/25 bg-info/[0.06] text-info",
    warn: "border-warn/25 bg-warn/[0.06] text-warn",
    danger: "border-danger/25 bg-danger/[0.06] text-danger",
    ok: "border-ok/25 bg-ok/[0.06] text-ok",
    synthetic: "border-iris/30 bg-iris/[0.07] text-iris",
  }[tone];
  return (
    <div className={cn("flex gap-3 rounded-xl border px-4 py-3", styles, className)}>
      <span className="mt-0.5 shrink-0">{icon ?? (tone === "synthetic" ? <FlaskConical className="size-4" /> : <AlertTriangle className="size-4" />)}</span>
      <div className="min-w-0 text-sm">
        {title && <p className="font-medium">{title}</p>}
        {children && <div className="text-fg-muted">{children}</div>}
      </div>
    </div>
  );
}

export function SyntheticModelNotice({ compact = false }: { compact?: boolean }) {
  return (
    <Notice tone="synthetic" title="Demonstration model — trained on synthetic data">
      {compact
        ? "Estimates illustrate the method only; they are not evidence about you."
        : "The active readiness model was trained and evaluated on a simulated development cohort because no consented, assessor-labelled dataset exists yet. Treat estimates as a demonstration of the method, never as evidence about you or your employability."}
    </Notice>
  );
}
