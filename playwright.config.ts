import { defineConfig } from "@playwright/test";
import fs from "node:fs";
fs.mkdirSync(".runtime", { recursive: true });
export default defineConfig({
  testDir: "./e2e",
  timeout: 60000,
  workers: 1,
  use: {
    baseURL: "http://127.0.0.1:8001",
    headless: true,
    reducedMotion: "reduce",
    trace: "retain-on-failure",
  },
  webServer: {
    // The server serves the prebuilt bundle from dist/ (see backend/main.py).
    // Without an explicit build here the browser test would silently exercise a
    // stale bundle left over from an earlier build, so UI changes in src/ would
    // not be tested at all. `tsc -b` also fails the suite on type errors.
    command:
      "npm run build && .venv\\Scripts\\python.exe -m uvicorn backend.main:app --host 127.0.0.1 --port 8001",
    url: "http://127.0.0.1:8001",
    reuseExistingServer: false,
    env: { DATABASE_URL: `sqlite:///.runtime/e2e-${Date.now()}.db` },
    timeout: 120000,
  },
});
