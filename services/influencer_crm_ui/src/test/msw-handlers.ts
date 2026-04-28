import { HttpResponse, http } from 'msw';

export const handlers = [
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
];
