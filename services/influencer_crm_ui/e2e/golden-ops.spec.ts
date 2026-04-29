import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

/**
 * GP-Ops: smoke test for the /ops dashboard.
 *
 * Mocks GET /ops/health with a synthetic OpsHealth response (3 KPIs +
 * 4 cron jobs + retention queue) and verifies all sections render. The
 * /ops/health route is registered BEFORE the catch-all in api-mock so
 * the broader catch-all wins last; we therefore stub it inline here
 * (page.route registered in this spec is appended LAST → wins via
 * Playwright's reverse-priority matching).
 */
test('GP-Ops: /ops dashboard renders KPIs, cron table and retention queue', async ({ page }) => {
  await mockApi(page);

  // Inline /ops/health stub — registered AFTER mockApi so it wins for this URL.
  await page.route('http://api.test/api/ops/health', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        etl_last_run: {
          started_at: '2026-04-28T20:00:00Z',
          status: 'success',
          duration_ms: 4200,
          error_message: null,
        },
        etl_last_24h: { success: 4, failed: 0 },
        mv_age_seconds: 180,
        retention: {
          audit_log_eligible_for_delete: 12,
          snapshots_eligible_for_delete: 3,
        },
        cron_jobs: [
          { jobname: 'crm_refresh_v_blogger_totals', schedule: '*/5 * * * *', active: true },
          { jobname: 'crm_retention_audit_log', schedule: '0 3 * * 0', active: true },
          { jobname: 'crm_retention_snapshots', schedule: '0 4 * * 0', active: true },
          { jobname: 'crm_sheets_etl', schedule: '0 */6 * * *', active: true },
        ],
      }),
    });
  });

  await page.goto('/ops');

  // Page header.
  await expect(page.getByRole('heading', { name: /ops/i, level: 1 })).toBeVisible();

  // 3 KPI cards by their visible labels.
  await expect(page.getByText('ETL — последний запуск')).toBeVisible();
  await expect(page.getByText('Свежесть MV')).toBeVisible();
  await expect(page.getByText('Сбои за 24ч')).toBeVisible();

  // Cron table — 4 rows. The table lives in the section after the KPI grid;
  // count <tbody> rows directly to avoid coupling to row text content.
  const cronRows = page.locator('table tbody tr');
  await expect(cronRows).toHaveCount(4);
  await expect(page.getByText('crm_refresh_v_blogger_totals')).toBeVisible();
  await expect(page.getByText('crm_sheets_etl')).toBeVisible();

  // Retention section.
  await expect(page.getByText('Очередь retention')).toBeVisible();
  await expect(page.getByText('audit_log > 90 дн.')).toBeVisible();
  await expect(page.getByText('snapshots > 365 дн.')).toBeVisible();
});
