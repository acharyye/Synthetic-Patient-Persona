import { defineConfig } from "@playwright/test";

/**
 * Exactly three specs, on exactly the three killer interactions. E2E breadth is
 * maintenance drag; these paths ARE the demo, and the demo is what must never
 * break. Requires the API on :8000 and `npm run dev` on :5173.
 */
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: {
    command: "npm run dev",
    url: "http://localhost:5173",
    reuseExistingServer: true,
    timeout: 60_000,
  },
});
