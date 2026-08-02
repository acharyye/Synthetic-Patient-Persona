import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

export default defineConfig({
  plugins: [react()],
  server: { proxy: { "/scenario": "http://localhost:8000", "/counterfactual": "http://localhost:8000", "/persona": "http://localhost:8000", "/panel": "http://localhost:8000", "/assumptions": "http://localhost:8000" } },
  test: {
    environment: "jsdom",
    globals: true,
    setupFiles: ["./tests/setup.ts"],
    // Vitest owns tests/, Playwright owns e2e/. Without this vitest collects the
    // spec file and Playwright's test() throws out of context.
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
