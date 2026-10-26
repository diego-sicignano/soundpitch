import { defineConfig } from "@playwright/test";

/** One server per scenario: the page and the API come from the same FastAPI app. */
const python = process.platform === "win32" ? ".venv\\Scripts\\python.exe" : ".venv/bin/python";
const server = (port: number, scenario: string) => ({
  command: `${python} -m uvicorn app.main:app --port ${port}`,
  cwd: "backend",
  url: `http://localhost:${port}/api/health`,
  env: { SOUNDPITCH_LLM: scenario, SOUNDPITCH_CLIPS_DIR: "data/no-clips" }, // the page tests mock /api/voice when they need clips
  reuseExistingServer: true,
});

export default defineConfig({
  testDir: "./e2e",
  // Locally the installed Chrome is used; CI installs Playwright's own Chromium.
  use: { baseURL: "http://localhost:8100", ...(process.env.CI ? {} : { channel: "chrome" }) },
  webServer: [server(8100, "scripted"), server(8101, "always_bad"), server(8102, "bad_then_good")],
});
