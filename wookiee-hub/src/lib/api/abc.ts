import { get } from "@/lib/api-client"
import type { AbcArticle, ApiQueryParams } from "@/types/api"

/** Raw article shape returned by the backend */
interface AbcArticleRaw {
  article: string
  model: string | null
  mp: string
  orders_count: number
  sales_count: number
  revenue: number
  margin: number
  adv_internal: number
  adv_external: number
  adv_total: number
  margin_share_pct: number
  cumulative_share_pct: number
  abc_category: string
  status?: string | null
  model_kod?: string | null
  model_osnova?: string | null
  color_code?: string | null
  color?: string | null
  tip_kollekcii?: string | null
}

function mapArticle(raw: AbcArticleRaw): AbcArticle {
  const marginPct = raw.revenue > 0 ? (raw.margin / raw.revenue) * 100 : 0
  const drr = raw.revenue > 0 ? (raw.adv_total / raw.revenue) * 100 : 0
  return {
    article: raw.article,
    model: raw.model ?? raw.article,
    category: raw.abc_category as AbcArticle["category"],
    status: raw.status ?? undefined,
    color_code: raw.color_code ?? undefined,
    collection: raw.tip_kollekcii ?? undefined,
    revenue: raw.revenue,
    orders: raw.orders_count,
    margin: raw.margin,
    margin_pct: Math.round(marginPct * 100) / 100,
    share: raw.margin_share_pct,
    adv_total: raw.adv_total,
    drr: Math.round(drr * 100) / 100,
  }
}

export async function fetchAbcByArticle(params: ApiQueryParams): Promise<AbcArticle[]> {
  const res = await get<{ articles: AbcArticleRaw[]; total_margin: number; article_count: number }>(
    "/api/abc/by-article",
    params,
  )
  return res.articles.map(mapArticle)
}
