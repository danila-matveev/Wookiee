import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

test('GP-1: bloggers list renders and detail row expands', async ({ page }) => {
  await mockApi(page);
  await page.goto('/bloggers');

  await expect(page.getByRole('heading', { name: 'Блогеры' })).toBeVisible();
  await expect(page.getByText('_anna.blog').first()).toBeVisible();

  // Click the row to expand — fetches /api/bloggers/1 and shows detail.
  await page.getByText('_anna.blog').first().click();
  await expect(page.getByText(/Anna/).first()).toBeVisible();
});
