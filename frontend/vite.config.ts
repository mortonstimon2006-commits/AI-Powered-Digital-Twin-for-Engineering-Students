/// <reference types="vitest/config" />
import { fileURLToPath, URL } from "node:url";

import tailwindcss from "@tailwindcss/vite";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

const API_TARGET = process.env.TWINPATH_API_URL ?? "http://127.0.0.1:8010";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": fileURLToPath(new URL("./src", import.meta.url)) } },
  server: {
    port: 5173,
    strictPort: true,
    host: "localhost",
    // Same-origin proxy: the browser only ever talks to the SPA origin, so session cookies stay
    // first-party and no CORS exceptions are needed in development.
    proxy: { "/api": { target: API_TARGET, changeOrigin: false } },
  },
  preview: { port: 4173, strictPort: true },
  build: {
    target: "es2022",
    sourcemap: false,
    chunkSizeWarningLimit: 1300, // the lazily-loaded three.js chunk is large by nature
    // Never inline assets as data: URIs — the production CSP allows fonts/images only from 'self'.
    assetsInlineLimit: 0,
    // No manual chunk grouping: three.js / R3F and the chart library are only reached through
    // React.lazy() boundaries, so the bundler keeps them out of the first-paint graph.
  },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./src/test/setup.ts"],
    css: false,
    include: ["src/**/*.test.{ts,tsx}"],
  },
});
