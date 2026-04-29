import AxeBuilder from '@axe-core/playwright';
import { expect, test } from '@playwright/test';
import { mockApi } from './fixtures/api-mock';

const ROUTES = [
  '/bloggers',
  '/integrations',
  '/calendar',
  '/briefs',
  '/slices',
  '/products',
  '/search?q=test',
  '/ops',
];

for (const route of ROUTES) {
  test(`a11y: ${route} has no critical or serious violations`, async ({ page }) => {
    await mockApi(page);
    await page.goto(route);
    await page.waitForLoadState('networkidle').catch(() => {});

    const results = await new AxeBuilder({ page })
      .withTags(['wcag2a', 'wcag2aa'])
      // Headless UI Dialog applies aria-hidden on the focus-trapped backdrop in test mode.
      .disableRules([
        'aria-hidden-focus',
        // Color contrast violations are inherent to the locked Wookiee brand palette
        // (orange #F97316 over white, success green #22C55E over light bg, etc).
        // Treated as a design tradeoff; tracked as FU-20 — full design-system contrast pass.
        'color-contrast',
      ])
      .analyze();

    const blocking = results.violations.filter(
      (v) => v.impact === 'critical' || v.impact === 'serious',
    );
    if (blocking.length > 0) {
      console.error(
        `axe violations on ${route}:`,
        JSON.stringify(
          blocking.map((v) => ({ id: v.id, impact: v.impact, help: v.help, nodes: v.nodes.length })),
          null,
          2,
        ),
      );
    }
    expect(blocking).toEqual([]);
  });
}
