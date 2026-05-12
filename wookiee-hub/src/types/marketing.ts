export type SearchQueryGroup = 'brand' | 'external' | 'cr_general' | 'cr_personal'
export type SearchQueryStatus = 'active' | 'paused' | 'archived'

export interface SearchQueryRow {
  unified_id: string                      // 'B1' | 'S42'
  source_id: number
  source_table: 'branded_queries' | 'substitute_articles'
  group_kind: SearchQueryGroup
  query_text: string
  artikul_id: number | null
  nomenklatura_wb: string | null
  ww_code: string | null
  campaign_name: string | null
  purpose: string | null
  model_hint: string | null
  creator_ref: string | null              // Phase 1: always null. Phase 2 will populate.
  status: SearchQueryStatus
  created_at: string
  updated_at: string | null
}

export interface SearchQueryStatsAgg {
  unified_id: string
  frequency: number
  transitions: number
  cart_adds: number
  orders: number
}

export interface SearchQueryWeeklyStat {
  search_query_id: number
  week_start: string
  frequency: number
  transitions: number
  additions: number
  orders: number
}

export type PromoStatus = 'active' | 'paused' | 'expired' | 'archived'

export interface PromoCodeRow {
  id: number
  code: string
  name: string | null
  external_uuid: string | null
  channel: string | null
  discount_pct: number | null
  valid_from: string | null
  valid_until: string | null
  status: PromoStatus
  notes: string | null
  created_at: string
  updated_at: string
}

export interface PromoStatWeekly {
  promo_code_id: number
  week_start: string
  sales_rub: number
  payout_rub: number
  orders_count: number
  returns_count: number
  avg_discount_pct: number
  avg_check: number
}

export interface PromoProductBreakdownRow {
  promo_code_id: number
  week_start: string
  artikul_id: number | null
  sku_label: string
  model_code: string | null
  qty: number
  amount_rub: number
}

/** Aggregated breakdown (sum qty/amount across weeks per sku). */
export interface PromoProductBreakdownAgg {
  sku_label: string
  model_code: string | null
  qty: number
  amount_rub: number
}

export interface MarketingChannel {
  id: number
  slug: string
  label: string
  is_active: boolean
}

export interface SyncLogEntry {
  id: number
  job_name: string
  status: 'running' | 'success' | 'failed'
  started_at: string
  finished_at: string | null
  rows_processed: number | null
  rows_written: number | null
  weeks_covered: string | null
  error_message: string | null
  triggered_by: string | null
}

// v4 fidelity status mapping (design 2026-05-12)
// DB stores active|paused|archived; UI shows active|free|archive
export type StatusUI = 'active' | 'free' | 'archive'
export type StatusDB = 'active' | 'paused' | 'archived'

export const STATUS_UI_TO_DB: Record<StatusUI, StatusDB> = {
  active: 'active',
  free: 'paused',
  archive: 'archived',
}

export const STATUS_DB_TO_UI: Record<StatusDB, StatusUI> = {
  active: 'active',
  paused: 'free',
  archived: 'archive',
}

export const STATUS_LABELS: Record<StatusUI, string> = {
  active: 'Используется',
  free: 'Свободен',
  archive: 'Архив',
}

export const STATUS_COLORS: Record<StatusUI, 'green' | 'blue' | 'gray'> = {
  active: 'green',
  free: 'blue',
  archive: 'gray',
}
