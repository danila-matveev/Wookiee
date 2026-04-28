import { HttpResponse, http } from 'msw';

const integrationsFixture = [
  {
    id: 1,
    blogger_id: 11,
    marketer_id: 7,
    brief_id: 101,
    publish_date: '2026-05-12',
    channel: 'instagram',
    ad_format: 'story',
    marketplace: 'wb',
    stage: 'lead',
    outcome: null,
    is_barter: false,
    cost_placement: '15000',
    cost_delivery: null,
    cost_goods: null,
    total_cost: '15000',
    erid: null,
    fact_views: null,
    fact_orders: null,
    fact_revenue: null,
    created_at: '2026-04-20T10:00:00Z',
    updated_at: '2026-04-20T10:00:00Z',
  },
  {
    id: 2,
    blogger_id: 12,
    marketer_id: 7,
    brief_id: null,
    publish_date: '2026-05-15',
    channel: 'telegram',
    ad_format: 'long_post',
    marketplace: 'ozon',
    stage: 'negotiation',
    outcome: null,
    is_barter: false,
    cost_placement: '8000',
    cost_delivery: null,
    cost_goods: null,
    total_cost: '8000',
    erid: null,
    fact_views: null,
    fact_orders: null,
    fact_revenue: null,
    created_at: '2026-04-21T10:00:00Z',
    updated_at: '2026-04-21T10:00:00Z',
  },
  {
    id: 3,
    blogger_id: 13,
    marketer_id: 7,
    brief_id: 103,
    publish_date: '2026-05-18',
    channel: 'tiktok',
    ad_format: 'short_video',
    marketplace: 'both',
    stage: 'scheduled',
    outcome: null,
    is_barter: true,
    cost_placement: null,
    cost_delivery: '500',
    cost_goods: '2500',
    total_cost: '3000',
    erid: null,
    fact_views: null,
    fact_orders: null,
    fact_revenue: null,
    created_at: '2026-04-22T10:00:00Z',
    updated_at: '2026-04-22T10:00:00Z',
  },
  {
    id: 4,
    blogger_id: 14,
    marketer_id: 8,
    brief_id: null,
    publish_date: '2026-05-20',
    channel: 'youtube',
    ad_format: 'integration',
    marketplace: 'wb',
    stage: 'published',
    outcome: null,
    is_barter: false,
    cost_placement: '50000',
    cost_delivery: null,
    cost_goods: null,
    total_cost: '50000',
    erid: 'abc123',
    fact_views: 12000,
    fact_orders: null,
    fact_revenue: null,
    created_at: '2026-04-23T10:00:00Z',
    updated_at: '2026-04-23T10:00:00Z',
  },
];

export const handlers = [
  http.get('/api/integrations', () =>
    HttpResponse.json({ items: integrationsFixture, next_cursor: null }),
  ),
  http.get('/api/integrations/:id', ({ params }) => {
    const id = Number(params.id);
    const base = integrationsFixture.find((i) => i.id === id) ?? integrationsFixture[0];
    return HttpResponse.json({
      ...base,
      id,
      blogger_handle: '_anna.blog',
      marketer_name: 'Маркетолог Иван',
      substitutes: [],
      posts: [],
      contract_url: null,
      post_url: null,
      tz_url: null,
      post_content: null,
      notes: null,
      has_marking: null,
      has_contract: null,
    });
  }),
  http.patch('/api/integrations/:id', async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const existing = integrationsFixture.find((i) => i.id === Number(params.id));
    return HttpResponse.json({
      ...(existing ?? integrationsFixture[0]),
      ...body,
      id: Number(params.id),
      updated_at: new Date().toISOString(),
    });
  }),
  http.post('/api/integrations', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const now = new Date().toISOString();
    return HttpResponse.json(
      {
        id: 999,
        blogger_id: body.blogger_id ?? 0,
        marketer_id: body.marketer_id ?? 0,
        brief_id: null,
        publish_date: body.publish_date ?? '2026-05-01',
        channel: body.channel ?? 'instagram',
        ad_format: body.ad_format ?? 'story',
        marketplace: body.marketplace ?? 'wb',
        stage: body.stage ?? 'lead',
        outcome: null,
        is_barter: body.is_barter ?? false,
        cost_placement: body.cost_placement ?? null,
        cost_delivery: body.cost_delivery ?? null,
        cost_goods: body.cost_goods ?? null,
        total_cost: '0',
        erid: body.erid ?? null,
        fact_views: null,
        fact_orders: null,
        fact_revenue: null,
        created_at: now,
        updated_at: now,
      },
      { status: 201 },
    );
  }),
  http.get('/api/bloggers', () =>
    HttpResponse.json({
      items: [
        {
          id: 1,
          display_handle: '_anna.blog',
          real_name: 'Anna',
          status: 'active',
          default_marketer_id: 7,
          price_story_default: null,
          price_reels_default: null,
          created_at: '2026-04-01T10:00:00Z',
          updated_at: '2026-04-28T10:00:00Z',
        },
      ],
      next_cursor: null,
    }),
  ),
  http.get('/api/bloggers/:id', ({ params }) =>
    HttpResponse.json({
      id: Number(params.id),
      display_handle: '_anna.blog',
      real_name: 'Anna',
      status: 'active',
      default_marketer_id: 7,
      price_story_default: null,
      price_reels_default: null,
      created_at: '2026-04-01T10:00:00Z',
      updated_at: '2026-04-28T10:00:00Z',
      channels: [],
      integrations_count: 5,
      integrations_done: 3,
      last_integration_at: '2026-04-20T10:00:00Z',
      total_spent: '0',
      avg_cpm_fact: null,
      contact_tg: null,
      contact_email: null,
      contact_phone: null,
      notes: null,
      geo_country: null,
    }),
  ),
  http.post('/api/bloggers', async ({ request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const now = new Date().toISOString();
    return HttpResponse.json(
      {
        id: 999,
        display_handle: body.display_handle ?? '',
        real_name: body.real_name ?? null,
        status: body.status ?? 'new',
        default_marketer_id: body.default_marketer_id ?? null,
        price_story_default: body.price_story_default ?? null,
        price_reels_default: body.price_reels_default ?? null,
        created_at: now,
        updated_at: now,
      },
      { status: 201 },
    );
  }),
  http.patch('/api/bloggers/:id', async ({ params, request }) => {
    const body = (await request.json()) as Record<string, unknown>;
    const now = new Date().toISOString();
    return HttpResponse.json({
      id: Number(params.id),
      display_handle: body.display_handle ?? '_anna.blog',
      real_name: body.real_name ?? null,
      status: body.status ?? 'active',
      default_marketer_id: body.default_marketer_id ?? null,
      price_story_default: body.price_story_default ?? null,
      price_reels_default: body.price_reels_default ?? null,
      created_at: '2026-04-01T10:00:00Z',
      updated_at: now,
    });
  }),
  // --- Briefs (T15) ----------------------------------------------------------
  // The real BFF currently only ships POST /briefs, POST /briefs/{id}/versions,
  // GET /briefs/{id}/versions. The list/detail/PATCH endpoints used by the UI
  // are anticipated — handlers here echo fixtures to keep the page testable.
  ...(() => {
    const briefsFixture = [
      {
        id: 101,
        title: 'ТЗ для Анны / WB / сторис',
        status: 'draft',
        current_version: 1,
        current_version_id: 5001,
        blogger_id: 11,
        blogger_handle: '_anna.blog',
        integration_id: null,
        scheduled_at: '2026-05-12',
        budget: '15000',
        created_at: '2026-04-20T10:00:00Z',
        updated_at: '2026-04-20T10:00:00Z',
      },
      {
        id: 102,
        title: 'OZON интеграция / Telegram',
        status: 'on_review',
        current_version: 2,
        current_version_id: 5002,
        blogger_id: 12,
        blogger_handle: 'tg_blogger',
        integration_id: null,
        scheduled_at: '2026-05-15',
        budget: '8000',
        created_at: '2026-04-21T10:00:00Z',
        updated_at: '2026-04-22T10:00:00Z',
      },
      {
        id: 103,
        title: 'TikTok бартер',
        status: 'signed',
        current_version: 3,
        current_version_id: 5003,
        blogger_id: 13,
        blogger_handle: 'tiktok_blogger',
        integration_id: 3,
        scheduled_at: '2026-05-18',
        budget: null,
        created_at: '2026-04-22T10:00:00Z',
        updated_at: '2026-04-23T10:00:00Z',
      },
      {
        id: 104,
        title: 'YouTube long-form',
        status: 'completed',
        current_version: 4,
        current_version_id: 5004,
        blogger_id: 14,
        blogger_handle: 'yt_blogger',
        integration_id: 4,
        scheduled_at: '2026-04-30',
        budget: '50000',
        created_at: '2026-04-10T10:00:00Z',
        updated_at: '2026-04-25T10:00:00Z',
      },
    ];

    return [
      http.get('/api/briefs', () => HttpResponse.json({ items: briefsFixture, next_cursor: null })),
      http.get('/api/briefs/:id', ({ params }) => {
        const id = Number(params.id);
        const base = briefsFixture.find((b) => b.id === id) ?? briefsFixture[0];
        return HttpResponse.json({
          ...base,
          id,
          content_md: `# ${base.title}\n\n- Пункт 1\n- Пункт 2`,
          versions: [
            {
              id: base.current_version_id,
              brief_id: id,
              version: base.current_version,
              content_md: `# ${base.title}\n\n- Пункт 1\n- Пункт 2`,
              created_at: base.updated_at,
            },
          ],
        });
      }),
      http.post('/api/briefs', async ({ request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const now = new Date().toISOString();
        return HttpResponse.json(
          {
            id: 999,
            title: body.title ?? '',
            status: 'draft',
            current_version: 1,
            current_version_id: 5999,
            blogger_id: body.blogger_id ?? null,
            blogger_handle: null,
            integration_id: body.integration_id ?? null,
            scheduled_at: null,
            budget: null,
            created_at: now,
            updated_at: now,
          },
          { status: 201 },
        );
      }),
      http.post('/api/briefs/:id/versions', async ({ params, request }) => {
        const body = (await request.json()) as { content_md?: string };
        const briefId = Number(params.id);
        const now = new Date().toISOString();
        // Echo back: simulate a freshly-created version row.
        return HttpResponse.json(
          {
            id: 6000 + briefId,
            brief_id: briefId,
            version: 2,
            content_md: body.content_md ?? '',
            created_at: now,
          },
          { status: 201 },
        );
      }),
      http.patch('/api/briefs/:id', async ({ params, request }) => {
        const body = (await request.json()) as Record<string, unknown>;
        const id = Number(params.id);
        const existing = briefsFixture.find((b) => b.id === id) ?? briefsFixture[0];
        const now = new Date().toISOString();
        return HttpResponse.json({
          ...existing,
          ...body,
          id,
          updated_at: now,
        });
      }),
    ];
  })(),
];
