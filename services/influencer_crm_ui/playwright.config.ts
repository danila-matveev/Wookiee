import { defineConfig, devices } from '@playwright/test';

const USE_LIVE_BFF = process.env.PLAYWRIGHT_LIVE_BFF === '1';

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
    env: USE_LIVE_BFF
      ? {
          // Live mode: hit the real BFF on :8082 via Vite's /api proxy.
          // Requires the backend running and INFLUENCER_CRM_API_KEY in env.
          VITE_API_BASE_URL: '/api',
          VITE_API_KEY: process.env.INFLUENCER_CRM_API_KEY ?? '',
        }
      : {
          // Mock mode (default): bypass Vite proxy via synthetic hostname so
          // page.route('**/api/**') intercepts directly. Without this, Vite
          // proxies the request server-side and returns 502 without a BFF.
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
