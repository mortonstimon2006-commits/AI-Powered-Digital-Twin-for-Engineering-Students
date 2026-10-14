import { expect, test, type Page } from "@playwright/test";
import { randomBytes } from "node:crypto";

const email = `e2e.${Date.now()}@example.edu`;
const password = `e2e-${randomBytes(12).toString("base64url")}`;

test.describe.configure({ mode: "serial" });

async function signIn(page: Page) {
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page).toHaveURL(/\/app/); // wait for the authenticated redirect
}

/** Creates and onboards an account through the API, for tests running in another project/worker. Returns a cleanup. */
async function apiAccount(page: Page): Promise<() => Promise<void>> {
  const who = `e2e.mobile.${Date.now()}@example.edu`;
  const pw = `e2e-${randomBytes(12).toString("base64url")}`;
  const h = { "X-Requested-With": "twinpath" };
  await page.request.post("/api/v1/auth/register", {
    headers: h,
    data: { email: who, password: pw, display_name: "E2E Mobile", accept_profile_processing: true },
  });
  const login = await page.request.post("/api/v1/auth/login", { headers: h, data: { email: who, password: pw } });
  expect(login.ok()).toBeTruthy();
  const csrf = (await page.context().cookies()).find((c) => c.name.endsWith("tp_csrf"))!.value;
  const auth = { ...h, "X-CSRF-Token": csrf };
  const roles = await (await page.request.get("/api/v1/roles")).json();
  await page.request.put("/api/v1/profile/roles", { headers: auth, data: { target_role_id: roles.roles[0].id } });
  await page.request.post("/api/v1/profile/onboarding/complete", { headers: auth });
  return async () => {
    const del = await page.request.post("/api/v1/privacy/delete-account", {
      headers: auth,
      data: { password: pw, confirmation: "DELETE MY ACCOUNT" },
    });
    expect(del.ok()).toBeTruthy();
  };
}

test("register, onboard and reach the dashboard", async ({ page }) => {
  await page.goto("/register");
  await page.getByLabel(/^Name/).fill("E2E Student");
  await page.getByLabel(/^Email/).fill(email);
  await page.getByLabel(/^Password/, { exact: false }).first().fill(password);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: /create account/i }).click();
  await expect(page.getByText(/same message whether or not an account already exists/)).toBeVisible();

  await signIn(page);
  await expect(page).toHaveURL(/\/app\/onboarding/);
  // Step 1 — academics
  await page.getByLabel(/^Degree/).fill("B.Tech");
  await page.getByLabel(/^Specialization/).fill("Information Technology");
  await page.getByRole("button", { name: /save and continue/i }).click();
  // Step 2 — goals
  await page.getByRole("radio", { name: /Data Analyst/ }).click();
  await page.getByRole("button", { name: /save and continue/i }).click();
  // Step 3 — skills (rate SQL, skip the rest)
  await page.getByRole("radiogroup", { name: "SQL self-rating" }).getByRole("radio", { name: /Working/ }).click();
  await page.getByRole("button", { name: /save and continue/i }).click();
  // Step 4 — availability
  await page.getByRole("button", { name: /finish setup/i }).click();

  await expect(page).toHaveURL(/\/app$/);
  await expect(page.getByRole("heading", { name: /Welcome back, E2E/ })).toBeVisible();
  await expect(page.getByText("How complete is your twin?")).toBeVisible();
});

test("twin evidence, gaps, readiness, simulation and roadmap", async ({ page }) => {
  await signIn(page);
  await expect(page).toHaveURL(/\/app$/);

  // Add a project with linked skill evidence
  await page.goto("/app/profile?tab=projects");
  await page.getByRole("button", { name: /add project/i }).first().click();
  await page.getByLabel(/^Title/).fill("Sales dashboard");
  await page.getByLabel("Add a skill").selectOption({ label: "SQL" });
  await page.getByRole("button", { name: /^Add$/ }).click();
  await page.getByRole("button", { name: /save project/i }).click();
  await expect(page.getByText("Sales dashboard")).toBeVisible();

  // Skill-gap analysis renders a real breakdown
  await page.goto("/app/gaps");
  await expect(page.getByText(/Data Analyst · v\d+/)).toBeVisible();
  await expect(page.getByRole("table")).toContainText("SQL");

  // Readiness analysis with explanation (model must be active in the target environment)
  await page.goto("/app/readiness");
  await page.getByRole("button", { name: /run analysis/i }).first().click();
  await expect(page.getByText(/What moved the estimate/)).toBeVisible();
  await expect(page.getByText(/not proof that changing a factor/)).toBeVisible();

  // What-if simulation — keyboard-driven slider, results clearly labelled hypothetical
  await page.goto("/app/simulator");
  const slider = page.getByRole("slider", { name: /SQL hypothetical level/ });
  await slider.focus();
  await page.keyboard.press("ArrowRight");
  await page.keyboard.press("ArrowRight");
  await expect(page.getByText("HYPOTHETICAL", { exact: true })).toBeVisible();
  await expect(page.getByText(/Role match: today vs hypothetical/)).toBeVisible();

  // Roadmap generation from real gaps
  await page.goto("/app/roadmap");
  await page.getByRole("button", { name: /^Generate$/ }).click();
  await expect(page.getByText(/Plan for Data Analyst/)).toBeVisible();
  await expect(page.getByRole("combobox", { name: /Status of/ }).first()).toBeVisible();
});

test("security: state-changing requests without CSRF protections are rejected", async ({ page }) => {
  await signIn(page);
  await expect(page).toHaveURL(/\/app$/);
  const statuses = await page.evaluate(async () => {
    const noHeader = await fetch("/api/v1/auth/sessions/revoke-others", { method: "POST" });
    const noToken = await fetch("/api/v1/auth/sessions/revoke-others", { method: "POST", headers: { "X-Requested-With": "twinpath" } });
    return [noHeader.status, noToken.status];
  });
  expect(statuses).toEqual([403, 403]);
});

test("keyboard: skip link is the first focusable element @responsive", async ({ page }) => {
  const cleanup = await apiAccount(page); // own account: this test also runs in the mobile project's separate worker
  await page.goto("/app");
  await expect(page).toHaveURL(/\/app$/);
  await page.keyboard.press("Tab");
  await expect(page.getByRole("link", { name: "Skip to content" })).toBeFocused();
  const overflow = await page.evaluate(() => document.documentElement.scrollWidth - document.documentElement.clientWidth);
  expect(overflow).toBeLessThanOrEqual(1);
  await cleanup();
});

test("account deletion removes the user", async ({ page }) => {
  await signIn(page);
  await page.goto("/app/settings?tab=privacy");
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel(/Type "DELETE MY ACCOUNT"/).fill("DELETE MY ACCOUNT");
  await page.getByRole("button", { name: /delete my account/i }).click();
  await page.getByRole("button", { name: /delete permanently/i }).click();
  await expect(page).toHaveURL(/\/$/);
  await page.goto("/login");
  await page.getByLabel("Email").fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: /sign in/i }).click();
  await expect(page.getByText(/Invalid email or password/)).toBeVisible();
});
