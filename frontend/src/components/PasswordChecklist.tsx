import { CheckCircle2 } from "lucide-react";
import { z } from "zod";

import { cn } from "@/lib/utils";

/** Password policy feedback (mirrors the backend rules; the server remains authoritative). */

const COMMON = ["password", "123456", "qwerty", "letmein", "welcome", "admin", "twinpath", "student"];
export function passwordChecks(pw: string, email = "") {
  const local = email.split("@")[0]?.toLowerCase() ?? "";
  return [
    { ok: pw.length >= 12, label: "At least 12 characters" },
    { ok: pw.length <= 128, label: "At most 128 characters" },
    { ok: !COMMON.some((c) => pw.toLowerCase().startsWith(c)), label: "Not a common password" },
    { ok: !(local.length >= 4 && pw.toLowerCase().includes(local)), label: "Does not contain your email name" },
    { ok: new Set(pw).size > 3, label: "Not just a few repeated characters" },
  ];
}

export const passwordSchema = z.string().min(12, "Use at least 12 characters.").max(128, "Use at most 128 characters.");

export function PasswordChecklist({ password, email }: { password: string; email?: string }) {
  const checks = passwordChecks(password, email);
  return (
    <ul className="mt-2 grid gap-1 text-xs sm:grid-cols-2" aria-label="Password requirements">
      {checks.map((c) => (
        <li key={c.label} className={cn("flex items-center gap-1.5", c.ok ? "text-ok" : "text-fg-faint")}>
          <CheckCircle2 className="size-3.5" aria-hidden /> {c.label}
          <span className="sr-only">{c.ok ? "met" : "not met"}</span>
        </li>
      ))}
    </ul>
  );
}

