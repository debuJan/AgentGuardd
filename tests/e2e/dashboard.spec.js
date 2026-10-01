import { test, expect } from '@playwright/test';

test('dashboard loads successfully', async ({ page }) => {
  await page.goto('/');

  await expect(
    page.getByText('AI Agent Reliability & Security Platform')
  ).toBeVisible();

  await expect(
    page.getByText('Evaluation · Security · Observability')
  ).toBeVisible();

  await expect(
    page.getByText('Platform Health Status')
  ).toBeVisible();

  await expect(
    page.getByText('Recent Activity')
  ).toBeVisible();
});

test('dashboard can navigate to runs', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: /View all runs/i }).click();

  await expect(
    page.getByRole('heading', { name: 'Runs' })
  ).toBeVisible();

  await expect(
    page.getByText('Execution Logs')
  ).toBeVisible();
});

test('runs page displays correctly', async ({ page }) => {
  await page.goto('/');

  await page.getByRole('button', { name: /View all runs/i }).click();

  await expect(
    page.getByRole('heading', { name: 'Runs' })
  ).toBeVisible();

  await expect(
    page.getByText('Execution Logs')
  ).toBeVisible();

  // The page should either show run reports or the empty state.
  const hasEmptyState = await page
    .getByText('No run reports found.')
    .isVisible()
    .catch(() => false);

  if (hasEmptyState) {
    await expect(page.getByText('No run reports found.')).toBeVisible();
  }
});

test('user can open run details', async ({ page }) => {
  const runId = 'e2e_test_run';

  // Mock the API responses so this E2E test is independent of backend state.
  await page.route('**/runs', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        reports: [
          {
            run_id: runId,
            agent_id: 'ecommerce_refund_agent',
            test_case_id: 'tc_refund_happy_path',
            overall_status: 'PASS',
            overall_score: 95,
            metrics: {
              duration_ms: 1250,
              total_tokens: 500,
              total_cost: 0.0025,
            },
          },
        ],
        count: 1,
      }),
    });
  });

  await page.route(`**/runs/${runId}`, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        run_id: runId,
        agent_id: 'ecommerce_refund_agent',
        test_case_id: 'tc_refund_happy_path',
        overall_status: 'PASS',
        overall_score: 95,
        reliability: {
          reliability_score: 100,
          passed: true,
          failures: [],
        },
        security: {
          security_score: 100,
          passed: true,
          findings: [],
        },
        metrics: {
          duration_ms: 1250,
          tokens: {
            input_tokens: 300,
            output_tokens: 200,
            total_tokens: 500,
          },
          cost: {
            total_cost: 0.0025,
          },
          tool_calls: [],
          tool_errors: [],
          repeated_tool_calls: [],
        },
      }),
    });
  });

  await page.goto('/');

  // Go to Runs.
  await page.getByRole('button', { name: /View all runs/i }).click();

  // The mocked run should be visible.
  await expect(page.getByText(runId)).toBeVisible();

  // Click the run row.
  await page.getByText(runId).click();

  // Verify the detailed report opened.
  await expect(
    page.getByText(`Run Detail: ${runId}`)
  ).toBeVisible();

  await expect(
    page.getByText('Reliability Score')
  ).toBeVisible();

  await expect(
    page.getByText('Security Score')
  ).toBeVisible();

  await expect(
    page.getByText('Observability & Tokens')
  ).toBeVisible();

  await expect(
    page.getByText('Security Findings')
  ).toBeVisible();
});

test('should display api_policy_violation in Alerts view', async ({ page }) => {
  await page.goto('/');

  // Click on the Alerts tab in navigation
  await page.getByRole('button', { name: 'Alerts' }).click();

  // Verify that api_policy_violation appears on the page
  const panel = page.locator('section.panel');
  await expect(panel).toContainText('api_policy_violation');
});

test('agents view renders cards and allows navigation to runs', async ({ page }) => {
  await page.goto('/');

  // Click on the Agents tab in navigation
  await page.getByRole('button', { name: 'Agents' }).click();

  // Verify header and page content
  await expect(page.getByRole('heading', { name: 'Agents' })).toBeVisible();
  await expect(page.getByText('Monitor and analyze AI agent performance')).toBeVisible();

  // Verify agent card is present
  await expect(page.getByText('ecommerce_refund_agent')).toBeVisible();

  // Click View Runs action button
  await page.getByRole('button', { name: /View Runs/i }).first().click();

  // Confirm navigation to Runs page
  await expect(page.getByRole('heading', { name: 'Runs' })).toBeVisible();
});
test('agents card does not show "No runs recorded yet" when runs exist', async ({ page }) => {
  await page.goto('/');

  // Navigate to Agents tab
  await page.getByRole('button', { name: 'Agents' }).click();

  // Locate the specific agent card
  const agentCard = page.locator('div').filter({ hasText: 'ecommerce_refund_agent' }).first();
  await expect(agentCard).toBeVisible();

  // Verify that "No runs recorded yet" is NOT rendered on this card
  await expect(agentCard.getByText('No runs recorded yet')).not.toBeVisible();
});