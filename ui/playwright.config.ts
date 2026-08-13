import { defineConfig } from "@playwright/test";

/**
 * Exactly three specs, on exactly the three killer interactions. E2E breadth is
 * maintenance drag; these paths ARE the demo, and the demo is what must never
 * break.
 *
 * Both servers are booted here. That is the point: a spec needing hand-started
 * processes is a spec that quietly stops being run, and this config previously
 * started only Vite while its own comment said the API was required — so the
 * suite passed for whoever happened to have uvicorn open and failed for
 * everyone else.
 *
 * `reuseExistingServer` means an already-running API or dev server is used as
 * is, so this stays convenient during development and self-contained from cold.
 */
export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:5173", trace: "on-first-retry" },
  webServer: [
    {
      // Prefers an activated venv, falls back to the repo's .venv, and uses
      // `python3` either way because a bare `python` is not guaranteed to exist.
      command:
        "sh -c '. .venv/bin/activate 2>/dev/null; exec python3 -m uvicorn spp.api.main:app --port 8000 --app-dir src'",
      cwd: "..",
      url: "http://localhost:8000/health",
      reuseExistingServer: true,
      timeout: 60_000,
    },
    {
      command: "npm run dev",
      url: "http://localhost:5173",
      reuseExistingServer: true,
      timeout: 60_000,
    },
  ],
});
