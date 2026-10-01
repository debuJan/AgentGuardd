import { defineConfig, devices } from '@playwright/test';

/**
 * AgentGuard dashboard smoke tests.
 *
 * Prerequisites (run once on your machine):
 *   npm install
 *   npx playwright install chromium
 *
 * The config starts everything itself:
 *   1. FastAPI backend on :8001 via e2e/launch-api.mjs (in-memory report
 *      store, no Postgres; CORS opened for the preview origin).
 *   2. Frontend rebuilt with VITE_API_BASE_URL pointing at the test backend,
 *      then served via preview on :4173.
 * Just run: npx playwright test
 *
 * Environment overrides:
 *   AGENTGUARD_E2E_API_CMD  Full command to start the API instead of the
 *                           launcher (run with cwd set to the repo root).
 *                           If you use it, you must set USE_POSTGRES=false
 *                           and AGENTGUARD_CORS_ORIGINS=http://127.0.0.1:4173
 *                           yourself — see e2e/launch-api.mjs.
 */
const API_PORT = 8001;
const WEB_PORT = 4173;
const API_URL = `http://127.0.0.1:${API_PORT}`;

// NOTE: commands run with cwd set to '..' (the repo root).
// The API is started through e2e/launch-api.mjs, which sets the required
// environment (USE_POSTGRES=false, AGENTGUARD_CORS_ORIGINS=...) in-process
// via Node's spawn. Do NOT move that environment back into webServer.env:
// on Windows it silently failed to reach the API process, the API fell back
// to its default CORS origins, and the browser blocked every API response
// ("API Unavailable" in the UI) while the API itself worked fine.

export default defineConfig({
  testDir: './e2e',
  timeout: 60_000,
  expect: { timeout: 10_000 },
  fullyParallel: false,
  retries: 0,
  reporter: [['list']],
  use: {
    baseURL: `http://127.0.0.1:${WEB_PORT}`,
    trace: 'retain-on-failure',
  },
  projects: [{ name: 'chromium', use: { ...devices['Desktop Chrome'] } }],
  webServer: [
    {
      command: process.env.AGENTGUARD_E2E_API_CMD || 'node frontend/e2e/launch-api.mjs',
      cwd: '..',
      url: `${API_URL}/health`,
      // Never reuse: a stale API (wrong CORS origins, wrong store) would be
      // silently reused and UI assertions would fail confusingly. If the
      // port is taken this fails fast — free it and rerun.
      reuseExistingServer: false,
      timeout: 60_000,
    },
    {
      // VITE_API_BASE_URL is baked into the bundle at build time, so build
      // here (with the env below) instead of relying on a stale dist/.
      // --host 127.0.0.1 is required: without it Vite may bind to ::1 on
      // Windows and Playwright's 127.0.0.1 health check never connects.
      // reuseExistingServer is false: a manually-built preview pointing at
      // the wrong API would otherwise be silently reused. Do NOT start the
      // preview by hand for e2e — just run npx playwright test.
      command: `npm run build && npx vite preview --host 127.0.0.1 --port ${WEB_PORT} --strictPort`,
      url: `http://127.0.0.1:${WEB_PORT}`,
      reuseExistingServer: false,
      timeout: 120_000,
      env: { VITE_API_BASE_URL: API_URL },
    },
  ],
});
