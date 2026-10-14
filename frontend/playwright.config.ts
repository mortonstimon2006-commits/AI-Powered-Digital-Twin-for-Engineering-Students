import { defineConfig, devices } from "@playwright/test";

/**
 * End-to-end smoke suite against a running stack (dev servers or the container pilot):
 *   E2E_BASE_URL=http://localhost:5173 npx playwright test      (default)
 *   E2E_BASE_URL=http://localhost:8080 npx playwright test      (containers)
 * Each run registers a unique throwaway account and deletes it at the end.
 * Never point this at production.
 */
export default defineConfig({
  testDir: "./e2e",
  timeout: 120_000,
  expect: { timeout: 15_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: process.env.E2E_BASE_URL ?? "http://localhost:5173",
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
  },
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 7"] }, grep: /@responsive/ },
  ],
});
