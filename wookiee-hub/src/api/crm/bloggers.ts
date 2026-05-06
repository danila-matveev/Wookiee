import { crmApi } from '@/lib/crm-api';

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

export interface ChannelBrief {
  id: number;
  channel: string;
  handle: string;
  url: string | null;
}

export interface BloggerSummaryOut {
  id: number;
  display_handle: string;
  real_name: string | null;
  status: BloggerStatus;
  default_marketer_id: number | null;
  price_story_default: string | null;
  price_reels_default: string | null;
  created_at: string | null;
  updated_at: string | null;
  channels: ChannelBrief[];
  integrations_count: number;
  integrations_done: number;
  last_integration_at: string | null;
  total_spent: string;
  avg_cpm_fact: string | null;
}

export interface BloggerSummaryPage {
  items: BloggerSummaryOut[];
  total: number;
}

export interface BloggerSummaryParams {
  status?: BloggerStatus;
  q?: string;
  channel?: string;
  limit?: number;
  offset?: number;
}

export function listBloggersSummary(params: BloggerSummaryParams = {}): Promise<BloggerSummaryPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v !== undefined) search.set(k, String(v));
  }
  const qs = search.toString();
  return crmApi.get<BloggerSummaryPage>(`/bloggers/summary${qs ? `?${qs}` : ''}`);
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
  return crmApi.get<BloggersPage>(`/bloggers${q ? `?${q}` : ''}`);
}

export function getBlogger(id: number): Promise<BloggerDetailOut> {
  return crmApi.get<BloggerDetailOut>(`/bloggers/${id}`);
}

export interface BloggerInput {
  display_handle: string;
  real_name?: string | null;
  status?: BloggerStatus;
  default_marketer_id?: number | null;
  price_story_default?: string | null;
  price_reels_default?: string | null;
  contact_tg?: string | null;
  contact_email?: string | null;
  contact_phone?: string | null;
  notes?: string | null;
}

export function createBlogger(body: BloggerInput): Promise<BloggerOut> {
  return crmApi.post<BloggerOut>('/bloggers', body);
}

export function updateBlogger(id: number, body: Partial<BloggerInput>): Promise<BloggerOut> {
  return crmApi.patch<BloggerOut>(`/bloggers/${id}`, body);
}
