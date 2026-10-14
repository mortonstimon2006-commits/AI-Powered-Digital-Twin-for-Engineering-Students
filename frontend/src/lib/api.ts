/**
 * Typed API client.
 *
 * - Same-origin requests with the HttpOnly session cookie (credentials are never handled in JS).
 * - Every state-changing request carries `X-Requested-With` and the double-submit CSRF token
 *   read from the (non-HttpOnly) CSRF cookie. Nothing sensitive is kept in localStorage.
 * - Errors are normalised from the backend envelope {error: {code, message, details, request_id}}.
 */

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: unknown;
  readonly requestId: string | null;

  constructor(status: number, code: string, message: string, details?: unknown, requestId?: string | null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
    this.requestId = requestId ?? null;
  }

  get fieldErrors(): Record<string, string> {
    const out: Record<string, string> = {};
    if (Array.isArray(this.details)) {
      for (const d of this.details as { field?: string; message?: string }[]) {
        if (d.field && d.message) out[d.field] = d.message;
      }
    }
    return out;
  }
}

export function readCookie(name: string): string | null {
  const parts = document.cookie ? document.cookie.split("; ") : [];
  for (const part of parts) {
    const idx = part.indexOf("=");
    if (part.slice(0, idx) === name) return decodeURIComponent(part.slice(idx + 1));
  }
  return null;
}

export function csrfToken(): string | null {
  return readCookie("__Host-tp_csrf") ?? readCookie("tp_csrf");
}

type Method = "GET" | "POST" | "PUT" | "PATCH" | "DELETE";

export interface RequestOptions {
  method?: Method;
  body?: unknown;
  form?: FormData;
  signal?: AbortSignal;
  query?: Record<string, string | number | boolean | null | undefined>;
}

function buildUrl(path: string, query?: RequestOptions["query"]): string {
  const url = new URL(API_BASE + path, window.location.origin);
  if (query) {
    for (const [k, v] of Object.entries(query)) {
      if (v !== undefined && v !== null && v !== "") url.searchParams.set(k, String(v));
    }
  }
  return url.pathname + url.search;
}

async function toError(resp: Response): Promise<ApiError> {
  let body: { error?: { code?: string; message?: string; details?: unknown; request_id?: string } } = {};
  try {
    body = await resp.json();
  } catch {
    /* non-JSON error (proxy, network) */
  }
  const e = body.error ?? {};
  const fallback =
    resp.status === 0 || resp.status >= 502
      ? "The TwinPath service is temporarily unreachable."
      : "The request could not be completed.";
  return new ApiError(resp.status, e.code ?? `http_${resp.status}`, e.message ?? fallback, e.details, e.request_id);
}

export function headersFor(method: Method, json: boolean): Headers {
  const h = new Headers({ Accept: "application/json" });
  if (json) h.set("Content-Type", "application/json");
  if (method !== "GET") {
    h.set("X-Requested-With", "twinpath");
    const token = csrfToken();
    if (token) h.set("X-CSRF-Token", token);
  }
  return h;
}

async function refreshCsrf(): Promise<void> {
  await fetch(API_BASE + "/auth/csrf", { credentials: "same-origin", headers: { Accept: "application/json" } });
}

export async function api<T>(path: string, opts: RequestOptions = {}, retried = false): Promise<T> {
  const method = opts.method ?? "GET";
  const isJson = opts.body !== undefined && !opts.form;
  let resp: Response;
  try {
    resp = await fetch(buildUrl(path, opts.query), {
      method,
      credentials: "same-origin",
      headers: headersFor(method, isJson),
      body: opts.form ?? (isJson ? JSON.stringify(opts.body) : undefined),
      signal: opts.signal,
    });
  } catch (err) {
    if ((err as Error).name === "AbortError") throw err;
    throw new ApiError(0, "network_error", "You appear to be offline or the server is unreachable.");
  }
  if (!resp.ok) {
    const error = await toError(resp);
    if (error.code === "csrf_invalid" && !retried) {
      await refreshCsrf();
      return api<T>(path, opts, true);
    }
    throw error;
  }
  if (resp.status === 204) return undefined as T;
  const type = resp.headers.get("content-type") ?? "";
  return (type.includes("application/json") ? resp.json() : resp.text()) as Promise<T>;
}

export async function download(path: string, filename: string): Promise<void> {
  const resp = await fetch(API_BASE + path, { credentials: "same-origin" });
  if (!resp.ok) throw await toError(resp);
  const blob = await resp.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.rel = "noopener";
  document.body.appendChild(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
