import type { RnpResponse, RnpModelsResponse } from "@/types/rnp"

const BASE    = import.meta.env.VITE_ANALYTICS_API_URL ?? "https://analytics-api.os.wookiee.shop"
const API_KEY = import.meta.env.VITE_ANALYTICS_API_KEY ?? ""

const AUTH_HEADERS = { "x-api-key": API_KEY }

export async function fetchRnpModels(): Promise<RnpModelsResponse> {
  const res = await fetch(`${BASE}/api/rnp/models?marketplace=wb`, { headers: AUTH_HEADERS })
  if (!res.ok) throw new Error(`fetchRnpModels: ${res.status}`)
  return res.json()
}

export async function fetchRnpWeeks(params: {
  model: string
  dateFrom: string  // YYYY-MM-DD
  dateTo: string
  buyoutForecast?: number
}): Promise<RnpResponse> {
  const url = new URL(`${BASE}/api/rnp/weeks`)
  url.searchParams.set("model", params.model)
  url.searchParams.set("date_from", params.dateFrom)
  url.searchParams.set("date_to", params.dateTo)
  if (params.buyoutForecast !== undefined) {
    url.searchParams.set("buyout_forecast", String(params.buyoutForecast))
  }
  const res = await fetch(url.toString(), { headers: AUTH_HEADERS })
  if (!res.ok) throw new Error(`fetchRnpWeeks: ${res.status}`)
  return res.json()
}
