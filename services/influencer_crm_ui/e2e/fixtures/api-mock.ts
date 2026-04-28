import type { Page } from '@playwright/test';

const USE_LIVE_BFF = process.env.PLAYWRIGHT_LIVE_BFF === '1';

/**
 * Routes all /api/** calls to fake responses. Mirrors the MSW handlers used in
 * unit tests, but lives in the Playwright runtime so we don't need MSW worker
 * registration in the browser.
 *
 * When `PLAYWRIGHT_LIVE_BFF=1`, this becomes a no-op and the browser hits the
 * real BFF via Vite's /api proxy on :8082 — useful for contract testing against
 * a real database before production cutover.
 *
 * Order matters: Playwright matches routes in REVERSE registration order
 * (last-registered wins). So we register the catch-all FIRST, the broad
 * list/collection routes NEXT, and the most-specific detail routes LAST so
 * they win the match.
 */
export async function mockApi(page: Page) {
  if (USE_LIVE_BFF) {
    // Live mode: requests pass through to /api → http://localhost:8082.
    return;
  }
  // Catch-all (lowest priority — registered first so it loses every overlap).
  await page.route('http://api.test/api/**', async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: '{"items": [], "next_cursor": null}',
    });
  });

  // Bloggers list / create
  await page.route('http://api.test/api/bloggers**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 1,
              display_handle: '_anna.blog',
              real_name: 'Anna',
              status: 'active',
              default_marketer_id: 7,
              price_story_default: '12000',
              price_reels_default: '15000',
              created_at: '2026-04-01T10:00:00Z',
              updated_at: '2026-04-28T10:00:00Z',
            },
            {
              id: 2,
              display_handle: 'milana_ru',
              real_name: 'Milana',
              status: 'in_progress',
              default_marketer_id: 7,
              price_story_default: '8000',
              price_reels_default: '11000',
              created_at: '2026-04-01T11:00:00Z',
              updated_at: '2026-04-28T11:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      });
      return;
    }
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() ?? '{}');
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          ...body,
          id: 999,
          created_at: new Date().toISOString(),
          updated_at: new Date().toISOString(),
        }),
      });
      return;
    }
    await route.continue();
  });

  // Integrations list (kanban)
  await page.route('http://api.test/api/integrations**', async (route) => {
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          items: [
            {
              id: 11,
              blogger_id: 1,
              marketer_id: 7,
              brief_id: null,
              publish_date: '2026-05-01',
              channel: 'instagram',
              ad_format: 'short_video',
              marketplace: 'wb',
              stage: 'agreed',
              outcome: null,
              is_barter: false,
              total_cost: '15000',
              cost_placement: '12000',
              cost_delivery: '0',
              cost_goods: '3000',
              erid: null,
              fact_views: null,
              fact_orders: null,
              fact_revenue: null,
              created_at: '2026-04-20T10:00:00Z',
              updated_at: '2026-04-25T10:00:00Z',
            },
            {
              id: 12,
              blogger_id: 2,
              marketer_id: 7,
              brief_id: null,
              publish_date: '2026-05-03',
              channel: 'telegram',
              ad_format: 'long_post',
              marketplace: 'ozon',
              stage: 'scheduled',
              outcome: null,
              is_barter: false,
              total_cost: '8000',
              cost_placement: '7000',
              cost_delivery: '0',
              cost_goods: '1000',
              erid: null,
              fact_views: null,
              fact_orders: null,
              fact_revenue: null,
              created_at: '2026-04-22T10:00:00Z',
              updated_at: '2026-04-26T10:00:00Z',
            },
          ],
          next_cursor: null,
        }),
      });
      return;
    }
    await route.continue();
  });

  // Search
  await page.route('http://api.test/api/search**', async (route) => {
    const url = new URL(route.request().url());
    const q = url.searchParams.get('q') ?? '';
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        bloggers: q
          ? [
              {
                id: 1,
                display_handle: '_anna.blog',
                real_name: 'Anna',
                status: 'active',
                default_marketer_id: 7,
                price_story_default: '12000',
                price_reels_default: '15000',
                created_at: '2026-04-01T10:00:00Z',
                updated_at: '2026-04-28T10:00:00Z',
              },
            ]
          : [],
        integrations: [],
      }),
    });
  });

  // Briefs (T15) — list + creation echo
  await page.route('http://api.test/api/briefs**', async (route) => {
    if (route.request().method() === 'POST') {
      const body = JSON.parse(route.request().postData() ?? '{}');
      await route.fulfill({
        status: 201,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 99,
          title: body.title ?? 'Test',
          current_version_id: 1,
          created_at: new Date().toISOString(),
        }),
      });
      return;
    }
    if (route.request().method() === 'GET') {
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({ items: [], next_cursor: null }),
      });
      return;
    }
    await route.continue();
  });

  // Single blogger detail (registered LAST among bloggers routes — wins for
  // /api/bloggers/{id} because Playwright matches last-registered first).
  await page.route(/^http:\/\/api\.test\/api\/bloggers\/\d+/, async (route) => {
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 1,
        display_handle: '_anna.blog',
        real_name: 'Anna',
        status: 'active',
        default_marketer_id: 7,
        price_story_default: '12000',
        price_reels_default: '15000',
        contact_tg: '@anna_blog',
        contact_email: 'anna@example.com',
        contact_phone: null,
        notes: null,
        geo_country: ['RU'],
        integrations_count: 5,
        integrations_done: 3,
        last_integration_at: '2026-04-15',
        total_spent: '125000',
        avg_cpm_fact: '350',
        channels: [
          { id: 1, channel: 'instagram', handle: '_anna.blog', url: null },
        ],
        created_at: '2026-04-01T10:00:00Z',
        updated_at: '2026-04-28T10:00:00Z',
      }),
    });
  });

  // Single integration detail / update
  await page.route(/^http:\/\/api\.test\/api\/integrations\/\d+/, async (route) => {
    if (route.request().method() === 'PATCH') {
      const body = JSON.parse(route.request().postData() ?? '{}');
      await route.fulfill({
        status: 200,
        contentType: 'application/json',
        body: JSON.stringify({
          id: 11,
          blogger_id: 1,
          blogger_handle: '_anna.blog',
          marketer_id: 7,
          marketer_name: 'Marketer 7',
          brief_id: null,
          publish_date: '2026-05-01',
          channel: 'instagram',
          ad_format: 'short_video',
          marketplace: 'wb',
          stage: 'agreed',
          outcome: null,
          is_barter: false,
          total_cost: '15000',
          cost_placement: '12000',
          cost_delivery: '0',
          cost_goods: '3000',
          erid: null,
          fact_views: null,
          fact_orders: null,
          fact_revenue: null,
          substitutes: [],
          posts: [],
          contract_url: null,
          post_url: null,
          tz_url: null,
          post_content: null,
          notes: null,
          has_marking: null,
          has_contract: null,
          created_at: '2026-04-20T10:00:00Z',
          updated_at: new Date().toISOString(),
          ...body,
        }),
      });
      return;
    }
    // GET detail
    await route.fulfill({
      status: 200,
      contentType: 'application/json',
      body: JSON.stringify({
        id: 11,
        blogger_id: 1,
        blogger_handle: '_anna.blog',
        marketer_id: 7,
        marketer_name: 'Marketer 7',
        brief_id: null,
        publish_date: '2026-05-01',
        channel: 'instagram',
        ad_format: 'short_video',
        marketplace: 'wb',
        stage: 'agreed',
        outcome: null,
        is_barter: false,
        total_cost: '15000',
        cost_placement: '12000',
        cost_delivery: '0',
        cost_goods: '3000',
        erid: null,
        fact_views: null,
        fact_orders: null,
        fact_revenue: null,
        substitutes: [],
        posts: [],
        contract_url: null,
        post_url: null,
        tz_url: null,
        post_content: null,
        notes: null,
        has_marking: null,
        has_contract: null,
        created_at: '2026-04-20T10:00:00Z',
        updated_at: '2026-04-25T10:00:00Z',
      }),
    });
  });
}
