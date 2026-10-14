import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderOptions } from "@testing-library/react";
import axe from "axe-core";
import { Tooltip } from "radix-ui";
import type { ReactElement, ReactNode } from "react";
import { MemoryRouter } from "react-router";

export function renderWithProviders(ui: ReactElement, { route = "/", ...opts }: { route?: string } & RenderOptions = {}) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const Wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={qc}>
      <Tooltip.Provider>
        <MemoryRouter initialEntries={[route]}>{children}</MemoryRouter>
      </Tooltip.Provider>
    </QueryClientProvider>
  );
  return { qc, ...render(ui, { wrapper: Wrapper, ...opts }) };
}

/** Runs axe-core and returns violations (colour contrast cannot be computed in jsdom). */
export async function axeViolations(container: HTMLElement) {
  const results = await axe.run(container, { rules: { "color-contrast": { enabled: false }, region: { enabled: false } } });
  return results.violations.map((v) => `${v.id}: ${v.help} (${v.nodes.length})`);
}

export function jsonResponse(body: unknown, status = 200) {
  return new Response(JSON.stringify(body), { status, headers: { "content-type": "application/json" } });
}
