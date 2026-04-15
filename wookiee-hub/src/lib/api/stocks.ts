import { get } from "@/lib/api-client"
import type { ApiQueryParams, StocksSummary, TurnoverRow } from "@/types/api"

export async function fetchStocksSummary(params: ApiQueryParams): Promise<StocksSummary> {
  const res = await get<{ avg_stock: number; channel: string }>("/api/stocks/summary", params)
  return {
    total_stock_value: res.avg_stock,
    fbo_value: res.avg_stock,
    fbo_count: 0,
    frozen_value: 0,
    turnover_days_avg: 0,
  }
}

export async function fetchStocksTurnover(params: ApiQueryParams) {
  const res = await get<{ rows: TurnoverRow[] }>("/api/stocks/turnover", params)
  return res.rows
}
