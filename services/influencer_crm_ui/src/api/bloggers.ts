import { api } from '@/lib/api';

export type BloggerStatus = 'active' | 'in_progress' | 'new' | 'paused';

export interface BloggerOut {
  id: number;
  display_handle: string;
  real_name: string | null;
  status: BloggerStatus;
  default_marketer_id: number | null;
  price_story_default: string | null;
  price_reels_default: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface BloggerChannelOut {
  id: number;
  channel: string;
  handle: string;
  url: string | null;
}

export interface BloggerDetailOut extends BloggerOut {
  channels: BloggerChannelOut[];
  integrations_count: number;
  integrations_done: number;
  last_integration_at: string | null;
  total_spent: string;
  avg_cpm_fact: string | null;
  contact_tg: string | null;
  contact_email: string | null;
  contact_phone: string | null;
  notes: string | null;
  geo_country: string[] | null;
}

export interface BloggersPage {
  items: BloggerOut[];
  next_cursor: string | null;
}

export interface BloggerListParams {
  status?: BloggerStatus;
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

export function getBlogger(id: number): Promise<BloggerDetailOut> {
  return api.get<BloggerDetailOut>(`/bloggers/${id}`);
}
