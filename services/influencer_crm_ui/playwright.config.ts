import { defineConfig, devices } from '@playwright/test';

export default defineConfig({
  testDir: './e2e',
  testMatch: '**/*.spec.ts',
  fullyParallel: false,
  retries: 0,
  webServer: {
    command: 'pnpm dev',
    url: 'http://localhost:5173',
    timeout: 120_000,
    reuseExistingServer: !process.env.CI,
    env: {
      // Bypass Vite's `/api` -> :8082 proxy: point the browser at a synthetic
      // host that Playwright's `page.route('**/api/**')` can intercept directly.
      // Without this, Vite proxies the request server-side and returns 502 when
      // the BFF isn't running, so the mock never sees the call.
      VITE_API_BASE_URL: 'http://api.test/api',
      VITE_API_KEY: 'e2e-fake-key',
    },
  },
  use: {
    baseURL: 'http://localhost:5173',
    trace: 'on-first-retry',
    screenshot: 'only-on-failure',
  },
  projects: [
    {
      name: 'desktop-chrome',
      use: { ...devices['Desktop Chrome'], viewport: { width: 1440, height: 900 } },
    },
  ],
});
