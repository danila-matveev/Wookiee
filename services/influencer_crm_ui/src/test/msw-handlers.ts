import { http, HttpResponse } from 'msw';

export const handlers = [
  http.get('/api/bloggers', () =>
    HttpResponse.json({
      items: [
        {
          id: 1,
          handle: '_anna.blog',
          display_name: 'Anna',
          status: 'active',
          marketer_id: 7,
          tags: [],
          channels_count: 2,
          integrations_count: 5,
          updated_at: '2026-04-28T10:00:00Z',
        },
      ],
      next_cursor: null,
    }),
  ),
];
