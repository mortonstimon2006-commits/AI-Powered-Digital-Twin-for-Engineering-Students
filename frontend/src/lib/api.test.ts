import { afterEach, describe, expect, it, vi } from "vitest";

import { jsonResponse } from "@/test/utils";

import { api, ApiError, csrfToken } from "./api";

afterEach(() => {
  vi.restoreAllMocks();
  document.cookie = "tp_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT";
});

describe("api client", () => {
  it("sends the anti-CSRF header and token only on state-changing requests", async () => {
    document.cookie = "tp_csrf=token-abc";
    const fetchMock = vi.spyOn(globalThis, "fetch").mockImplementation(async () => jsonResponse({ ok: true }));
    await api("/thing");
    await api("/thing", { method: "POST", body: { a: 1 } });
    const getHeaders = fetchMock.mock.calls[0]![1]!.headers as Headers;
    const postHeaders = fetchMock.mock.calls[1]![1]!.headers as Headers;
    expect(getHeaders.get("X-CSRF-Token")).toBeNull();
    expect(postHeaders.get("X-Requested-With")).toBe("twinpath");
    expect(postHeaders.get("X-CSRF-Token")).toBe("token-abc");
    expect(fetchMock.mock.calls[1]![1]!.credentials).toBe("same-origin");
  });

  it("normalises the backend error envelope", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: { code: "validation_error", message: "Bad input", request_id: "r1",
        details: [{ field: "email", message: "invalid email" }] } }, 422),
    );
    const err = await api<never>("/x", { method: "POST", body: {} }).catch((e: unknown) => e as ApiError);
    expect(err).toBeInstanceOf(ApiError);
    expect(err.status).toBe(422);
    expect(err.code).toBe("validation_error");
    expect(err.requestId).toBe("r1");
    expect(err.fieldErrors).toEqual({ email: "invalid email" });
  });

  it("refreshes the CSRF token once and retries on csrf_invalid", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch")
      .mockResolvedValueOnce(jsonResponse({ error: { code: "csrf_invalid", message: "Invalid" } }, 403))
      .mockResolvedValueOnce(jsonResponse({}))
      .mockResolvedValueOnce(jsonResponse({ done: true }));
    await expect(api("/y", { method: "POST", body: {} })).resolves.toEqual({ done: true });
    expect(fetchMock).toHaveBeenCalledTimes(3);
    expect(String(fetchMock.mock.calls[1]![0])).toContain("/auth/csrf");
  });

  it("reports network failures as offline errors", async () => {
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const err = await api<never>("/z").catch((e: unknown) => e as ApiError);
    expect(err.code).toBe("network_error");
  });

  it("prefers the __Host- prefixed CSRF cookie", () => {
    document.cookie = "tp_csrf=plain";
    expect(csrfToken()).toBe("plain");
  });
});
