import { defineConfig } from "@playwright/test";

/** One server per scenario: the page and the API come from the same FastAPI app. */
const server = (port: number, scenario: string) => ({
  command: `.venv\\Scripts\\python.exe -m uvicorn app.main:app --port ${port}`,
  cwd: "backend",
  url: `http://localhost:${port}/api/health`,
  env: { SOUNDPITCH_LLM: scenario },
  reuseExistingServer: true,
});

export default defineConfig({
  testDir: "./e2e",
  use: { baseURL: "http://localhost:8100", channel: "chrome" },
  webServer: [server(8100, "scripted"), server(8101, "always_bad"), server(8102, "bad_then_good")],
});
