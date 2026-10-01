/**
 * E2E API launcher.
 *
 * Starts the FastAPI backend for the Playwright smoke tests with the exact
 * environment the e2e harness requires. The environment is set in-process
 * via Node's `spawn` (explicit `env`), deliberately NOT via Playwright's
 * `webServer.env`: on Windows the latter silently failed to reach the API
 * process, so the API fell back to its default CORS origins, the browser's
 * preflight got a 400, and the UI rendered "API Unavailable" even though the
 * API itself worked (root-caused 2026-09-29).
 *
 * Ports must match frontend/playwright.config.js (API 8001) and
 * frontend/e2e/smoke.spec.js.
 */
import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO_ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..');
const API_PORT = 8001;
const WEB_PORT = 4173;

const pythonBin =
  process.platform === 'win32'
    ? path.join(REPO_ROOT, '.venv', 'Scripts', 'python.exe')
    : path.join(REPO_ROOT, '.venv', 'bin', 'python');

if (!existsSync(pythonBin)) {
  console.error(`[launch-api] venv python not found: ${pythonBin}`);
  console.error('[launch-api] create the venv at the repo root first: python -m venv .venv');
  process.exit(1);
}

const child = spawn(
  pythonBin,
  ['-m', 'uvicorn', 'src.api.app:app', '--host', '127.0.0.1', '--port', String(API_PORT)],
  {
    cwd: REPO_ROOT,
    stdio: 'inherit',
    env: {
      ...process.env,
      // Explicit wins over any ambient values: the e2e API must use the
      // in-memory store and must allow the preview origin.
      USE_POSTGRES: 'false',
      AGENTGUARD_CORS_ORIGINS: `http://127.0.0.1:${WEB_PORT}`,
    },
  }
);

child.on('error', (err) => {
  console.error(`[launch-api] failed to start uvicorn: ${err.message}`);
  process.exit(1);
});

child.on('exit', (code, signal) => {
  console.error(`[launch-api] uvicorn exited (code=${code}, signal=${signal})`);
  process.exit(code ?? 1);
});

const shutdown = (signal) => {
  try {
    child.kill(signal);
  } catch {
    // Already gone; nothing to do.
  }
};
process.on('SIGTERM', () => shutdown('SIGTERM'));
process.on('SIGINT', () => shutdown('SIGINT'));
process.on('exit', () => {
  try {
    child.kill();
  } catch {
    // Already gone; nothing to do.
  }
});
