import { useMutation, useQuery } from "@tanstack/react-query";
import { Download, KeyRound, Laptop, MonitorSmartphone, Settings, ShieldCheck, Trash2 } from "lucide-react";
import { useState } from "react";
import { useNavigate, useSearchParams } from "react-router";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { Button } from "@/components/ui/button";
import { Field, Input, Select, Switch } from "@/components/ui/form";
import { ConfirmButton, Dialog, TabPanel, Tabs } from "@/components/ui/overlay";
import { Badge, Card, CardBody, CardHeader } from "@/components/ui/primitives";
import { ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError, download } from "@/lib/api";
import { queryClient, useMe } from "@/lib/queries";
import { dateTime } from "@/lib/utils";
import { setVisualsPref, useVisualsPref } from "@/lib/visuals";
import { PasswordChecklist } from "@/components/PasswordChecklist";

function SecurityTab() {
  const me = useMe();
  const sessions = useQuery({ queryKey: ["sessions"], queryFn: () => api<{ id: string; created_at: string; last_seen_at: string; user_agent: string | null; ip_prefix: string | null; current: boolean }[]>("/auth/sessions") });
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [mfa, setMfa] = useState<{ secret: string; otpauth_uri: string } | null>(null);
  const [code, setCode] = useState("");
  const [disable, setDisable] = useState({ open: false, password: "", code: "" });
  const change = useMutation({
    mutationFn: () => api("/auth/password/change", { method: "POST", body: { current_password: current, new_password: next } }),
    onSuccess: () => { toast.success("Password changed. Other sessions were signed out."); setCurrent(""); setNext(""); void sessions.refetch(); },
    onError: (e) => toast.error(e instanceof ApiError ? (Array.isArray(e.details) ? (e.details as string[]).join(" ") : e.message) : "Failed."),
  });
  const mfaEnabled = me.data?.user.mfa_enabled;
  async function verifyMfa() {
    try {
      await api("/auth/mfa/verify", { method: "POST", body: { code } });
      toast.success("Two-factor authentication enabled.");
      setMfa(null);
      setCode("");
      await queryClient.invalidateQueries({ queryKey: ["me"] });
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Invalid code.");
    }
  }
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title="Change password" description="Other sessions are signed out after a change." />
        <CardBody className="space-y-4">
          <Field label="Current password">{({ id }) => <Input id={id} type="password" autoComplete="current-password" value={current} onChange={(e) => setCurrent(e.target.value)} />}</Field>
          <Field label="New password">{({ id }) => <><Input id={id} type="password" autoComplete="new-password" value={next} onChange={(e) => setNext(e.target.value)} /><PasswordChecklist password={next} email={me.data?.user.email} /></>}</Field>
          <div className="flex justify-end"><Button onClick={() => change.mutate()} loading={change.isPending} disabled={!current || next.length < 12}><KeyRound className="size-4" /> Update password</Button></div>
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Two-factor authentication" description="Time-based one-time codes from an authenticator app." actions={<Badge tone={mfaEnabled ? "ok" : "muted"}>{mfaEnabled ? "enabled" : "off"}</Badge>} />
        <CardBody className="space-y-4">
          {mfaEnabled ? (
            <Button variant="secondary" onClick={() => setDisable({ open: true, password: "", code: "" })}>Disable two-factor</Button>
          ) : mfa ? (
            <div className="space-y-3">
              <p className="text-sm text-fg-muted">Add this key to your authenticator app (manual entry), then enter the 6-digit code it shows.</p>
              <p className="break-all rounded-lg bg-ink-800 p-3 font-mono text-sm tracking-widest">{mfa.secret.match(/.{1,4}/g)?.join(" ")}</p>
              <Field label="Verification code">{({ id }) => <Input id={id} inputMode="numeric" maxLength={6} value={code} onChange={(e) => setCode(e.target.value.replace(/\D/g, ""))} />}</Field>
              <Button onClick={verifyMfa} disabled={code.length !== 6}><ShieldCheck className="size-4" /> Confirm and enable</Button>
            </div>
          ) : (
            <Button onClick={async () => setMfa(await api("/auth/mfa/setup", { method: "POST" }))}><ShieldCheck className="size-4" /> Set up two-factor</Button>
          )}
        </CardBody>
      </Card>
      <Card className="lg:col-span-2">
        <CardHeader title="Active sessions" description="Sign out of devices you don't recognise."
          actions={<Button variant="secondary" size="sm" onClick={async () => { const r = await api<{ message: string }>("/auth/sessions/revoke-others", { method: "POST" }); toast.success(r.message); void sessions.refetch(); }}>Sign out other sessions</Button>} />
        <CardBody>
          {sessions.isLoading ? <LoadingBlock rows={2} /> : sessions.error ? <ErrorState error={sessions.error} /> : (
            <ul className="divide-y divide-line">
              {sessions.data!.map((s) => (
                <li key={s.id} className="flex flex-wrap items-center gap-3 py-3 text-sm">
                  {/Mobile|Android|iPhone/i.test(s.user_agent ?? "") ? <MonitorSmartphone className="size-4 text-fg-faint" /> : <Laptop className="size-4 text-fg-faint" />}
                  <span className="min-w-0 flex-1 truncate text-fg-muted">{s.user_agent ?? "Unknown device"}</span>
                  <span className="text-xs text-fg-faint">last active {dateTime(s.last_seen_at)} · {s.ip_prefix ?? "—"}</span>
                  {s.current ? <Badge tone="aurora">this device</Badge> : (
                    <Button variant="ghost" size="sm" onClick={async () => { await api(`/auth/sessions/${s.id}`, { method: "DELETE" }); void sessions.refetch(); }}>Revoke</Button>
                  )}
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
      <Dialog open={disable.open} onOpenChange={(o) => setDisable((d) => ({ ...d, open: o }))} title="Disable two-factor authentication">
        <div className="space-y-3">
          <Field label="Password">{({ id }) => <Input id={id} type="password" value={disable.password} onChange={(e) => setDisable((d) => ({ ...d, password: e.target.value }))} />}</Field>
          <Field label="Current code">{({ id }) => <Input id={id} inputMode="numeric" maxLength={6} value={disable.code} onChange={(e) => setDisable((d) => ({ ...d, code: e.target.value.replace(/\D/g, "") }))} />}</Field>
          <div className="flex justify-end"><Button variant="danger" onClick={async () => {
            try { await api("/auth/mfa/disable", { method: "POST", body: { password: disable.password, code: disable.code } }); toast.success("Two-factor disabled."); setDisable({ open: false, password: "", code: "" }); await queryClient.invalidateQueries({ queryKey: ["me"] }); }
            catch (e) { toast.error(e instanceof ApiError ? e.message : "Failed."); }
          }}>Disable</Button></div>
        </div>
      </Dialog>
    </div>
  );
}

function PrivacyTab() {
  const consents = useQuery({ queryKey: ["consents"], queryFn: () => api<{ items: { purpose: string; description: string; required: boolean; granted: boolean; updated_at: string | null }[] }>("/privacy/consents") });
  const policy = useQuery({ queryKey: ["policy"], queryFn: () => api<{ retention_days: Record<string, number>; local_ai: Record<string, string>; network_connections: string[]; not_collected: string[] }>("/privacy/policy") });
  const navigate = useNavigate();
  const [pw, setPw] = useState("");
  const [confirmText, setConfirmText] = useState("");
  async function toggle(purpose: string, granted: boolean) {
    try {
      await api(`/privacy/consents/${purpose}`, { method: "PUT", body: { granted } });
      await consents.refetch();
      await queryClient.invalidateQueries({ queryKey: ["profile"] });
      toast.success(granted ? "Consent granted." : "Consent withdrawn.");
    } catch (e) {
      toast.error(e instanceof ApiError ? e.message : "Could not update consent.");
    }
  }
  return (
    <div className="grid gap-5 lg:grid-cols-2">
      <Card>
        <CardHeader title="Consents" description="Optional uses are off unless you turn them on. Changes apply immediately." />
        <CardBody>
          {consents.isLoading ? <LoadingBlock rows={3} /> : (
            <ul className="divide-y divide-line">
              {consents.data?.items.map((c) => (
                <li key={c.purpose} className="flex items-start justify-between gap-4 py-3">
                  <div>
                    <p className="text-sm font-medium capitalize">{c.purpose.replaceAll("_", " ")} {c.required && <Badge tone="muted">required</Badge>}</p>
                    <p className="mt-0.5 text-xs text-fg-muted">{c.description}</p>
                  </div>
                  <Switch label={`Consent: ${c.purpose}`} checked={c.granted} disabled={c.required} onCheckedChange={(v) => toggle(c.purpose, v)} />
                </li>
              ))}
            </ul>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="How your data is handled" />
        <CardBody className="space-y-3 text-sm text-fg-muted">
          {policy.data && (
            <>
              <p><span className="text-fg">AI:</span> {policy.data.local_ai.runtime} with {policy.data.local_ai.chat_model} and {policy.data.local_ai.embed_model}. External AI APIs: {policy.data.local_ai.external_ai_apis}.</p>
              <p><span className="text-fg">Retention:</span> documents {policy.data.retention_days.documents} days · mentor conversations {policy.data.retention_days.mentor_conversations} days.</p>
              <p><span className="text-fg">Never collected:</span> {policy.data.not_collected.join(", ")}.</p>
              <div><p className="text-fg">Network connections the system makes:</p><ul className="mt-1 list-disc pl-5 text-xs">{policy.data.network_connections.map((n) => <li key={n}>{n}</li>)}</ul></div>
            </>
          )}
        </CardBody>
      </Card>
      <Card>
        <CardHeader title="Export your data" description="A complete JSON export of everything stored about you (secrets excluded)." />
        <CardBody><Button variant="secondary" onClick={() => download("/privacy/export", "twinpath-export.json").catch(() => toast.error("Export failed."))}><Download className="size-4" /> Download export</Button></CardBody>
      </Card>
      <Card className="border-danger/30">
        <CardHeader title="Delete account" description="Permanently deletes your profile, documents, conversations and all derived data. This cannot be undone." />
        <CardBody className="space-y-3">
          <Field label="Password">{({ id }) => <Input id={id} type="password" autoComplete="current-password" value={pw} onChange={(e) => setPw(e.target.value)} />}</Field>
          <Field label='Type "DELETE MY ACCOUNT" to confirm'>{({ id }) => <Input id={id} value={confirmText} onChange={(e) => setConfirmText(e.target.value)} />}</Field>
          <ConfirmButton
            trigger={<Button variant="danger" disabled={!pw || confirmText !== "DELETE MY ACCOUNT"}><Trash2 className="size-4" /> Delete my account</Button>}
            title="Delete your account permanently?" description="All of your data, files and mentor history are erased immediately. You will be signed out."
            confirmLabel="Delete permanently"
            onConfirm={async () => {
              try {
                await api("/privacy/delete-account", { method: "POST", body: { password: pw, confirmation: confirmText } });
                queryClient.clear();
                toast.success("Your account has been deleted.");
                navigate("/", { replace: true });
              } catch (e) {
                toast.error(e instanceof ApiError ? e.message : "Deletion failed.");
              }
            }} />
        </CardBody>
      </Card>
    </div>
  );
}

function PreferencesTab() {
  const pref = useVisualsPref();
  return (
    <Card className="max-w-2xl">
      <CardHeader title="Display preferences" description="Stored only in this browser." />
      <CardBody className="space-y-4">
        <Field label="3D visuals" hint="Auto disables 3D when your system requests reduced motion or WebGL is unavailable. A 2D equivalent is always available.">
          {({ id, describedBy }) => (
            <Select id={id} aria-describedby={describedBy} className="w-56" value={pref} onChange={(e) => setVisualsPref(e.target.value as "on" | "off" | "auto")}>
              <option value="auto">Automatic</option><option value="on">Always on</option><option value="off">Off (2D only)</option>
            </Select>
          )}
        </Field>
        <Notice tone="info">Animations also follow your operating system's "reduce motion" setting.</Notice>
      </CardBody>
    </Card>
  );
}

export function SettingsPage() {
  const [params, setParams] = useSearchParams();
  const tab = params.get("tab") ?? "security";
  const me = useMe();
  return (
    <div>
      <PageHeader icon={Settings} eyebrow="Account" title="Settings, privacy & data" description={me.data ? `Signed in as ${me.data.user.email}` : undefined} />
      {me.data && !me.data.user.email_verified && (
        <Notice tone="info" className="mb-5" title="Email not verified">
          <Button variant="ghost" size="sm" onClick={async () => { await api("/auth/email/resend", { method: "POST" }); toast.success("If your address is unverified, a new link was sent."); }}>Resend verification email</Button>
        </Notice>
      )}
      <Tabs value={tab} onValueChange={(v) => setParams({ tab: v }, { replace: true })} items={[{ value: "security", label: "Security" }, { value: "privacy", label: "Privacy & data" }, { value: "preferences", label: "Preferences" }]}>
        <div className="pt-6">
          <TabPanel value="security"><SecurityTab /></TabPanel>
          <TabPanel value="privacy"><PrivacyTab /></TabPanel>
          <TabPanel value="preferences"><PreferencesTab /></TabPanel>
        </div>
      </Tabs>
    </div>
  );
}
