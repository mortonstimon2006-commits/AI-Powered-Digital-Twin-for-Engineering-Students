import { screen } from "@testing-library/react";
import { Route, Routes } from "react-router";
import { afterEach, describe, expect, it, vi } from "vitest";

import { RequireAuth } from "@/components/layout/guards";
import type { Me } from "@/lib/types";
import { jsonResponse, renderWithProviders } from "@/test/utils";

function me(role: Me["user"]["role"], onboarding_completed: boolean): Me {
  return {
    user: { id: "u1", email: "s@example.edu", display_name: "S", role, email_verified: true, mfa_enabled: false, created_at: "2026-10-14T00:00:00Z" },
    csrf_token: "t",
    onboarding_completed,
    email_verification_required: false,
  };
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/app" element={<RequireAuth><p>dashboard</p></RequireAuth>} />
      <Route path="/app/onboarding" element={<RequireAuth><p>onboarding</p></RequireAuth>} />
    </Routes>,
    { route },
  );
}

afterEach(() => vi.restoreAllMocks());

describe("RequireAuth onboarding routing", () => {
  it("sends a student who has not finished onboarding to onboarding", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(me("student", false)));
    renderAt("/app");
    expect(await screen.findByText("onboarding")).toBeInTheDocument();
  });

  it("sends a student who already finished onboarding back to the dashboard", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(me("student", true)));
    renderAt("/app/onboarding");
    expect(await screen.findByText("dashboard")).toBeInTheDocument();
  });

  it("does not show student onboarding to staff", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse(me("mentor", false)));
    renderAt("/app/onboarding");
    expect(await screen.findByText("dashboard")).toBeInTheDocument();
  });
});
