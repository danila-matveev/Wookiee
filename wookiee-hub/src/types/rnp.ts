export type RnpPhase = "norm" | "decline" | "recovery"

export interface RnpWeek {
  week_start: string
  week_end: string
  week_label: string
  phase: RnpPhase
  // Заказы
  orders_qty: number | null
  orders_rub: number | null
  orders_spp_rub: number | null
  avg_order_rub: number | null
  avg_order_spp_rub: number | null
  spp_pct: number | null
  // Продажи
  sales_qty: number | null
  buyout_pct: number | null
  sales_rub: number | null
  avg_sale_rub: number | null
  // Воронка
  clicks_total: number | null
  cart_total: number | null
  cr_card_to_cart: number | null
  cr_cart_to_order: number | null
  cr_total: number | null
  // Реклама итого
  adv_total_rub: number | null
  drr_total_from_sales: number | null
  drr_total_from_orders: number | null
  // Внутренняя реклама
  adv_internal_rub: number | null
  drr_internal_from_sales: number | null
  drr_internal_from_orders: number | null
  orders_organic_qty: number | null
  orders_internal_qty: number | null
  adv_views: number | null
  adv_clicks: number | null
  ctr_internal: number | null
  cpc_internal: number | null
  cpo_internal: number | null
  cpm_internal: number | null
  adv_internal_profit_forecast: number | null
  romi_internal: number | null
  // Внешняя реклама итого
  adv_external_rub: number | null
  drr_external_from_sales: number | null
  drr_external_from_orders: number | null
  ext_views: number | null
  ext_clicks: number | null
  ctr_external: number | null
  // Блогеры
  blogger_rub: number | null
  drr_blogger_from_sales: number | null
  drr_blogger_from_orders: number | null
  blogger_views: number | null
  blogger_clicks: number | null
  ctr_blogger: number | null
  blogger_carts: number | null
  blogger_orders: number | null
  blogger_profit_forecast: number | null
  romi_blogger: number | null
  blogger_no_stats: boolean
  // ВК SIDS
  vk_sids_rub: number | null
  drr_vk_sids_from_sales: number | null
  drr_vk_sids_from_orders: number | null
  vk_sids_views: number | null
  vk_sids_clicks: number | null
  ctr_vk_sids: number | null
  vk_sids_orders: number | null
  cpo_vk_sids: number | null
  // SIDS Contractor
  sids_contractor_rub: number | null
  drr_sids_contractor_from_sales: number | null
  drr_sids_contractor_from_orders: number | null
  sids_contractor_views: number | null
  sids_contractor_clicks: number | null
  ctr_sids_contractor: number | null
  sids_contractor_orders: number | null
  cpo_sids_contractor: number | null
  // Яндекс
  yandex_contractor_rub: number | null
  drr_yandex_contractor_from_sales: number | null
  drr_yandex_contractor_from_orders: number | null
  yandex_contractor_views: number | null
  yandex_contractor_clicks: number | null
  ctr_yandex_contractor: number | null
  yandex_contractor_orders: number | null
  cpo_yandex_contractor: number | null
  // Маржа
  margin_before_ads_rub: number | null
  margin_before_ads_pct: number | null
  margin_rub: number | null
  margin_pct: number | null
  // Прогноз
  sales_forecast_rub: number | null
  margin_forecast_rub: number | null
  margin_forecast_pct: number | null
}

export interface RnpResponse {
  model: string
  marketplace: string
  date_from: string
  date_to: string
  buyout_forecast_used: number
  ext_ads_available: boolean
  weeks: RnpWeek[]
}

export interface RnpModel {
  label: string
  value: string
}

export interface RnpModelsResponse {
  marketplace: string
  models: RnpModel[]
}
