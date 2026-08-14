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
      // Uses the repo's .venv when there is one (local dev) and the ambient
      // interpreter when there is not (CI). `python3` either way, because a
      // bare `python` is not guaranteed to exist on a stock macOS shell.
      //
      // The guard is an `if`, not `. .venv/bin/activate 2>/dev/null`. Sourcing
      // a missing file is a special-builtin failure, which makes a POSIX sh
      // (dash, i.e. every Ubuntu runner) exit on the spot instead of falling
      // through — so the API never started in CI while the local box, which has
      // a .venv and a bash /bin/sh, sailed through and hid it.
      command:
        "sh -c 'if [ -f .venv/bin/activate ]; then . .venv/bin/activate; fi; exec python3 -m uvicorn spp.api.main:app --port 8000 --app-dir src'",
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
