import { get } from "@/lib/api-client"
import type {
  AdDailySeries,
  ApiQueryParams,
  BudgetRow,
  PromoModelRow,
} from "@/types/api"

/** Backend ModelAdRoiRow */
interface ModelAdRoiRaw {
  period: string
  model: string
  ad_spend: number
  ad_orders: number
  revenue: number
  margin: number
  drr_pct: number | null
  romi: number | null
}

export async function fetchPromoModelRoi(params: ApiQueryParams): Promise<PromoModelRow[]> {
  const rows = await get<ModelAdRoiRaw[]>("/api/promo/model-ad-roi", params)
  // Only current period, map to frontend shape
  return rows
    .filter((r) => r.period === "current")
    .map((r) => ({
      model: r.model,
      ad_spend: r.ad_spend,
      ad_orders: r.ad_orders,
      drr_pct: r.drr_pct ?? 0,
      romi_pct: r.romi ?? 0,
      adv_internal: r.ad_spend, // backend doesn't split; total goes here
      adv_external: 0,
      adv_bloggers: 0,
      adv_vk: 0,
    }))
}

/** Backend AdDailyRow */
interface AdDailyRaw {
  date: string
  views: number
  clicks: number
  spend: number
  to_cart: number
  orders: number
  ctr: number
  cpc: number
}

export async function fetchAdDailySeries(params: ApiQueryParams): Promise<AdDailySeries[]> {
  const rows = await get<AdDailyRaw[]>("/api/promo/ad-daily", params)
  return rows.map((r) => ({
    date: r.date,
    ad_spend: r.spend,
    ad_orders: r.orders,
    ad_revenue: 0, // backend doesn't provide per-day revenue
    drr_pct: 0, // would need revenue to compute
  }))
}

export function fetchBudgetUtilization(params: ApiQueryParams) {
  return get<BudgetRow[]>("/api/promo/budget-utilization", params)
}
