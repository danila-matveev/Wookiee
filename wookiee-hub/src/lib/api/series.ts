import { get } from "@/lib/api-client"
import type { ApiQueryParams, DailySeries, WeeklySeries } from "@/types/api"

export async function fetchDailySeries(params: ApiQueryParams) {
  const res = await get<{ series: DailySeries[] }>("/api/series/daily", params)
  return res.series
}

export async function fetchWeeklySeries(params: ApiQueryParams) {
  const res = await get<{ weeks: WeeklySeries[] }>("/api/series/weekly", params)
  return res.weeks
}
