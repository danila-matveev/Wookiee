import { get } from "@/lib/api-client"
import type {
  ApiQueryParams,
  ExternalBreakdown,
  OrganicVsPaid,
  TrafficModelRow,
  TrafficSummary,
  TrafficPeriod,
} from "@/types/api"

/** Backend returns arrays of objects with a `period` field ("current" | "previous"). */
interface OrganicRow {
  period: string
  card_opens: number
  add_to_cart: number
  funnel_orders: number
  buyouts: number
}

interface AdRow {
  period: string
  ad_views: number
  ad_clicks: number
  ad_to_cart: number
  ad_orders: number
  ad_spend: number
  ctr: number
  cpc: number
}

interface TrafficSummaryRaw {
  organic: OrganicRow[]
  ads: AdRow[]
}

function findByPeriod<T extends { period: string }>(arr: T[], period: string): T | undefined {
  return arr.find((r) => r.period === period)
}

function buildPeriod(org: OrganicRow | undefined, ad: AdRow | undefined): TrafficPeriod {
  return {
    card_opens: org?.card_opens ?? 0,
    add_to_cart: org?.add_to_cart ?? 0,
    funnel_orders: org?.funnel_orders ?? 0,
    buyouts: org?.buyouts ?? 0,
    ad_views: ad?.ad_views ?? 0,
    ad_clicks: ad?.ad_clicks ?? 0,
    ad_to_cart: ad?.ad_to_cart ?? 0,
    ad_orders: ad?.ad_orders ?? 0,
    ad_spend: ad?.ad_spend ?? 0,
    ctr: ad?.ctr ?? 0,
    cpc: ad?.cpc ?? 0,
  }
}

export async function fetchTrafficSummary(params: ApiQueryParams): Promise<TrafficSummary> {
  const res = await get<TrafficSummaryRaw>("/api/traffic/summary", params)

  return {
    current: buildPeriod(
      findByPeriod(res.organic, "current"),
      findByPeriod(res.ads, "current"),
    ),
    previous: buildPeriod(
      findByPeriod(res.organic, "previous"),
      findByPeriod(res.ads, "previous"),
    ),
  }
}

export function fetchTrafficByModel(params: ApiQueryParams) {
  return get<TrafficModelRow[]>("/api/traffic/by-model", params)
}

/** Backend OrganicVsPaidResponse */
interface OrgVsPaidRaw {
  organic: Array<{
    period: string
    card_opens: number
    add_to_cart: number
    funnel_orders: number
    buyouts: number
  }>
  paid: Array<{
    period: string
    ad_views: number
    ad_clicks: number
    ad_to_cart: number
    ad_orders: number
    ad_spend: number
  }>
}

export async function fetchOrganicVsPaid(params: ApiQueryParams): Promise<OrganicVsPaid> {
  const res = await get<OrgVsPaidRaw>("/api/traffic/organic-vs-paid", params)

  const orgCurrent = res.organic.find((r) => r.period === "current")
  const paidCurrent = res.paid.find((r) => r.period === "current")

  const organicOrders = orgCurrent?.funnel_orders ?? 0
  const paidOrders = paidCurrent?.ad_orders ?? 0
  const paidSpend = paidCurrent?.ad_spend ?? 0
  const totalOrders = organicOrders + paidOrders

  return {
    organic_orders: organicOrders,
    organic_revenue: 0, // backend doesn't provide revenue split
    paid_orders: paidOrders,
    paid_revenue: paidSpend,
    paid_share_pct: totalOrders > 0 ? (paidOrders / totalOrders) * 100 : 0,
  }
}

/** Backend ExternalBreakdownResponse */
interface ExtBreakdownRaw {
  wb: Array<{
    period: string
    adv_internal: number
    adv_bloggers: number
    adv_vk: number
    adv_creators: number
    adv_total: number
  }>
  ozon: Array<{
    period: string
    adv_internal: number
    adv_bloggers: number
    adv_vk: number
    adv_creators: number
    adv_total: number
  }>
}

export async function fetchExternalBreakdown(params: ApiQueryParams): Promise<ExternalBreakdown[]> {
  const res = await get<ExtBreakdownRaw>("/api/traffic/external-breakdown", params)

  // Combine WB + OZON current-period rows into channel-based breakdown
  const channels: Record<string, { spend: number }> = {}

  function addChannel(name: string, value: number) {
    if (value <= 0) return
    if (!channels[name]) channels[name] = { spend: 0 }
    channels[name].spend += value
  }

  for (const source of [res.wb, res.ozon]) {
    const current = source.find((r) => r.period === "current")
    if (!current) continue
    addChannel("Внутренняя МП", current.adv_internal)
    addChannel("Блогеры", current.adv_bloggers)
    addChannel("ВК", current.adv_vk)
    addChannel("Creators", current.adv_creators)
  }

  return Object.entries(channels).map(([channel, data]) => ({
    channel,
    spend: data.spend,
    orders: 0, // backend doesn't provide per-channel orders
    revenue: 0,
    drr_pct: 0,
  }))
}
