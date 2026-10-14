import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]): string {
  return twMerge(clsx(inputs));
}

export const CATEGORY_LABEL: Record<string, string> = {
  programming: "Programming",
  dsa: "DSA",
  databases: "Databases",
  web: "Web",
  ml_ai: "AI / ML",
  data: "Data",
  cloud_devops: "Cloud & DevOps",
  security: "Security",
  professional: "Professional",
};

export const CATEGORY_COLOR: Record<string, string> = {
  programming: "#7dd3fc",
  dsa: "#a78bfa",
  databases: "#5eead4",
  web: "#f9a8d4",
  ml_ai: "#fbbf24",
  data: "#fdba74",
  cloud_devops: "#93c5fd",
  security: "#fca5a5",
  professional: "#c4b5fd",
};

export const LEVEL_NAMES = ["None", "Awareness", "Working", "Proficient", "Advanced"] as const;

export const STATUS_META: Record<string, { label: string; tone: "ok" | "info" | "warn" | "muted" | "iris"; hint: string }> = {
  assessed: { label: "Assessed", tone: "ok", hint: "From a verified assessment result (highest trust)." },
  verified_evidence: { label: "Verified evidence", tone: "info", hint: "From a project/experience a mentor verified." },
  unverified_evidence: { label: "Unverified evidence", tone: "iris", hint: "Linked to a project/experience not yet verified." },
  self_reported: { label: "Self-reported", tone: "warn", hint: "Your own rating only (lowest trust)." },
  unknown: { label: "Unknown", tone: "muted", hint: "No information recorded yet — not the same as zero." },
};

export const ACTION_META: Record<string, { label: string; tone: "danger" | "warn" | "info" | "ok" | "iris" }> = {
  learn: { label: "Learn", tone: "danger" },
  prerequisite: { label: "Prerequisite first", tone: "warn" },
  assess: { label: "Assess baseline", tone: "info" },
  verify: { label: "Add evidence", tone: "iris" },
  maintain: { label: "Met", tone: "ok" },
};

export const BAND_META: Record<string, { label: string; color: string }> = {
  not_yet_ready: { label: "Not yet interview-ready", color: "#fb7185" },
  developing: { label: "Developing", color: "#fbbf24" },
  interview_ready: { label: "Likely interview-ready", color: "#34d399" },
};

export function pct(v: number | null | undefined, digits = 0): string {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return `${(v * 100).toFixed(digits)}%`;
}

export function level(v: number | null | undefined): string {
  if (v === null || v === undefined) return "Unknown";
  return Number.isInteger(v) ? `${v}` : v.toFixed(1);
}

export function dateTime(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }).format(new Date(iso));
}

export function dateOnly(iso: string | null | undefined): string {
  if (!iso) return "—";
  return new Intl.DateTimeFormat(undefined, { dateStyle: "medium" }).format(new Date(iso));
}

export function relative(iso: string): string {
  const diff = (Date.now() - new Date(iso).getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat(undefined, { numeric: "auto" });
  if (diff < 60) return rtf.format(-Math.round(diff), "second");
  if (diff < 3600) return rtf.format(-Math.round(diff / 60), "minute");
  if (diff < 86400) return rtf.format(-Math.round(diff / 3600), "hour");
  return rtf.format(-Math.round(diff / 86400), "day");
}
