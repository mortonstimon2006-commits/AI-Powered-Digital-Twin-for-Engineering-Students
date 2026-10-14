import { fireEvent, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { axeViolations, jsonResponse, renderWithProviders } from "@/test/utils";

import { LoginPage, RegisterPage } from "./AuthPages";

afterEach(() => vi.restoreAllMocks());

describe("RegisterPage", () => {
  it("validates fields client-side before calling the API", async () => {
    const fetchMock = vi.spyOn(globalThis, "fetch");
    renderWithProviders(<RegisterPage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^Name/), "Asha");
    await user.type(screen.getByLabelText(/^Email/), "not-an-email");
    await user.type(screen.getByLabelText(/^Password/, { selector: "input" }), "short");
    await user.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/valid email/i)).toBeInTheDocument();
    expect(screen.getByText(/Use at least 12 characters/)).toBeInTheDocument();
    expect(screen.getByText(/Consent is required/)).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("shows the same neutral confirmation regardless of account existence", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ message: "ok" }, 202));
    renderWithProviders(<RegisterPage />);
    const user = userEvent.setup();
    await user.type(screen.getByLabelText(/^Name/), "Asha Kulkarni");
    await user.type(screen.getByLabelText(/^Email/), "asha@example.edu");
    await user.type(screen.getByLabelText(/^Password/, { selector: "input" }), "correct-horse-battery-staple");
    await user.click(screen.getByRole("checkbox"));
    await user.click(screen.getByRole("button", { name: /create account/i }));
    expect(await screen.findByText(/same message whether or not an account already exists/)).toBeInTheDocument();
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = renderWithProviders(<RegisterPage />);
    expect(await axeViolations(container)).toEqual([]);
  });
});

describe("LoginPage", () => {
  it("displays the server's generic error without revealing account existence", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(
      jsonResponse({ error: { code: "invalid_credentials", message: "Invalid email or password, or too many recent attempts." } }, 401),
    );
    renderWithProviders(<LoginPage />, { route: "/login" });
    fireEvent.input(screen.getByLabelText("Email"), { target: { value: "x@example.edu" } });
    fireEvent.input(screen.getByLabelText("Password"), { target: { value: "whatever-pass" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    await waitFor(() => expect(screen.getByText(/Invalid email or password/)).toBeInTheDocument());
  });

  it("switches to the MFA step when required", async () => {
    vi.spyOn(globalThis, "fetch").mockResolvedValue(jsonResponse({ status: "mfa_required", mfa_challenge: "c".repeat(40), me: null }));
    renderWithProviders(<LoginPage />, { route: "/login" });
    fireEvent.input(screen.getByLabelText("Email"), { target: { value: "x@example.edu" } });
    fireEvent.input(screen.getByLabelText("Password"), { target: { value: "whatever-pass" } });
    fireEvent.click(screen.getByRole("button", { name: /sign in/i }));
    expect(await screen.findByLabelText(/Authentication code/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /verify/i })).toBeDisabled();
  });

  it("has no detectable accessibility violations", async () => {
    const { container } = renderWithProviders(<LoginPage />, { route: "/login" });
    expect(await axeViolations(container)).toEqual([]);
  });
});
