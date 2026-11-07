import { defineConfig } from "@playwright/test";
import { randomUUID } from "node:crypto";

export default defineConfig({
  testDir: "./tests",
  workers: 1,
  fullyParallel: false,
  use: {
    baseURL: "http://127.0.0.1:8001",
    viewport: { width: 1440, height: 1000 },
    permissions: ["clipboard-read", "clipboard-write"],
    trace: "retain-on-failure",
  },
  webServer: {
    command: `${process.env.PYTHON_BIN || "python"} -m panel.api --demo --port 8001`,
    cwd: "..",
    url: "http://127.0.0.1:8001/api/health",
    reuseExistingServer: false,
    env: {
      PANEL_DEMO_FILE: `/tmp/adaptia-browser-${randomUUID()}/config.json`,
    },
  },
});
