import { defineConfig } from "@playwright/test";

// The backend serves the built UI from ui/dist (see app.config.ui_dist_path),
// so one webServer covers both the API and the SPA. `npm run test:e2e`
// builds the UI first.
const PORT = Number(process.env.AFR_E2E_PORT ?? 8791);

export default defineConfig({
  testDir: "./e2e",
  testMatch: "*.spec.ts",
  timeout: 300_000,
  expect: { timeout: 90_000 },
  retries: 0,
  workers: 1,
  reporter: [["list"]],
  use: {
    baseURL: `http://127.0.0.1:${PORT}`,
    headless: true,
  },
  webServer: {
    command: "bash e2e/serve-e2e.sh",
    url: `http://127.0.0.1:${PORT}/health`,
    timeout: 180_000,
    reuseExistingServer: false,
  },
});
