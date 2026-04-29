import { api } from '@/lib/api';

// Stage tuple — matches BFF schemas/integration.py exactly (10 columns Kanban).
export const STAGES = [
  'lead',
  'negotiation',
  'agreed',
  'content_received',
  'content_approved',
  'scheduled',
  'published',
  'paid',
  'done',
  'rejected',
] as const;

export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  lead: 'Лид',
  negotiation: 'Переговоры',
  agreed: 'Согласовано',
  content_received: 'Контент получен',
  content_approved: 'Контент утверждён',
  scheduled: 'Запланировано',
  published: 'Опубликовано',
  paid: 'Оплачено',
  done: 'Готово',
  rejected: 'Отклонено',
};

export type Outcome = 'delivered' | 'cancelled' | 'no_show' | 'failed_compliance';
export type Channel = 'instagram' | 'telegram' | 'tiktok' | 'youtube' | 'vk' | 'rutube';
export type AdFormat =
  | 'story'
  | 'short_video'
  | 'long_video'
  | 'long_post'
  | 'image_post'
  | 'integration'
  | 'live_stream';
export type Marketplace = 'wb' | 'ozon' | 'both';

export interface IntegrationOut {
  id: number;
  blogger_id: number;
  marketer_id: number;
  brief_id: number | null;
  publish_date: string; // ISO date
  channel: Channel;
  ad_format: AdFormat;
  marketplace: Marketplace;
  stage: Stage;
  outcome: Outcome | null;
  is_barter: boolean;
  cost_placement: string | null;
  cost_delivery: string | null;
  cost_goods: string | null;
  total_cost: string;
  erid: string | null;
  fact_views: number | null;
  fact_orders: number | null;
  fact_revenue: string | null;
  created_at: string | null;
  updated_at: string | null;
}

export interface IntegrationSubstituteOut {
  substitute_article_id: number;
  code: string;
  artikul_id: number | null;
  display_order: number;
  tracking_url: string | null;
}

export interface IntegrationPostOut {
  id: number;
  post_url: string | null;
  posted_at: string | null;
  fact_views: number | null;
  fact_clicks: number | null;
}

export interface IntegrationDetailOut extends IntegrationOut {
  blogger_handle: string;
  marketer_name: string;
  substitutes: IntegrationSubstituteOut[];
  posts: IntegrationPostOut[];
  contract_url: string | null;
  post_url: string | null;
  tz_url: string | null;
  post_content: string | null;
  notes: string | null;
  has_marking: boolean | null;
  has_contract: boolean | null;
}

export interface IntegrationsPage {
  items: IntegrationOut[];
  next_cursor: string | null;
}

export interface IntegrationListParams {
  stage_in?: Stage[];
  marketplace?: Marketplace;
  marketer_id?: number;
  blogger_id?: number;
  date_from?: string;
  date_to?: string;
  cursor?: string;
  limit?: number;
}

export function listIntegrations(params: IntegrationListParams = {}): Promise<IntegrationsPage> {
  const search = new URLSearchParams();
  for (const [k, v] of Object.entries(params)) {
    if (v === undefined) continue;
    if (Array.isArray(v)) {
      for (const item of v) search.append(k, String(item));
    } else {
      search.set(k, String(v));
    }
  }
  const q = search.toString();
  return api.get<IntegrationsPage>(`/integrations${q ? `?${q}` : ''}`);
}

export function getIntegration(id: number): Promise<IntegrationDetailOut> {
  return api.get<IntegrationDetailOut>(`/integrations/${id}`);
}

export interface IntegrationUpdate {
  blogger_id?: number;
  marketer_id?: number;
  publish_date?: string;
  channel?: Channel;
  ad_format?: AdFormat;
  marketplace?: Marketplace;
  stage?: Stage;
  outcome?: Outcome | null;
  is_barter?: boolean;
  cost_placement?: string | null;
  cost_delivery?: string | null;
  cost_goods?: string | null;
  erid?: string | null;
  notes?: string | null;
  fact_views?: number | null;
  fact_orders?: number | null;
  fact_revenue?: string | null;
}

/**
 * Mirrors `IntegrationCreate` on the BFF — a strict superset of `IntegrationUpdate`
 * where blogger_id/marketer_id/publish_date/channel/ad_format/marketplace are required.
 * Used by the upsert form: when no id is set we POST this; when id is set we PATCH the
 * partial slice. We type as a shared shape and let the runtime pick which endpoint to hit.
 */
export interface IntegrationInput {
  blogger_id: number;
  marketer_id: number;
  publish_date: string;
  channel: Channel;
  ad_format: AdFormat;
  marketplace: Marketplace;
  stage?: Stage;
  outcome?: Outcome | null;
  is_barter?: boolean;
  cost_placement?: string | null;
  cost_delivery?: string | null;
  cost_goods?: string | null;
  erid?: string | null;
  notes?: string | null;
  fact_views?: number | null;
  fact_orders?: number | null;
  fact_revenue?: string | null;
}

export function createIntegration(body: IntegrationInput): Promise<IntegrationOut> {
  return api.post<IntegrationOut>('/integrations', body);
}

export function updateIntegration(id: number, body: IntegrationUpdate): Promise<IntegrationOut> {
  return api.patch<IntegrationOut>(`/integrations/${id}`, body);
}
