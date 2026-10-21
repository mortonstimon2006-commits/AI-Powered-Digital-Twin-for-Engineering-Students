import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Bot, BookOpen, Cpu, MessageSquarePlus, Send, Square, ThumbsDown, ThumbsUp, Trash2, UserRound } from "lucide-react";
import { AnimatePresence, motion } from "motion/react";
import { useEffect, useRef, useState } from "react";
import { toast } from "sonner";

import { PageHeader } from "@/components/layout/AppShell";
import { SafeMarkdown } from "@/components/SafeMarkdown";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/form";
import { ConfirmButton } from "@/components/ui/overlay";
import { Badge, Card } from "@/components/ui/primitives";
import { ErrorState, LoadingBlock, Notice } from "@/components/ui/states";
import { api, ApiError } from "@/lib/api";
import { qk, queryClient, useMentorStatus } from "@/lib/queries";
import { postSse } from "@/lib/sse";
import type { MentorSource } from "@/lib/types";
import { cn, relative } from "@/lib/utils";

interface Msg {
  id?: string;
  role: "user" | "assistant";
  content: string;
  sources?: MentorSource[];
  status?: string;
  model?: string;
  latency_ms?: number | null;
  unverified?: string[];
  removedLinks?: number;
  sections?: string[];
  pending?: boolean;
  error?: string;
}

const STARTERS = [
  "What should I focus on first for my target role, and why?",
  "Explain my readiness estimate and its limitations.",
  "Break my next roadmap item into a two-week plan.",
  "How should I prepare for a technical mock interview?",
];

function SourceList({ sources, highlight }: { sources: MentorSource[]; highlight: string | null }) {
  if (!sources.length) return null;
  return (
    <div className="mt-3 rounded-lg border border-line bg-ink-900/60 p-3">
      <p className="eyebrow mb-2 flex items-center gap-1.5"><BookOpen className="size-3" /> Retrieved evidence (knowledge base / your documents)</p>
      <ul className="space-y-2">
        {sources.map((s) => (
          <li key={s.ref} id={`src-${s.ref}`} className={cn("rounded-md p-2 text-xs transition", highlight === s.ref ? "bg-aurora/10" : "")}>
            <p className="flex flex-wrap items-center gap-2"><Badge tone="aurora">{s.ref}</Badge><span className="text-fg">{s.title}</span>{s.section && <span className="text-fg-faint">· {s.section}</span>}
              <Badge tone={s.scope === "private" ? "iris" : "muted"}>{s.scope === "private" ? "your document" : "knowledge base"}</Badge></p>
            <p className="mt-1 line-clamp-2 text-fg-muted">{s.excerpt}</p>
          </li>
        ))}
      </ul>
    </div>
  );
}

function AssistantBubble({ m }: { m: Msg }) {
  const [cite, setCite] = useState<string | null>(null);
  async function rate(r: number) {
    if (!m.id) return;
    try {
      await api("/feedback", { method: "POST", body: { target_type: "mentor_message", target_id: m.id, rating: r } });
      toast.success("Feedback recorded.");
    } catch {
      toast.error("Could not send feedback.");
    }
  }
  return (
    <div className="flex gap-3">
      <div className="grid size-8 shrink-0 place-items-center rounded-full bg-gradient-to-br from-aurora/25 to-iris/25"><Bot className="size-4 text-aurora" /></div>
      <div className="min-w-0 flex-1">
        <p className="mb-1.5 flex flex-wrap items-center gap-2 text-[0.7rem] text-fg-faint">
          <span>AI-generated advice · {m.model ?? "local model"} via Ollama</span>
          {m.latency_ms ? <span className="metric">{(m.latency_ms / 1000).toFixed(1)} s</span> : null}
          {m.sections?.length ? <span>context: {m.sections.join(", ")}</span> : null}
        </p>
        <div className="rounded-2xl rounded-tl-sm border border-line bg-ink-800/70 px-4 py-3">
          {m.content ? <SafeMarkdown text={m.content} onCite={(r) => { setCite(r); document.getElementById(`src-${r}`)?.scrollIntoView({ behavior: "smooth", block: "nearest" }); }} />
            : m.pending ? <span className="inline-flex gap-1" aria-label="Generating"><span className="size-1.5 animate-pulse rounded-full bg-aurora" /><span className="size-1.5 animate-pulse rounded-full bg-aurora [animation-delay:150ms]" /><span className="size-1.5 animate-pulse rounded-full bg-aurora [animation-delay:300ms]" /></span> : null}
          {m.pending && m.content && <span className="ml-0.5 inline-block h-4 w-1.5 animate-pulse bg-aurora align-middle" aria-hidden />}
          {m.error && <Notice tone="danger" className="mt-2">{m.error}</Notice>}
          {m.unverified && m.unverified.length > 0 && (
            <Notice tone="warn" className="mt-3" icon={<AlertTriangle className="size-4" />} title="Check these numbers">
              This answer mentions {m.unverified.join(", ")}, which do not appear in your profile record or the retrieved sources.
            </Notice>
          )}
          {m.removedLinks ? (
            <p className="mt-2 text-xs text-fg-faint">{m.removedLinks} link(s) the model wrote were removed because they are not in the app's verified resource catalogue.</p>
          ) : null}
          {m.status === "cancelled" && <p className="mt-2 text-xs text-fg-faint">Generation stopped.</p>}
          <SourceList sources={m.sources ?? []} highlight={cite} />
        </div>
        {m.id && m.status === "complete" && (
          <div className="mt-1 flex items-center gap-1 text-xs text-fg-faint">
            Helpful? <Button variant="ghost" size="icon" className="size-7" aria-label="Helpful" onClick={() => rate(5)}><ThumbsUp className="size-3.5" /></Button>
            <Button variant="ghost" size="icon" className="size-7" aria-label="Not helpful" onClick={() => rate(1)}><ThumbsDown className="size-3.5" /></Button>
          </div>
        )}
      </div>
    </div>
  );
}

export function MentorPage() {
  const status = useMentorStatus();
  const convs = useQuery({ queryKey: qk.conversations, queryFn: () => api<{ items: { id: string; title: string; updated_at: string }[] }>("/mentor/conversations") });
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Msg[]>([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const abort = useRef<AbortController | null>(null);
  const endRef = useRef<HTMLDivElement>(null);

  useEffect(() => { endRef.current?.scrollIntoView({ behavior: "smooth", block: "end" }); }, [messages]);

  async function openConversation(id: string) {
    setConversationId(id);
    const c = await api<{ messages: { id: string; role: "user" | "assistant"; content: string; sources: MentorSource[]; status: string; model_tag: string; latency_ms: number | null; context_sections: string[] }[] }>(`/mentor/conversations/${id}`);
    setMessages(c.messages.map((m) => ({ id: m.id, role: m.role, content: m.content, sources: m.sources, status: m.status, model: m.model_tag, latency_ms: m.latency_ms, sections: m.context_sections })));
  }

  async function send(text: string) {
    const question = text.trim();
    if (!question || busy) return;
    setInput("");
    setBusy(true);
    const controller = new AbortController();
    abort.current = controller;
    setMessages((m) => [...m, { role: "user", content: question }, { role: "assistant", content: "", pending: true }]);
    const patch = (fn: (m: Msg) => Msg) => setMessages((all) => all.map((m, i) => (i === all.length - 1 ? fn(m) : m)));
    try {
      await postSse("/mentor/ask", { question, conversation_id: conversationId }, {
        onEvent: (event, data) => {
          if (event === "meta") {
            setConversationId(String(data.conversation_id));
            patch((m) => ({ ...m, sources: data.sources as MentorSource[], model: String(data.model), sections: data.context_sections as string[] }));
          } else if (event === "delta") patch((m) => ({ ...m, content: m.content + String(data.text) }));
          else if (event === "done") patch((m) => ({ ...m, pending: false, id: String(data.message_id), status: String(data.status), latency_ms: Number(data.latency_ms),
            unverified: data.unverified_numbers as string[], removedLinks: Number(data.removed_links ?? 0),
            content: typeof data.content === "string" ? data.content : m.content }));
          else if (event === "error") patch((m) => ({ ...m, pending: false, error: String(data.message) }));
        },
      }, controller.signal);
    } catch (e) {
      if ((e as Error).name === "AbortError") patch((m) => ({ ...m, pending: false, status: "cancelled" }));
      else patch((m) => ({ ...m, pending: false, error: e instanceof ApiError ? e.message : "The Personalized Mentor request failed." }));
    } finally {
      setBusy(false);
      abort.current = null;
      void queryClient.invalidateQueries({ queryKey: qk.conversations });
    }
  }

  const online = status.data?.available;
  return (
    <div>
      <PageHeader icon={Bot} eyebrow="Runs locally and privately" title="Personalized Mentor"
        description="Answers are grounded in your profile record and retrieved guidance documents. The model runs locally; nothing is sent to an external AI service." />
      <div className="grid gap-5 lg:grid-cols-[260px_1fr]">
        <Card className="h-fit p-3">
          <Button className="w-full" variant="secondary" onClick={() => { setConversationId(null); setMessages([]); }}><MessageSquarePlus className="size-4" /> New conversation</Button>
          <div className="mt-3 space-y-1">
            {convs.isLoading ? <LoadingBlock rows={2} /> : convs.data?.items.map((c) => (
              <div key={c.id} className={cn("group flex items-center gap-1 rounded-lg px-2 py-1.5 text-sm", conversationId === c.id ? "bg-white/[0.06]" : "hover:bg-white/[0.03]")}>
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => openConversation(c.id)}>
                  <span className="block truncate">{c.title}</span><span className="text-[0.68rem] text-fg-faint">{relative(c.updated_at)}</span>
                </button>
                <ConfirmButton trigger={<Button variant="ghost" size="icon" className="size-7 opacity-60 group-hover:opacity-100" aria-label={`Delete ${c.title}`}><Trash2 className="size-3.5" /></Button>}
                  title="Delete conversation?" description="The conversation and its messages are permanently removed." confirmLabel="Delete"
                  onConfirm={async () => { await api(`/mentor/conversations/${c.id}`, { method: "DELETE" }); if (conversationId === c.id) { setConversationId(null); setMessages([]); } await convs.refetch(); }} />
              </div>
            ))}
          </div>
        </Card>

        <Card className="flex min-h-[620px] flex-col">
          <div className="flex flex-wrap items-center justify-between gap-2 border-b border-line px-4 py-3">
            <div className="flex items-center gap-2 text-sm">
              <span className={cn("size-2 rounded-full", online ? "bg-ok shadow-[0_0_8px] shadow-ok/60" : "bg-danger")} />
              {online ? "Local model online" : "Mentor unavailable"}
              <span className="flex items-center gap-1 font-mono text-[0.7rem] text-fg-faint"><Cpu className="size-3" /> {status.data?.chat_model} · {status.data?.embed_model}</span>
            </div>
            {status.data?.queue && Number(status.data.queue.waiting) > 0 && <Badge tone="warn">{status.data.queue.waiting} waiting</Badge>}
          </div>
          <div className="flex-1 space-y-6 overflow-y-auto px-4 py-5" aria-live="polite">
            {!online && !status.isLoading && (
              <Notice tone="warn" title="The Personalized Mentor is offline">The Ollama service or the configured model isn't running, so no answers are generated. Everything else in the app keeps working.</Notice>
            )}
            {status.error && <ErrorState error={status.error} />}
            {!messages.length ? (
              <div className="mx-auto max-w-xl py-10 text-center">
                <div className="mx-auto mb-4 grid size-12 place-items-center rounded-2xl bg-gradient-to-br from-aurora/20 to-iris/20"><Bot className="size-6 text-aurora" /></div>
                <h2 className="text-lg font-semibold">Ask about your twin, roles, gaps or your plan</h2>
                <p className="mt-1 text-sm text-fg-muted">The Personalized Mentor sees your profile summary and retrieved guidance. It is instructed never to invent scores, skills or job openings.</p>
                <div className="mt-6 grid gap-2 sm:grid-cols-2">
                  {STARTERS.map((s) => <button key={s} type="button" disabled={!online} onClick={() => send(s)} className="rounded-xl border border-line bg-ink-800/50 p-3 text-left text-sm text-fg-muted transition hover:border-aurora/40 hover:text-fg disabled:opacity-50">{s}</button>)}
                </div>
              </div>
            ) : (
              <AnimatePresence initial={false}>
                {messages.map((m, i) => (
                  <motion.div key={i} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }}>
                    {m.role === "user" ? (
                      <div className="flex justify-end gap-3">
                        <div className="max-w-[80%] rounded-2xl rounded-tr-sm bg-aurora/12 px-4 py-2.5 text-sm text-fg">{m.content}</div>
                        <div className="grid size-8 shrink-0 place-items-center rounded-full bg-ink-700"><UserRound className="size-4 text-fg-muted" /></div>
                      </div>
                    ) : <AssistantBubble m={m} />}
                  </motion.div>
                ))}
              </AnimatePresence>
            )}
            <div ref={endRef} />
          </div>
          <form className="border-t border-line p-3" onSubmit={(e) => { e.preventDefault(); void send(input); }}>
            <div className="flex items-end gap-2">
              <Textarea aria-label="Your question" className="max-h-40 min-h-12 flex-1 resize-y" placeholder={online ? "Ask your Personalized Mentor… (Enter to send, Shift+Enter for a new line)" : "Mentor unavailable"}
                value={input} maxLength={2000} disabled={!online} onChange={(e) => setInput(e.target.value)}
                onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); void send(input); } }} />
              {busy ? (
                <Button type="button" variant="secondary" onClick={() => abort.current?.abort()} aria-label="Stop generating"><Square className="size-4" /> Stop</Button>
              ) : (
                <Button type="submit" disabled={!online || !input.trim()} aria-label="Send"><Send className="size-4" /></Button>
              )}
            </div>
            <p className="mt-1.5 text-right font-mono text-[0.65rem] text-fg-faint">{input.length}/2000</p>
          </form>
        </Card>
      </div>
    </div>
  );
}
