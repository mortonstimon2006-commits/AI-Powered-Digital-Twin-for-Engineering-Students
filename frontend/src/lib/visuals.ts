import { useEffect, useState, useSyncExternalStore } from "react";

/**
 * Whether to render WebGL scenes. 3D is an enhancement, never a gate to information:
 * it is disabled when the user turns it off, when reduced motion is requested, when WebGL is
 * unavailable, or on low-memory devices — a 2D alternative is rendered instead.
 */
const KEY = "twinpath.visuals3d";
const listeners = new Set<() => void>();

function readPref(): "on" | "off" | "auto" {
  try {
    const v = localStorage.getItem(KEY);
    return v === "on" || v === "off" ? v : "auto";
  } catch {
    return "auto";
  }
}

export function setVisualsPref(v: "on" | "off" | "auto"): void {
  try {
    if (v === "auto") localStorage.removeItem(KEY);
    else localStorage.setItem(KEY, v);
  } catch {
    /* storage unavailable: preference applies to this page view only */
  }
  listeners.forEach((l) => l());
}

export function useVisualsPref(): "on" | "off" | "auto" {
  return useSyncExternalStore(
    (cb) => {
      listeners.add(cb);
      return () => listeners.delete(cb);
    },
    readPref,
    () => "auto",
  );
}

let webglCache: boolean | null = null;
export function supportsWebGL(): boolean {
  if (webglCache !== null) return webglCache;
  try {
    const canvas = document.createElement("canvas");
    webglCache = Boolean(canvas.getContext("webgl2") ?? canvas.getContext("webgl"));
  } catch {
    webglCache = false;
  }
  return webglCache;
}

export function usePrefersReducedMotion(): boolean {
  const [reduced, setReduced] = useState(
    () => typeof window !== "undefined" && window.matchMedia?.("(prefers-reduced-motion: reduce)").matches,
  );
  useEffect(() => {
    const mq = window.matchMedia?.("(prefers-reduced-motion: reduce)");
    if (!mq) return;
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return Boolean(reduced);
}

export function useCan3D(): { enabled: boolean; reason: string | null } {
  const pref = useVisualsPref();
  const reduced = usePrefersReducedMotion();
  if (pref === "off") return { enabled: false, reason: "3D visuals are turned off in Settings." };
  if (!supportsWebGL()) return { enabled: false, reason: "WebGL is not available in this browser." };
  if (pref === "on") return { enabled: true, reason: null };
  if (reduced) return { enabled: false, reason: "Reduced motion is requested by your system." };
  const mem = (navigator as Navigator & { deviceMemory?: number }).deviceMemory;
  if (mem !== undefined && mem < 4) return { enabled: false, reason: "Simplified view for this device." };
  return { enabled: true, reason: null };
}
