import { act, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { setVisualsPref, useCan3D } from "./visuals";

function mockMatchMedia(reduced: boolean) {
  vi.stubGlobal("matchMedia", (q: string) => ({
    matches: q.includes("reduce") ? reduced : false, media: q, addEventListener: () => {}, removeEventListener: () => {},
  }));
}

afterEach(() => {
  vi.unstubAllGlobals();
  setVisualsPref("auto");
});

describe("useCan3D", () => {
  it("falls back to 2D when WebGL is unavailable (jsdom)", () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useCan3D());
    expect(result.current.enabled).toBe(false);
    expect(result.current.reason).toMatch(/WebGL/);
  });

  it("respects the user's 3D-off preference first", () => {
    mockMatchMedia(false);
    const { result } = renderHook(() => useCan3D());
    act(() => setVisualsPref("off"));
    expect(result.current).toEqual({ enabled: false, reason: "3D visuals are turned off in Settings." });
  });
});
