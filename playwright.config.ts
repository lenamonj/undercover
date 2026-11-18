import { defineConfig } from "@playwright/test";

const backend = "http://127.0.0.1:8001";

export default defineConfig({
  testDir: "e2e",
  outputDir: "e2e/test-results",
  reporter: "list",
  workers: 1,
  use: { baseURL: "http://localhost:5174" },
  webServer: [
    {
      command: "uv run -m e2e.server",
      url: `${backend}/api/health`,
      reuseExistingServer: false,
    },
    {
      command: "npx vite dashboard --port 5174 --strictPort",
      url: "http://localhost:5174",
      env: { BACKEND_URL: backend },
      reuseExistingServer: false,
    },
  ],
});
