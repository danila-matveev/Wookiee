import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

test('GP-2: integrations kanban shows columns and cards', async ({ page }) => {
  await mockApi(page);
  await page.goto('/integrations');

  await expect(page.getByRole('heading', { name: 'Интеграции' })).toBeVisible();
  // Two cards from the fixture, in `agreed` and `scheduled` columns.
  await expect(page.getByText('Блогер #1')).toBeVisible();
  await expect(page.getByText('Блогер #2')).toBeVisible();
});
