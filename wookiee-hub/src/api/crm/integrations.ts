import { crmApi } from '@/lib/crm-api';

// Stage tuple — matches BFF schemas/integration.py exactly (8-stage Russian funnel).
export const STAGES = [
  'переговоры',
  'согласовано',
  'отправка_комплекта',
  'контент',
  'запланировано',
  'аналитика',
  'завершено',
  'архив',
] as const;

export type Stage = (typeof STAGES)[number];

export const STAGE_LABELS: Record<Stage, string> = {
  переговоры: 'Переговоры',
  согласовано: 'Согласовано',
  отправка_комплекта: 'Отправка комплекта',
  контент: 'Контент',
  запланировано: 'Запланировано',
  аналитика: 'Аналитика',
  завершено: 'Завершено',
  архив: 'Архив',
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
  blogger_handle: string | null;
  marketer_id: number | null;
  marketer_name: string | null;
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
  primary_substitute_code: string | null;
  // Audience
  theme: string | null;
  audience_age: string | null;
  subscribers: number | null;
  min_reach: number | null;
  engagement_rate: string | null;
  // Plan metrics
  plan_cpm: string | null;
  plan_ctr: string | null;
  plan_clicks: number | null;
  plan_cpc: string | null;
  // Fact metrics
  fact_views: number | null;
  fact_cpm: string | null;
  fact_clicks: number | null;
  fact_ctr: string | null;
  fact_cpc: string | null;
  fact_carts: number | null;
  cr_to_cart: string | null;
  fact_orders: number | null;
  cr_to_order: string | null;
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
  // Content & links
  contract_url: string | null;
  post_url: string | null;
  tz_url: string | null;
  screen_url: string | null;
  post_content: string | null;
  analysis: string | null;
  recommended_models: string | null;
  notes: string | null;
  // Compliance
  has_marking: boolean | null;
  has_contract: boolean | null;
  has_deeplink: boolean | null;
  has_closing_docs: boolean | null;
  has_full_recording: boolean | null;
  all_data_filled: boolean | null;
  has_quality_content: boolean | null;
  complies_with_rules: boolean | null;
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
  q?: string;
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
  return crmApi.get<IntegrationsPage>(`/integrations${q ? `?${q}` : ''}`);
}

export function getIntegration(id: number): Promise<IntegrationDetailOut> {
  return crmApi.get<IntegrationDetailOut>(`/integrations/${id}`);
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
  // Audience
  theme?: string | null;
  audience_age?: string | null;
  subscribers?: number | null;
  min_reach?: number | null;
  engagement_rate?: string | null;
  // Fact metrics
  fact_views?: number | null;
  fact_cpm?: string | null;
  fact_clicks?: number | null;
  fact_ctr?: string | null;
  fact_cpc?: string | null;
  fact_carts?: number | null;
  cr_to_cart?: string | null;
  fact_orders?: number | null;
  cr_to_order?: string | null;
  fact_revenue?: string | null;
  // Content & links
  contract_url?: string | null;
  post_url?: string | null;
  tz_url?: string | null;
  screen_url?: string | null;
  post_content?: string | null;
  analysis?: string | null;
  recommended_models?: string | null;
  // Compliance
  has_marking?: boolean | null;
  has_contract?: boolean | null;
  has_deeplink?: boolean | null;
  has_closing_docs?: boolean | null;
  has_full_recording?: boolean | null;
  all_data_filled?: boolean | null;
  has_quality_content?: boolean | null;
  complies_with_rules?: boolean | null;
}

/**
 * Mirrors `IntegrationCreate` on the BFF — required fields for create, optional for patch.
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
  // Audience
  theme?: string | null;
  audience_age?: string | null;
  subscribers?: number | null;
  min_reach?: number | null;
  engagement_rate?: string | null;
  // Fact metrics
  fact_views?: number | null;
  fact_cpm?: string | null;
  fact_clicks?: number | null;
  fact_ctr?: string | null;
  fact_cpc?: string | null;
  fact_carts?: number | null;
  cr_to_cart?: string | null;
  fact_orders?: number | null;
  cr_to_order?: string | null;
  fact_revenue?: string | null;
  // Content & links
  contract_url?: string | null;
  post_url?: string | null;
  tz_url?: string | null;
  screen_url?: string | null;
  post_content?: string | null;
  analysis?: string | null;
  recommended_models?: string | null;
  // Compliance
  has_marking?: boolean | null;
  has_contract?: boolean | null;
  has_deeplink?: boolean | null;
  has_closing_docs?: boolean | null;
  has_full_recording?: boolean | null;
  all_data_filled?: boolean | null;
  has_quality_content?: boolean | null;
  complies_with_rules?: boolean | null;
}

export function createIntegration(body: IntegrationInput): Promise<IntegrationOut> {
  return crmApi.post<IntegrationOut>('/integrations', body);
}

export function updateIntegration(id: number, body: IntegrationUpdate): Promise<IntegrationOut> {
  return crmApi.patch<IntegrationOut>(`/integrations/${id}`, body);
}
