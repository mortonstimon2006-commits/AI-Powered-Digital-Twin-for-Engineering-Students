import { zodResolver } from "@hookform/resolvers/zod";
import { useQueryClient } from "@tanstack/react-query";
import { KeyRound, MailCheck, ShieldCheck } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useState, type ReactNode } from "react";
import { useForm, useWatch } from "react-hook-form";
import { Link, useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";
import { z } from "zod";

import { Brand } from "@/components/layout/Brand";
import { Button } from "@/components/ui/button";
import { Field, Input } from "@/components/ui/form";
import { Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { qk } from "@/lib/queries";
import type { LoginResult } from "@/lib/types";
import { PasswordChecklist, passwordSchema } from "@/components/PasswordChecklist";

function AuthFrame({ title, subtitle, children, footer }: { title: string; subtitle?: ReactNode; children: ReactNode; footer?: ReactNode }) {
  return (
    <div className="grid-bg flex min-h-dvh items-center justify-center px-4 py-10">
      <motion.div initial={{ opacity: 0, y: 14 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.45 }} className="w-full max-w-md">
        <div className="mb-8 flex justify-center">
          <Brand />
        </div>
        <div className="card p-6 sm:p-8">
          <h1 className="text-2xl font-semibold">{title}</h1>
          {subtitle && <p className="mt-1.5 text-sm text-fg-muted">{subtitle}</p>}
          <div className="mt-6">{children}</div>
        </div>
        {footer && <div className="mt-6 text-center text-sm text-fg-muted">{footer}</div>}
      </motion.div>
    </div>
  );
}

function fragmentToken(): string | null {
  const m = window.location.hash.match(/token=([A-Za-z0-9_-]{20,128})/);
  return m ? m[1]! : null;
}

function serverFieldErrors(e: unknown, setError: (name: never, err: { message: string }) => void) {
  if (e instanceof ApiError) {
    for (const [field, message] of Object.entries(e.fieldErrors)) setError(field as never, { message });
    if (e.code === "weak_password" && Array.isArray(e.details)) setError("password" as never, { message: (e.details as string[]).join(" ") });
  }
}

// ------------------------------------------------------------------------- login

const loginSchema = z.object({ email: z.email("Enter a valid email address."), password: z.string().min(1, "Enter your password.") });

export function LoginPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const [params] = useSearchParams();
  const [challenge, setChallenge] = useState<string | null>(null);
  const [code, setCode] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const form = useForm<z.infer<typeof loginSchema>>({ resolver: zodResolver(loginSchema), mode: "onTouched" });
  const next = params.get("next");
  const safeNext = next && next.startsWith("/app") ? next : "/app";

  async function finish(result: LoginResult) {
    if (result.status === "mfa_required") {
      setChallenge(result.mfa_challenge);
      return;
    }
    qc.setQueryData(qk.me, result.me);
    navigate(result.me && !result.me.onboarding_completed && result.me.user.role === "student" ? "/app/onboarding" : safeNext, { replace: true });
  }

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await finish(await api<LoginResult>("/auth/login", { method: "POST", body: values }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Sign-in failed.");
    }
  });

  async function submitMfa(ev: React.FormEvent) {
    ev.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await finish(await api<LoginResult>("/auth/login/mfa", { method: "POST", body: { challenge, code } }));
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Verification failed.");
    } finally {
      setBusy(false);
    }
  }

  if (challenge) {
    return (
      <AuthFrame title="Two-factor verification" subtitle="Enter the 6-digit code from your authenticator app.">
        <form onSubmit={submitMfa} className="space-y-4" noValidate>
          <Field label="Authentication code" error={error ?? undefined}>
            {({ id, describedBy, invalid }) => (
              <Input id={id} aria-describedby={describedBy} aria-invalid={invalid} inputMode="numeric" autoComplete="one-time-code"
                pattern="\d{6}" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} autoFocus />
            )}
          </Field>
          <Button type="submit" className="w-full" loading={busy} disabled={code.length !== 6}>
            <ShieldCheck className="size-4" /> Verify
          </Button>
        </form>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Welcome back" subtitle="Sign in to your digital twin."
      footer={<>New to TwinPath? <Link className="text-aurora hover:underline" to="/register">Create an account</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && <Notice tone="danger">{error}</Notice>}
        <Field label="Email" error={form.formState.errors.email?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("email")} />
          )}
        </Field>
        <Field label="Password" error={form.formState.errors.password?.message}>
          {({ id, describedBy, invalid }) => (
            <Input id={id} type="password" autoComplete="current-password" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("password")} />
          )}
        </Field>
        <div className="flex justify-end">
          <Link to="/forgot-password" className="text-sm text-fg-muted hover:text-aurora">Forgot password?</Link>
        </div>
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>
          <KeyRound className="size-4" /> Sign in
        </Button>
      </form>
    </AuthFrame>
  );
}

// ------------------------------------------------------------------------- register

const registerSchema = z.object({
  display_name: z.string().trim().min(2, "Enter your name.").max(80),
  email: z.email("Enter a valid email address."),
  password: passwordSchema,
  accept_profile_processing: z.literal(true, { error: "Consent is required to use TwinPath." }),
});

export function RegisterPage() {
  const [done, setDone] = useState(false);
  const form = useForm<z.infer<typeof registerSchema>>({ resolver: zodResolver(registerSchema), mode: "onTouched",
    defaultValues: { display_name: "", email: "", password: "", accept_profile_processing: undefined as unknown as true } });
  const password = useWatch({ control: form.control, name: "password" }) ?? "";
  const email = useWatch({ control: form.control, name: "email" }) ?? "";
  const [error, setError] = useState<string | null>(null);

  const onSubmit = form.handleSubmit(async (values) => {
    setError(null);
    try {
      await api("/auth/register", { method: "POST", body: values });
      setDone(true);
    } catch (e) {
      serverFieldErrors(e, form.setError as never);
      setError(e instanceof ApiError ? e.message : "Registration failed.");
    }
  });

  if (done) {
    return (
      <AuthFrame title="Check your inbox" footer={<Link className="text-aurora hover:underline" to="/login">Go to sign in</Link>}>
        <div className="flex gap-3">
          <MailCheck className="size-6 shrink-0 text-aurora" />
          <p className="text-sm text-fg-muted">
            If this address can be registered, your account is ready and a verification link has been sent. For privacy we show the
            same message whether or not an account already exists.
          </p>
        </div>
      </AuthFrame>
    );
  }

  return (
    <AuthFrame title="Create your digital twin" subtitle="It takes about five minutes to set up."
      footer={<>Already registered? <Link className="text-aurora hover:underline" to="/login">Sign in</Link></>}>
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && <Notice tone="danger">{error}</Notice>}
        <Field label="Name" error={form.formState.errors.display_name?.message} required>
          {({ id, describedBy, invalid }) => <Input id={id} autoComplete="name" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("display_name")} />}
        </Field>
        <Field label="Email" error={form.formState.errors.email?.message} required>
          {({ id, describedBy, invalid }) => <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("email")} />}
        </Field>
        <Field label="Password" error={form.formState.errors.password?.message} required>
          {({ id, describedBy, invalid }) => (
            <>
              <Input id={id} type="password" autoComplete="new-password" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("password")} />
              <PasswordChecklist password={password} email={email} />
            </>
          )}
        </Field>
        <label className="flex items-start gap-3 rounded-lg border border-line bg-ink-800/50 p-3 text-sm">
          <input type="checkbox" className="mt-0.5 size-4 accent-[#5eead4]" {...form.register("accept_profile_processing")} />
          <span className="text-fg-muted">
            I agree that TwinPath may process the profile information I enter to provide its features. Optional uses (mentor sharing,
            research use) are off by default and can be changed in Privacy settings.
          </span>
        </label>
        {form.formState.errors.accept_profile_processing && (
          <p role="alert" className="text-xs text-danger">{form.formState.errors.accept_profile_processing.message}</p>
        )}
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>Create account</Button>
      </form>
    </AuthFrame>
  );
}

// ------------------------------------------------------------------------- recovery

export function ForgotPasswordPage() {
  const [sent, setSent] = useState(false);
  const form = useForm<{ email: string }>({ resolver: zodResolver(z.object({ email: z.email("Enter a valid email address.") })) });
  const [error, setError] = useState<string | null>(null);
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await api("/auth/password/forgot", { method: "POST", body: v });
      setSent(true);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Request failed.");
    }
  });
  return (
    <AuthFrame title="Reset your password" subtitle="We'll email you a single-use link that expires in 30 minutes."
      footer={<Link className="text-aurora hover:underline" to="/login">Back to sign in</Link>}>
      {sent ? (
        <Notice tone="ok" title="Request received">If an account exists for this address, a reset link has been sent.</Notice>
      ) : (
        <form onSubmit={onSubmit} className="space-y-4" noValidate>
          {error && <Notice tone="danger">{error}</Notice>}
          <Field label="Email" error={form.formState.errors.email?.message}>
            {({ id, describedBy, invalid }) => <Input id={id} type="email" autoComplete="email" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("email")} />}
          </Field>
          <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>Send reset link</Button>
        </form>
      )}
    </AuthFrame>
  );
}

export function ResetPasswordPage() {
  const [token] = useState(fragmentToken);
  const navigate = useNavigate();
  const form = useForm<{ new_password: string }>({ resolver: zodResolver(z.object({ new_password: passwordSchema })), mode: "onTouched" });
  const pw = useWatch({ control: form.control, name: "new_password" }) ?? "";
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (token) window.history.replaceState(null, "", window.location.pathname); // keep tokens out of history
  }, [token]);
  const onSubmit = form.handleSubmit(async (v) => {
    try {
      await api("/auth/password/reset", { method: "POST", body: { token, ...v } });
      toast.success("Password updated. Please sign in.");
      navigate("/login", { replace: true });
    } catch (e) {
      if (e instanceof ApiError && e.code === "weak_password") form.setError("new_password", { message: (e.details as string[]).join(" ") });
      else setError(e instanceof ApiError ? e.message : "Reset failed.");
    }
  });
  if (!token) {
    return (
      <AuthFrame title="Invalid link">
        <Notice tone="danger">This reset link is missing its token. Request a new one from the sign-in page.</Notice>
      </AuthFrame>
    );
  }
  return (
    <AuthFrame title="Choose a new password">
      <form onSubmit={onSubmit} className="space-y-4" noValidate>
        {error && <Notice tone="danger">{error}</Notice>}
        <Field label="New password" error={form.formState.errors.new_password?.message}>
          {({ id, describedBy, invalid }) => (
            <>
              <Input id={id} type="password" autoComplete="new-password" aria-describedby={describedBy} aria-invalid={invalid} {...form.register("new_password")} />
              <PasswordChecklist password={pw} />
            </>
          )}
        </Field>
        <Button type="submit" className="w-full" loading={form.formState.isSubmitting}>Update password</Button>
      </form>
    </AuthFrame>
  );
}

export function VerifyEmailPage() {
  const [token] = useState(fragmentToken);
  const qc = useQueryClient();
  const [state, setState] = useState<"working" | "ok" | "error">(token ? "working" : "error");
  const [message, setMessage] = useState("This verification link is invalid.");
  useEffect(() => {
    if (!token) return;
    window.history.replaceState(null, "", window.location.pathname);
    api("/auth/email/verify", { method: "POST", body: { token } })
      .then(() => {
        setState("ok");
        void qc.invalidateQueries({ queryKey: qk.me });
      })
      .catch((e) => {
        setState("error");
        setMessage(e instanceof ApiError ? e.message : "Verification failed.");
      });
  }, [token, qc]);
  return (
    <AuthFrame title="Email verification" footer={<Link className="text-aurora hover:underline" to="/app">Continue to TwinPath</Link>}>
      {state === "working" && <p className="text-sm text-fg-muted" role="status">Verifying…</p>}
      {state === "ok" && <Notice tone="ok" title="Your email address is verified." />}
      {state === "error" && <Notice tone="danger">{message}</Notice>}
    </AuthFrame>
  );
}
