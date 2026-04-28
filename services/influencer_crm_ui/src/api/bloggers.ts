import { api } from '@/lib/api';

export interface BloggerOut {
  id: number;
  handle: string;
  display_name: string | null;
  status: 'active' | 'paused' | 'archived';
  marketer_id: number | null;
  tags: { id: number; name: string }[];
  channels_count: number;
  integrations_count: number;
  updated_at: string;
}

export interface BloggersPage {
  items: BloggerOut[];
  next_cursor: string | null;
}

export interface BloggerListParams {
  status?: 'active' | 'paused' | 'archived';
  marketer_id?: number;
  tag_id?: number;
  q?: string;
  cursor?: string;
  limit?: number;
}

export function listBloggers(params: BloggerListParams = {}): Promise<BloggersPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v));
  }
  const q = search.toString();
  return api.get<BloggersPage>(`/bloggers${q ? `?${q}` : ''}`);
}
