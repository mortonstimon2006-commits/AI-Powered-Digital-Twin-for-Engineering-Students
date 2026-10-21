import { MessageSquarePlus } from "lucide-react";
import { useState } from "react";
import { useLocation } from "react-router";
import { toast } from "sonner";

import { Button } from "@/components/ui/button";
import { Field, Select, Textarea } from "@/components/ui/form";
import { Dialog } from "@/components/ui/overlay";
import { api, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

/** Areas people can comment on; values are the server's feedback target types. */
export const FEEDBACK_AREAS = [
  ["general", "Overall experience"],
  ["role_recommendation", "Role explorer"],
  ["gap_analysis", "Skill gaps"],
  ["prediction", "Readiness estimate"],
  ["simulation", "What-if simulator"],
  ["resource", "Learning resources"],
] as const;

type Area = (typeof FEEDBACK_AREAS)[number][0];

const RATINGS = ["Not useful", "Slightly useful", "Somewhat useful", "Useful", "Very useful"] as const;
const MAX_COMMENT = 1000;

function areaForPath(path: string): Area {
  if (path.startsWith("/app/gaps")) return "gap_analysis";
  if (path.startsWith("/app/readiness")) return "prediction";
  if (path.startsWith("/app/simulator")) return "simulation";
  if (path.startsWith("/app/roles")) return "role_recommendation";
  return "general";
}

function FeedbackForm({ page, onDone }: { page: string; onDone: () => void }) {
  const [area, setArea] = useState<Area>(() => areaForPath(page));
  const [rating, setRating] = useState<number | null>(null);
  const [comment, setComment] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit() {
    if (rating === null) return;
    setBusy(true);
    try {
      const res = await api<{ message: string }>("/feedback", {
        method: "POST",
        body: { target_type: area, target_id: page.slice(0, 64), rating, comment: comment.trim() },
      });
      toast.success(res.message);
      onDone();
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not send feedback.");
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="space-y-5">
      <Field label="What is it about?">
        {({ id }) => (
          <Select id={id} value={area} onChange={(e) => setArea(e.target.value as Area)}>
            {FEEDBACK_AREAS.map(([value, label]) => <option key={value} value={value}>{label}</option>)}
          </Select>
        )}
      </Field>
      <fieldset>
        <legend className="mb-2 text-sm font-medium">How useful is it? <span className="text-danger" aria-hidden>*</span></legend>
        <div className="grid grid-cols-5 gap-2">
          {RATINGS.map((label, i) => {
            const value = i + 1;
            const on = rating === value;
            return (
              <button key={value} type="button" aria-pressed={on} aria-label={`${value} – ${label}`} onClick={() => setRating(value)}
                className={cn("rounded-lg border py-2 font-display text-lg font-semibold transition",
                  on ? "border-aurora/60 bg-aurora/10 text-aurora" : "border-line text-fg-muted hover:text-fg")}>
                {value}
              </button>
            );
          })}
        </div>
        <div className="mt-1.5 flex justify-between text-xs text-fg-faint"><span>{RATINGS[0]}</span><span>{RATINGS[4]}</span></div>
      </fieldset>
      <Field label="Comment" hint={`Optional. ${comment.length}/${MAX_COMMENT} characters. Please don't include personal details.`}>
        {({ id, describedBy }) => (
          <Textarea id={id} aria-describedby={describedBy} rows={4} maxLength={MAX_COMMENT} value={comment}
            placeholder="What worked, what was confusing, what would you change?" onChange={(e) => setComment(e.target.value)} />
        )}
      </Field>
      <div className="flex justify-end">
        <Button onClick={submit} loading={busy} disabled={rating === null}>Send feedback</Button>
      </div>
    </div>
  );
}

export function FeedbackButton() {
  const [open, setOpen] = useState(false);
  const { pathname } = useLocation();
  return (
    <>
      <Button variant="secondary" size="sm" className="w-full justify-start" onClick={() => setOpen(true)}>
        <MessageSquarePlus className="size-4" /> Send feedback
      </Button>
      <Dialog open={open} onOpenChange={setOpen} title="Send feedback"
        description="Administrators see your rating and comment without your name or email. Thank you for helping improve the app.">
        {/* Remounted on each open, so the form always starts empty and matches the current page. */}
        {open && <FeedbackForm key={pathname} page={pathname} onDone={() => setOpen(false)} />}
      </Dialog>
    </>
  );
}
