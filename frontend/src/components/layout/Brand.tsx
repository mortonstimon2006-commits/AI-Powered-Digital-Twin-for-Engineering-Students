import { useId } from "react";
import { Link } from "react-router";

import { cn } from "@/lib/utils";

export function BrandMark({ className }: { className?: string }) {
  // Unique per instance: duplicate gradient ids resolve to the first (possibly hidden) SVG.
  const gid = `tp-g-${useId().replace(/:/g, "")}`;
  return (
    <svg viewBox="0 0 64 64" className={cn("size-8", className)} aria-hidden>
      <defs>
        <linearGradient id={gid} x1="0" y1="0" x2="1" y2="1">
          <stop offset="0" stopColor="#5eead4" />
          <stop offset="1" stopColor="#a78bfa" />
        </linearGradient>
      </defs>
      <rect width="64" height="64" rx="16" fill="#0a0f1c" stroke="#233049" />
      <circle cx="24" cy="32" r="10" fill="none" stroke={`url(#${gid})`} strokeWidth="3.5" />
      <circle cx="40" cy="32" r="10" fill="none" stroke={`url(#${gid})`} strokeWidth="3.5" opacity=".7" />
      <circle cx="32" cy="32" r="3" fill="#e8edf6" />
    </svg>
  );
}

export function Brand({ to = "/", compact = false }: { to?: string; compact?: boolean }) {
  return (
    <Link to={to} className="group inline-flex items-center gap-2.5 rounded-lg" aria-label="TwinPath AI home">
      <BrandMark className="transition-transform duration-300 group-hover:rotate-[8deg]" />
      {!compact && (
        <span className="font-display text-[1.05rem] font-semibold tracking-tight">
          TwinPath <span className="text-gradient">AI</span>
        </span>
      )}
    </Link>
  );
}
