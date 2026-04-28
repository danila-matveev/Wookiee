import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

test('GP-4: briefs page renders kanban columns', async ({ page }) => {
  await mockApi(page);
  await page.goto('/briefs');

  await expect(page.getByRole('heading', { name: /Брифы/ })).toBeVisible();
  // Empty kanban: at least the column titles render. There are two elements
  // with text "Черновик" (a status filter pill and a column heading) — match
  // the heading explicitly to avoid strict-mode violation.
  await expect(page.getByRole('heading', { name: 'Черновик' })).toBeVisible();
});
