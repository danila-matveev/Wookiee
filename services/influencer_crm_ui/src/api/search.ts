import type { BloggerOut } from '@/api/bloggers';
import type { IntegrationOut } from '@/api/integrations';
import { api } from '@/lib/api';

/**
 * Shape of `GET /search?q=...` on the BFF (services/influencer_crm/routers/search.py):
 *   { bloggers: BloggerOut[], integrations: IntegrationOut[] }
 *
 * Both lists are capped server-side by the `limit` query param (default 10, max 50).
 * No pagination cursor — search is intentionally a small "top hits" view.
 */
export interface SearchResponse {
  bloggers: BloggerOut[];
  integrations: IntegrationOut[];
}

export function searchAll(q: string, limit = 10): Promise<SearchResponse> {
  const params = new URLSearchParams({ q, limit: String(limit) });
  return api.get<SearchResponse>(`/search?${params.toString()}`);
}
