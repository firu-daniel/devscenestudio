import { defineConfig } from "@playwright/test";

// End-to-end suites, run in CI as a required check (not part of the harness test gate).
// `browser`: the renderer in browser mode on `vite preview`. `electron`: the real app (Day 2).
const PREVIEW_PORT = 4173;

export default defineConfig({
  testDir: "tests/e2e",
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI ? [["github"], ["html", { open: "never" }]] : "list",
  projects: [
    {
      name: "browser",
      testMatch: "browser/**/*.spec.ts",
      use: {
        baseURL: `http://localhost:${PREVIEW_PORT}`,
        browserName: "chromium",
      },
    },
    { name: "electron", testMatch: "electron/**/*.spec.ts" },
  ],
  webServer: {
    command: `npm run build:browser && npx vite preview --mode browser --port ${PREVIEW_PORT} --strictPort`,
    port: PREVIEW_PORT,
    reuseExistingServer: !process.env.CI,
  },
});
