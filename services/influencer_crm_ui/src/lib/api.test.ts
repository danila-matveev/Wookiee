import { describe, expect, it, vi, beforeEach } from 'vitest';
import { api, ApiError } from './api';

describe('api client', () => {
  beforeEach(() => {
    vi.stubGlobal('fetch', vi.fn());
    import.meta.env.VITE_API_KEY = 'test-key';
    import.meta.env.VITE_API_BASE_URL = 'http://test';
  });

  it('sends X-API-Key header on every request', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce(
      new Response(JSON.stringify({ items: [], next_cursor: null }), {
        status: 200,
        headers: { 'content-type': 'application/json', etag: 'W/"abc"' },
      }),
    );
    await api.get('/bloggers');
    const [, init] = (globalThis.fetch as any).mock.calls[0];
    expect(init.headers['X-API-Key']).toBe('test-key');
  });

  it('throws ApiError with status on non-2xx', async () => {
    (globalThis.fetch as any).mockResolvedValueOnce(
      new Response(JSON.stringify({ detail: 'nope' }), { status: 404 }),
    );
    await expect(api.get('/bloggers/9999')).rejects.toBeInstanceOf(ApiError);
  });

  it('caches ETag and sends If-None-Match on repeat GET', async () => {
    (globalThis.fetch as any)
      .mockResolvedValueOnce(
        new Response(JSON.stringify({ id: 1 }), {
          status: 200,
          headers: { etag: 'W/"v1"' },
        }),
      )
      .mockResolvedValueOnce(new Response(null, { status: 304 }));
    await api.get('/bloggers/1');
    const result = await api.get('/bloggers/1');
    const [, init] = (globalThis.fetch as any).mock.calls[1];
    expect(init.headers['If-None-Match']).toBe('W/"v1"');
    expect(result).toEqual({ id: 1 }); // served from cache on 304
  });
});
