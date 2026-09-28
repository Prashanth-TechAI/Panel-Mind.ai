import { defineConfig, devices } from "@playwright/test";

const WEB_PORT = Number(process.env.E2E_WEB_PORT ?? 3100);
const API_PORT = Number(process.env.E2E_API_PORT ?? 8100);

const BASE_URL = `http://127.0.0.1:${WEB_PORT}`;
const API_URL = `http://127.0.0.1:${API_PORT}`;

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  workers: process.env.CI ? 1 : undefined,
  reporter: process.env.CI ? [["github"], ["list"]] : [["list"]],

  timeout: 60_000,
  expect: { timeout: 15_000 },

  use: {
    baseURL: BASE_URL,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
    extraHTTPHeaders: { "x-e2e": "1" },
  },

  projects: [
    {
      name: "chromium",
      use: {
        ...devices["Desktop Chrome"],
        permissions: ["microphone"],
        launchOptions: {
          args: [
            // Headless Chromium refuses audio.play() without a gesture it
            // recognises, which would fail the voice tests for a reason that
            // never occurs in a real browser.
            "--autoplay-policy=no-user-gesture-required",
            "--mute-audio",
            // A synthetic microphone, so the board has something to hear.
            "--use-fake-ui-for-media-stream",
            "--use-fake-device-for-media-stream",
            // A real spoken answer as the microphone, looped. Without this the
            // fake device emits a tone, nothing transcribes, the candidate
            // never completes a turn, and the board never hands over — which
            // is how a frozen mic passed every browser run.
            `--use-file-for-fake-audio-capture=${process.cwd()}/tests/fixtures/candidate-answer.wav`,
          ],
        },
      },
    },
  ],

  // Both planes come up for every run. The suite exercises the real Python
  // control plane against real providers — a dead key must fail the build.
  webServer: [
    {
      command: `.venv/bin/python -m uvicorn app.main:app --port ${API_PORT} --log-level warning`,
      cwd: "./backend",
      url: `${API_URL}/api/board`,
      reuseExistingServer: !process.env.CI,
      timeout: 120_000,
      stdout: "pipe",
      stderr: "pipe",
      // The suite serves the frontend on a non-default port, so the browser's
      // origin must be allowed or every client-side call is blocked by CORS.
      env: { CORS_ORIGINS: `${BASE_URL},http://localhost:${WEB_PORT}` },
    },
    {
      // Production build, not `next dev`. NEXT_PUBLIC_* is inlined at build
      // time, and the dev server's HMR layer interferes with hydration under
      // headless Chromium — this is also simply closer to what ships.
      command: `npm run build && npm run start -- --port ${WEB_PORT}`,
      url: BASE_URL,
      reuseExistingServer: !process.env.CI,
      timeout: 240_000,
      stdout: "pipe",
      stderr: "pipe",
      env: { NEXT_PUBLIC_API_URL: API_URL },
    },
  ],
});
