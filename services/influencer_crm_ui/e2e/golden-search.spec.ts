import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

test('GP-3: top bar search navigates and renders results', async ({ page }) => {
  await mockApi(page);
  await page.goto('/');

  // Wait for redirect from / to /bloggers.
  await expect(page).toHaveURL(/\/bloggers/);

  // Type in TopBar search and submit.
  const searchInput = page.getByRole('searchbox');
  await searchInput.fill('anna');
  await searchInput.press('Enter');

  await expect(page).toHaveURL(/\/search\?q=anna/);
  await expect(page.getByText('_anna.blog').first()).toBeVisible();
});
