import { ApiError, API_BASE, headersFor } from "./api";

export interface SseHandlers {
  onEvent: (event: string, data: Record<string, unknown>) => void;
}

/**
 * POST + Server-Sent-Events reader (EventSource cannot send POST bodies or CSRF headers).
 * Parses `event:` / `data:` frames from the streamed body.
 */
export async function postSse(path: string, body: unknown, handlers: SseHandlers, signal?: AbortSignal): Promise<void> {
  const resp = await fetch(API_BASE + path, {
    method: "POST",
    credentials: "same-origin",
    headers: headersFor("POST", true),
    body: JSON.stringify(body),
    signal,
  });
  if (!resp.ok || !resp.body) {
    let payload: { error?: { code?: string; message?: string; request_id?: string } } = {};
    try {
      payload = await resp.json();
    } catch {
      /* ignore */
    }
    throw new ApiError(
      resp.status,
      payload.error?.code ?? `http_${resp.status}`,
      payload.error?.message ?? "The mentor request failed.",
      undefined,
      payload.error?.request_id,
    );
  }
  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) break;
    buffer += decoder.decode(value, { stream: true });
    let sep: number;
    while ((sep = buffer.indexOf("\n\n")) >= 0) {
      const frame = buffer.slice(0, sep);
      buffer = buffer.slice(sep + 2);
      let event = "message";
      let data = "";
      for (const line of frame.split("\n")) {
        if (line.startsWith("event:")) event = line.slice(6).trim();
        else if (line.startsWith("data:")) data += line.slice(5).trim();
      }
      if (data) {
        try {
          handlers.onEvent(event, JSON.parse(data) as Record<string, unknown>);
        } catch {
          /* malformed frame: ignore */
        }
      }
    }
  }
}
