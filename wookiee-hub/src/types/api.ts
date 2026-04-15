// ---------------------------------------------------------------------------
// API response types — mirrors the backend contract
// ---------------------------------------------------------------------------

// -- Finance ----------------------------------------------------------------

export interface PeriodFinance {
  orders_count: number
  orders_rub: number
  sales_count: number
  revenue_before_spp: number
  revenue_after_spp: number
  margin: number
  margin_pct: number
  adv_internal: number
  adv_external: number
  adv_total: number
  cost_of_goods: number
  logistics: number
  storage: number
  commission: number
  nds: number
  spp_amount: number
  returns_revenue: number
  penalty: number
  retention: number
  deduction: number
  revenue_before_spp_gross: number
  drr_pct: number
}

export interface FinanceSummary {
  current: PeriodFinance
  previous: PeriodFinance
}

export interface ModelRow {
  model: string
  mp: "wb" | "ozon"
  period: "current" | "previous"
  sales_count: number
  revenue_before_spp: number
  margin: number
  margin_pct: number
  adv_internal: number
  adv_external: number
  cost_of_goods: number
  drr_pct: number
}

// -- ABC --------------------------------------------------------------------

export interface AbcArticle {
  article: string
  model: string
  category: "A" | "B" | "C" | "New"
  status?: string
  color_code?: string
  collection?: string
  revenue: number
  orders: number
  margin: number
  margin_pct: number
  share: number
  adv_total: number
  drr: number
  turnover_days?: number
}

// -- Traffic ----------------------------------------------------------------

export interface TrafficPeriod {
  card_opens: number
  add_to_cart: number
  funnel_orders: number
  buyouts: number
  ad_views: number
  ad_clicks: number
  ad_to_cart: number
  ad_orders: number
  ad_spend: number
  ctr: number
  cpc: number
}

export interface TrafficSummary {
  current: TrafficPeriod
  previous: TrafficPeriod
}

export interface TrafficModelRow {
  model: string
  card_opens: number
  add_to_cart: number
  funnel_orders: number
  ad_views: number
  ad_clicks: number
  ad_spend: number
  ctr: number
  cpc: number
}

export interface OrganicVsPaid {
  organic_orders: number
  organic_revenue: number
  paid_orders: number
  paid_revenue: number
  paid_share_pct: number
}

export interface ExternalBreakdown {
  channel: string
  spend: number
  orders: number
  revenue: number
  drr_pct: number
}

// -- Series -----------------------------------------------------------------

export interface DailySeries {
  date: string
  orders_count: number
  sales_count: number
  revenue_before_spp: number
  margin: number
  adv_total: number
  logistics: number
  cost_of_goods: number
  storage: number
}

export interface WeeklySeries {
  week_start: string
  orders_count: number
  sales_count: number
  revenue_before_spp: number
  margin: number
  adv_total: number
}

// -- Stocks -----------------------------------------------------------------

export interface StocksSummary {
  total_stock_value: number
  fbo_value: number
  fbo_count: number
  frozen_value: number
  turnover_days_avg: number
}

export interface TurnoverRow {
  model: string
  mp: string
  avg_stock: number
  stock_mp: number
  stock_moysklad: number
  daily_sales: number
  turnover_days: number
  sales_count: number
  revenue: number
  margin: number
}

// -- Promo / Advertising ----------------------------------------------------

export interface PromoModelRow {
  model: string
  ad_spend: number
  ad_orders: number
  drr_pct: number
  romi_pct: number
  adv_internal: number
  adv_external: number
  adv_bloggers: number
  adv_vk: number
}

export interface AdDailySeries {
  date: string
  ad_spend: number
  ad_orders: number
  ad_revenue: number
  drr_pct: number
}

export interface BudgetRow {
  channel: string
  planned: number
  spent: number
  utilization_pct: number
}

// -- Common query params ----------------------------------------------------

export interface ApiQueryParams {
  [key: string]: string | number | undefined
  start_date: string
  end_date: string
  mp?: "wb" | "ozon" | "all"
}
