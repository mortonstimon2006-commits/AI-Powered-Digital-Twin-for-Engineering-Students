import { zodResolver } from "@hookform/resolvers/zod";
import { useEffect } from "react";
import { useForm } from "react-hook-form";
import { Link } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { Button } from "@/components/ui/button";
import { Field, Input, Textarea } from "@/components/ui/form";
import { Card, CardBody, CardHeader } from "@/components/ui/primitives";
import { ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { invalidateTwin, useProfile } from "@/lib/queries";

const optionalNumber = (min: number, max: number) =>
  z.union([z.literal("").transform(() => null), z.null(), z.coerce.number().min(min, `${min}–${max}`).max(max, `${min}–${max}`)]);

const schema = z.object({
  degree: z.string().trim().max(80),
  specialization: z.string().trim().max(80),
  current_semester: optionalNumber(1, 12),
  graduation_year: optionalNumber(2000, 2100),
  cgpa: optionalNumber(0, 10),
  attendance_pct: optionalNumber(0, 100),
  headline: z.string().trim().max(160),
  academic_achievements: z.string().trim().max(2000),
});

export function AcademicSection() {
  const profile = useProfile();
  const form = useForm<z.input<typeof schema>, unknown, z.output<typeof schema>>({ resolver: zodResolver(schema), mode: "onTouched" });
  useEffect(() => {
    const p = profile.data;
    if (p) {
      form.reset({ degree: p.degree ?? "", specialization: p.specialization ?? "", current_semester: p.current_semester ?? "",
        graduation_year: p.graduation_year ?? "", cgpa: p.cgpa ?? "", attendance_pct: p.attendance_pct ?? "",
        headline: p.headline, academic_achievements: p.academic_achievements });
    }
  }, [profile.data, form]);
  if (profile.isLoading) return <LoadingBlock rows={3} />;
  if (profile.error) return <ErrorState error={profile.error} onRetry={() => profile.refetch()} />;
  const consent = profile.data!.attendance_consent;
  const submit = form.handleSubmit(async (v) => {
    try {
      const body: Record<string, unknown> = { ...v, degree: v.degree || null, specialization: v.specialization || null };
      if (!consent) delete body.attendance_pct;
      await api("/profile", { method: "PATCH", body });
      await invalidateTwin();
      toast.success("Profile saved — a new twin version was recorded.");
    } catch (e) {
      if (e instanceof ApiError) {
        for (const [f, m] of Object.entries(e.fieldErrors)) form.setError(f as keyof z.input<typeof schema>, { message: m });
        toast.error(e.message);
      }
    }
  });
  const e = form.formState.errors;
  return (
    <Card>
      <CardHeader title="Academic information" description="Only what's needed for analysis. Every saved change creates a twin snapshot." />
      <CardBody>
        <form onSubmit={submit} className="grid gap-4 sm:grid-cols-2" noValidate>
          <Field label="Degree" error={e.degree?.message}>{({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("degree")} />}</Field>
          <Field label="Specialization" error={e.specialization?.message}>{({ id, describedBy, invalid }) => <Input id={id} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("specialization")} />}</Field>
          <Field label="Current semester" error={e.current_semester?.message}>{({ id, describedBy, invalid }) => <Input id={id} type="number" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("current_semester")} />}</Field>
          <Field label="Graduation year" error={e.graduation_year?.message}>{({ id, describedBy, invalid }) => <Input id={id} type="number" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("graduation_year")} />}</Field>
          <Field label="CGPA (0–10)" error={e.cgpa?.message}>{({ id, describedBy, invalid }) => <Input id={id} type="number" step="0.01" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("cgpa")} />}</Field>
          {consent ? (
            <Field label="Attendance %" hint="Stored because you granted the attendance-data consent." error={e.attendance_pct?.message}>
              {({ id, describedBy, invalid }) => <Input id={id} type="number" step="0.1" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("attendance_pct")} />}
            </Field>
          ) : (
            <Notice tone="info" className="self-end">Attendance is not collected unless you opt in under <Link className="text-aurora underline" to="/app/settings?tab=privacy">Privacy</Link>.</Notice>
          )}
          <Field label="Headline" className="sm:col-span-2" error={e.headline?.message}>{({ id, describedBy, invalid }) => <Input id={id} placeholder="Aspiring data analyst focused on product metrics" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("headline")} />}</Field>
          <Field label="Academic achievements" className="sm:col-span-2" error={e.academic_achievements?.message}>{({ id, describedBy, invalid }) => <Textarea id={id} aria-describedby={describedBy} aria-invalid={invalid} {...form.register("academic_achievements")} />}</Field>
          <div className="flex justify-end sm:col-span-2">
            <Button type="submit" loading={form.formState.isSubmitting} disabled={!form.formState.isDirty}>Save changes</Button>
          </div>
        </form>
      </CardBody>
    </Card>
  );
}
