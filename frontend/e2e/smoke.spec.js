import { test, expect } from '@playwright/test';

/**
 * Deterministic dashboard smoke test.
 *
 * Each test seeds its own run through the real API (canned trace + config,
 * no LLM), so tests are independent of execution order and of how Playwright
 * loads/isolates test files across workers.
 */

const API = 'http://127.0.0.1:8001';

const AGENT = { name: 'e2e_agent', description: 'Playwright smoke-test agent' };
const TEST_CASE = {
  id: 'tc_e2e_smoke',
  agent_name: 'e2e_agent',
  category: 'functional',
  user_input: 'Say hello.',
  expected_outcome: 'hello',
};

function cannedRunPayload(runId) {
  return {
    agent_config: AGENT,
    test_case: TEST_CASE,
    trace: {
      run_id: runId,
      agent_id: 'e2e_agent',
      test_case_id: 'tc_e2e_smoke',
      events: [{ type: 'final_response', content: 'hello' }],
    },
  };
}

/** Seed one run via the real API; returns its unique run id. */
async function seedRun(request) {
  const runId = `run_e2e_${Date.now()}_${Math.floor(Math.random() * 1e6)}`;
  const res = await request.post(`${API}/runs`, {
    data: cannedRunPayload(runId),
  });
  expect(res.status()).toBe(201);
  const body = await res.json();
  expect(body.run_id).toBe(runId);
  expect(body.overall_status).toBe('PASS');
  expect(body.metrics).toBeDefined();
  return runId;
}

test.describe('AgentGuard dashboard smoke', () => {
  test('frontend is configured against the e2e API', async ({ page }) => {
    // Guard against a stale frontend bundle: the API base URL is baked in
    // at build time (see src/api/client.js). If the served UI was built
    // without VITE_API_BASE_URL=http://127.0.0.1:8001, every UI assertion
    // below would silently talk to the wrong backend. The Settings view
    // renders the baked-in value; fail fast if it is not the e2e API.
    await page.goto('/');
    await page.getByRole('button', { name: /settings/i }).first().click();
    await expect(page.getByText(API, { exact: true })).toBeVisible({
      timeout: 15000,
    });
  });

  test('e2e API allows the preview origin via CORS', async ({ request }) => {
    // Regression test for the runs-list failure root-caused on 2026-09-29:
    // the e2e harness launched the API without AGENTGUARD_CORS_ORIGINS, so
    // the API answered the browser's preflight with 400 and Chromium blocked
    // every API response. The UI then rendered "API Unavailable" even though
    // the API itself stored and served runs correctly. The harness must
    // launch the API with the preview origin allowed.
    const origin = 'http://127.0.0.1:4173';
    const res = await request.get(`${API}/health`, {
      headers: { Origin: origin },
    });
    expect(res.ok()).toBeTruthy();
    expect(res.headers()['access-control-allow-origin']).toBe(origin);

    const preflight = await request.fetch(`${API}/runs`, {
      method: 'OPTIONS',
      headers: {
        Origin: origin,
        'Access-Control-Request-Method': 'GET',
        'Access-Control-Request-Headers': 'content-type',
      },
    });
    expect(preflight.status()).toBe(200);
    expect(preflight.headers()['access-control-allow-origin']).toBe(origin);
  });

  test('seed a run via the API', async ({ request }) => {
    const health = await request.get(`${API}/health`);
    expect(health.ok()).toBeTruthy();

    await seedRun(request);
  });

  test('runs list shows the seeded run', async ({ page, request }) => {
    const runId = await seedRun(request);

    await page.goto('/');
    // Sidebar -> Runs view.
    await page.getByRole('button', { name: /runs/i }).first().click();
    await expect(page.getByText(runId)).toBeVisible({ timeout: 15000 });
  });

  test('run detail shows reliability and security sections', async ({ page, request }) => {
    const runId = await seedRun(request);

    await page.goto('/');
    await page.getByRole('button', { name: /runs/i }).first().click();
    await page.getByText(runId).click();
    // Detail view renders the report: status, scores, metrics.
    await expect(page.getByText(/reliability/i).first()).toBeVisible({ timeout: 15000 });
    await expect(page.getByText(/security/i).first()).toBeVisible();
  });

  test('delete the seeded run via the API', async ({ request, page }) => {
    const runId = await seedRun(request);

    const del = await request.delete(`${API}/runs/${runId}`);
    expect(del.ok()).toBeTruthy();

    await page.goto('/');
    await page.getByRole('button', { name: /runs/i }).first().click();
    await expect(page.getByText(runId)).toHaveCount(0);
  });
});
